import 'dotenv/config';
import express, { Request, Response } from "express";
import cors from "cors";
import helmet from "helmet";
import jwt from "jsonwebtoken";
import pg from "pg";
import bcrypt from "bcrypt";

const app = express();

// Fargate-optimized: Persistent connection pool for long-running container
// Pool is shared across all requests for the lifetime of the container
const pool = new pg.Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: process.env.NODE_ENV === 'production' ? { rejectUnauthorized: false } : false,
  // Container optimization: Persistent connections
  max: 20,                    // Maximum connections in pool
  idleTimeoutMillis: 30000,   // Close idle connections after 30s
  connectionTimeoutMillis: 2000, // Timeout when getting connection
  keepAlive: true,            // Keep connections alive
  keepAliveInitialDelayMillis: 10000
});

// Container pattern: Initialize on startup, not per request
async function initializeDatabase() {
  try {
    await pool.query(`
      CREATE TABLE IF NOT EXISTS users (
        id VARCHAR(255) PRIMARY KEY,
        email VARCHAR(255) UNIQUE NOT NULL,
        name VARCHAR(255) NOT NULL,
        password_hash VARCHAR(255),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
    `);
    console.log('Database initialized successfully');
  } catch (error) {
    console.error('Database initialization failed:', error);
    process.exit(1);
  }
}

// Graceful shutdown for container restarts
process.on('SIGTERM', async () => {
  console.log('SIGTERM received, closing database pool...');
  await pool.end();
  process.exit(0);
});

process.on('SIGINT', async () => {
  console.log('SIGINT received, closing database pool...');
  await pool.end();
  process.exit(0);
});

app.use(helmet());
app.use(cors());
app.use(express.json());

interface User {
  id?: string;
  email: string;
  name: string;
  created_at?: string;
}

interface AuthRequest {
  email: string;
  password: string;
}

interface RegisterRequest {
  email: string;
  name: string;
  password: string;
}

interface AuthenticatedRequest extends Request {
  user?: {
    user_id: string;
    exp: number;
  };
}

const authenticateToken = (req: AuthenticatedRequest, res: Response, next: any) => {
  const authHeader = req.headers['authorization'];
  const token = authHeader && authHeader.split(' ')[1];

  if (!token) {
    return res.status(401).json({ detail: 'Access token required' });
  }

  try {
    const decoded = jwt.verify(token, process.env.JWT_SECRET || 'secret-key') as any;
    req.user = decoded;
    next();
  } catch (error) {
    return res.status(403).json({ detail: 'Invalid or expired token' });
  }
};

// Container health checks for ECS
app.get("/", (req: Request, res: Response) => {
  res.json({ status: "healthy", service: "fargate-express" });
});

app.get("/health", async (req: Request, res: Response) => {
  try {
    // Check database connectivity
    await pool.query('SELECT 1');
    res.json({
      status: "healthy",
      service: "fargate-express",
      database: "connected",
      uptime: process.uptime(),
      memory: process.memoryUsage()
    });
  } catch (error) {
    res.status(503).json({
      status: "unhealthy",
      service: "fargate-express",
      database: "disconnected",
      error: error instanceof Error ? error.message : 'Unknown error'
    });
  }
});

// Suga-specific health check endpoints for ALB
app.get("/x-suga-health", (req: Request, res: Response) => {
  res.status(200).send('OK');
});

// Also handle with /app prefix for ALB
app.get("/app/x-suga-health", (req: Request, res: Response) => {
  res.status(200).send('OK');
});

// Auth Service (Port 4000 equivalent endpoints)
app.post("/auth/login", async (req: Request, res: Response) => {
  try {
    const { email, password }: AuthRequest = req.body;

    const result = await pool.query(
      'SELECT * FROM users WHERE email = $1',
      [email]
    );

    if (result.rows.length === 0) {
      return res.status(401).json({ detail: "Invalid credentials" });
    }

    const user = result.rows[0];

    if (!user.password_hash) {
      return res.status(401).json({ detail: "Invalid credentials" });
    }

    const isValidPassword = await bcrypt.compare(password, user.password_hash);
    if (!isValidPassword) {
      return res.status(401).json({ detail: "Invalid credentials" });
    }

    const token = jwt.sign(
      { user_id: user.id, exp: Math.floor(Date.now() / 1000) + (24 * 60 * 60) },
      process.env.JWT_SECRET || 'secret-key'
    );

    const { password_hash, ...userWithoutPassword } = user;
    res.json({ token, user: userWithoutPassword });
  } catch (error: any) {
    res.status(500).json({ detail: error.message });
  }
});

app.post("/auth/register", async (req: Request, res: Response) => {
  try {
    const { email, name, password }: RegisterRequest = req.body;

    if (!password || password.length < 6) {
      return res.status(400).json({ detail: "Password must be at least 6 characters long" });
    }

    const userId = `user_${Date.now()}`;
    const saltRounds = 10;
    const passwordHash = await bcrypt.hash(password, saltRounds);

    const result = await pool.query(
      'INSERT INTO users (id, email, name, password_hash) VALUES ($1, $2, $3, $4) RETURNING id, email, name, created_at',
      [userId, email, name, passwordHash]
    );

    res.json(result.rows[0]);
  } catch (error: any) {
    res.status(500).json({ detail: error.message });
  }
});

// API Service (Port 3000 equivalent endpoints)
app.get("/api/users", authenticateToken, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const result = await pool.query('SELECT * FROM users ORDER BY created_at DESC');
    res.json(result.rows);
  } catch (error: any) {
    res.status(500).json({ detail: error.message });
  }
});

app.post("/api/users", async (req: Request, res: Response) => {
  try {
    const { email, name }: User = req.body;
    const userId = `user_${Date.now()}`;

    const result = await pool.query(
      'INSERT INTO users (id, email, name) VALUES ($1, $2, $3) RETURNING *',
      [userId, email, name]
    );

    res.json(result.rows[0]);
  } catch (error: any) {
    res.status(500).json({ detail: error.message });
  }
});

app.get("/api/users/:userId", authenticateToken, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const { userId } = req.params;

    const result = await pool.query(
      'SELECT * FROM users WHERE id = $1',
      [userId]
    );

    if (result.rows.length === 0) {
      return res.status(404).json({ detail: "User not found" });
    }

    res.json(result.rows[0]);
  } catch (error: any) {
    res.status(500).json({ detail: error.message });
  }
});

app.delete("/api/users/:userId", authenticateToken, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const { userId } = req.params;

    const result = await pool.query(
      'DELETE FROM users WHERE id = $1 RETURNING *',
      [userId]
    );

    if (result.rows.length === 0) {
      return res.status(404).json({ detail: "User not found" });
    }

    res.json({ detail: "User deleted successfully", user: result.rows[0] });
  } catch (error: any) {
    res.status(500).json({ detail: error.message });
  }
});

const port = process.env.PORT || 9001;

// Container startup: Initialize database then start server
async function startServer() {
  try {
    await initializeDatabase();

    app.listen(port, () => {
      console.log(`Server running on port ${port}`);
    });
  } catch (error) {
    console.error('Failed to start server:', error);
    process.exit(1);
  }
}

startServer();
