# Fargate Express Demo

TypeScript Express.js API with persistent connection pooling for ECS Fargate deployment.

## Setup

1. **Start Database**:
   ```bash
   docker-compose up -d
   ```

2. **Install Dependencies**:
   ```bash
   npm install
   ```

3. **Set Environment**:
   ```bash
   export DATABASE_URL="postgresql://admin:secure_password@localhost:5433/fargate_express_db"
   export JWT_SECRET="your-secret-key"
   ```

## Run

```bash
suga dev
```

## Endpoints

- **Frontend**: `http://localhost:3000/website/`
- **API**: `http://localhost:3000/api/users`
- **Health**: `http://localhost:3000/health`

## Architecture

- **Pattern**: Container with persistent connection pool (20 connections)
- **Database**: Shared pool across all requests, graceful shutdown on SIGTERM
- **Initialization**: One-time setup at container startup