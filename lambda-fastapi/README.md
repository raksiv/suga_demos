# Lambda FastAPI Demo

Python FastAPI with stateless per-request connections for AWS Lambda deployment.

## Setup

1. **Start Database**:
   ```bash
   docker-compose up -d
   ```

2. **Install Dependencies**:
   ```bash
   uv venv && source .venv/bin/activate
   uv sync
   ```

3. **Set Environment**:
   ```bash
   export DATABASE_URL="postgresql://admin:secure_password@localhost:5434/lambda_fastapi_db"
   ```

## Run

```bash
suga dev
```

## Endpoints

- **Frontend**: `http://localhost:8000/website/`
- **API**: `http://localhost:8000/api/users`
- **Docs**: `http://localhost:8000/docs`

## Architecture

- **Pattern**: Serverless with fresh connection per request
- **Database**: New connection created and closed for each invocation
- **Handler**: Mangum adapter converts Lambda events to ASGI