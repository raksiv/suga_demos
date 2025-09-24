# Container vs Serverless Architecture Demo

Two identical user management APIs demonstrating **ECS Fargate (Container)** vs **AWS Lambda (Serverless)** patterns.

## Projects

| Project | Architecture | Language | Key Pattern |
|---------|-------------|----------|-------------|
| **fargate-express** | ECS Fargate | TypeScript/Express | Persistent connection pool |
| **lambda-fastapi** | AWS Lambda | Python/FastAPI | Fresh connections per request |

## Quick Start

```bash
# Fargate Express
cd fargate-express/
docker-compose up -d && npm install && suga dev

# Lambda FastAPI
cd lambda-fastapi/
docker-compose up -d && uv sync && suga dev
```

## Architectural Differences

| Aspect | Fargate Container | Lambda Serverless |
|--------|------------------|-------------------|
| **Connection Strategy** | Persistent pool (20 connections) | Fresh connection per request |
| **State** | Shared across requests | Stateless, isolated requests |
| **Startup** | One-time initialization | Per-request table check |
| **Health Checks** | `/health` with DB connectivity | Basic health only |
| **Shutdown** | Graceful SIGTERM handling | Automatic cleanup |
| **Cold Start** | ~30s container startup | ~100-500ms function init |
| **Scaling** | Horizontal container scaling | Auto-scale to 1000+ concurrent |
| **Cost Model** | Fixed hourly cost | Pay per execution |

## When to Choose

| Use Fargate When | Use Lambda When |
|------------------|-----------------|
| Predictable high traffic (>100 req/min) | Sporadic/unpredictable traffic |
| Need persistent state/connections | Event-driven processing |
| WebSocket/real-time apps | Simple API backends |
| Background tasks alongside API | Microservices architecture |
| >3GB memory requirements | Cost optimization for low traffic |

## Database Config

| Project | Port | Connection String |
|---------|------|-------------------|
| **fargate-express** | 5433 | `postgresql://admin:secure_password@localhost:5433/fargate_express_db` |
| **lambda-fastapi** | 5434 | `postgresql://admin:secure_password@localhost:5434/lambda_fastapi_db` |

## API Endpoints

Both implement identical functionality:

| Endpoint | Method | Auth Required | Description |
|----------|--------|---------------|-------------|
| `/auth/register` | POST | No | User registration |
| `/auth/login` | POST | No | JWT authentication |
| `/api/users` | GET | Yes | List users |
| `/api/users/{id}` | GET | Yes | Get user |
| `/api/users/{id}` | DELETE | Yes | Delete user |
| `/api/users` | POST | No | Create user |

**Frontend**: Both projects serve UI at `/website/` for testing

## Code Patterns

**Fargate (Persistent Pool)**:
```typescript
const pool = new pg.Pool({ max: 20, keepAlive: true });
// Pool shared across all requests
```

**Lambda (Per-Request)**:
```python
connection = await get_db_connection()  # Fresh per request
try:
    # Process request
finally:
    await close_db_connection(connection)  # Always cleanup
```

## Performance

| Metric | Fargate | Lambda |
|--------|---------|--------|
| **Warm Latency** | <10ms | 10-50ms |
| **Memory** | Shared | Isolated |
| **Connections** | Pooled | Per-request overhead |
| **Low Traffic Cost** | High (always running) | Very low (pay-per-use) |