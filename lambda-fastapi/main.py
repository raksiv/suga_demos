"""FastAPI application for Lambda deployment with API and Auth services."""

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import List, Optional, Annotated
import os
import asyncpg
import jwt
import bcrypt
from datetime import datetime, timedelta
from mangum import Mangum

app = FastAPI()

# Lambda-optimized: Stateless connection per request
# No persistent connection pool - each request gets fresh connection
async def get_db_connection():
    """
    Lambda pattern: Create fresh connection per request.
    Lambda functions are stateless and may be frozen/thawed.
    """
    connection = await asyncpg.connect(os.environ.get('DATABASE_URL'))

    # Ensure table exists on each connection (Lambda best practice)
    await connection.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id VARCHAR(255) PRIMARY KEY,
            email VARCHAR(255) UNIQUE NOT NULL,
            name VARCHAR(255) NOT NULL,
            password_hash VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    return connection

async def close_db_connection(connection):
    """Lambda pattern: Always close connections after use"""
    if connection:
        await connection.close()

# Models
class User(BaseModel):
    id: Optional[str] = None
    email: str
    name: str

class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    created_at: str

class AuthRequest(BaseModel):
    email: str
    password: str

class RegisterRequest(BaseModel):
    email: str
    name: str
    password: str

# JWT Authentication dependency
async def get_current_user(authorization: Annotated[str | None, Header()] = None):
    """Extract and validate JWT token from Authorization header."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Access token required")

    try:
        # Extract token from "Bearer <token>" format
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization header format")

        token = authorization.split(" ")[1]
        payload = jwt.decode(token, 'secret-key', algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=403, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=403, detail="Invalid token")

# Auth endpoints
@app.post("/auth/login")
async def login(auth_request: AuthRequest):
    """Authenticate user and return JWT token."""
    connection = None
    try:
        # Lambda pattern: Fresh connection per request
        connection = await get_db_connection()

        row = await connection.fetchrow(
            'SELECT * FROM users WHERE email = $1',
            auth_request.email
        )
        if not row:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        user = dict(row)

        if not user.get('password_hash'):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # Verify password
        is_valid = bcrypt.checkpw(
            auth_request.password.encode('utf-8'),
            user['password_hash'].encode('utf-8')
        )

        if not is_valid:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        token = jwt.encode(
            {'user_id': user['id'], 'exp': datetime.utcnow() + timedelta(hours=24)},
            'secret-key',
            algorithm='HS256'
        )

        # Remove password hash from response
        user_response = {k: v for k, v in user.items() if k != 'password_hash'}
        return {"token": token, "user": user_response}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Lambda pattern: Always close connection
        await close_db_connection(connection)

@app.post("/auth/register")
async def register(user: RegisterRequest):
    """Register a new user."""
    connection = None
    try:
        if not user.password or len(user.password) < 6:
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters long")

        # Lambda pattern: Fresh connection per request
        connection = await get_db_connection()
        user_id = f"user_{datetime.utcnow().timestamp()}"

        # Hash the password
        salt = bcrypt.gensalt()
        password_hash = bcrypt.hashpw(user.password.encode('utf-8'), salt)

        row = await connection.fetchrow(
            'INSERT INTO users (id, email, name, password_hash) VALUES ($1, $2, $3, $4) RETURNING id, email, name, created_at',
            user_id, user.email, user.name, password_hash.decode('utf-8')
        )
        user_data = dict(row)
        user_data['created_at'] = user_data['created_at'].isoformat()
        return UserResponse(**user_data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Lambda pattern: Always close connection
        await close_db_connection(connection)

# API endpoints
@app.get("/api/users", response_model=List[UserResponse])
async def get_users(current_user: dict = Depends(get_current_user)):
    """Get all users."""
    connection = None
    try:
        # Lambda pattern: Fresh connection per request
        connection = await get_db_connection()
        rows = await connection.fetch('SELECT * FROM users ORDER BY created_at DESC')
        users = []
        for row in rows:
            user_data = dict(row)
            user_data['created_at'] = user_data['created_at'].isoformat()
            users.append(UserResponse(**user_data))
        return users
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Lambda pattern: Always close connection
        await close_db_connection(connection)

@app.post("/api/users", response_model=UserResponse)
async def create_user(user: User):
    """Create a new user."""
    connection = None
    try:
        # Lambda pattern: Fresh connection per request
        connection = await get_db_connection()
        user_id = f"user_{datetime.utcnow().timestamp()}"
        row = await connection.fetchrow(
            'INSERT INTO users (id, email, name) VALUES ($1, $2, $3) RETURNING *',
            user_id, user.email, user.name
        )
        user_data = dict(row)
        user_data['created_at'] = user_data['created_at'].isoformat()
        return UserResponse(**user_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Lambda pattern: Always close connection
        await close_db_connection(connection)

@app.get("/api/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: str, current_user: dict = Depends(get_current_user)):
    """Get a specific user by ID."""
    connection = None
    try:
        # Lambda pattern: Fresh connection per request
        connection = await get_db_connection()
        row = await connection.fetchrow(
            'SELECT * FROM users WHERE id = $1',
            user_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        user_data = dict(row)
        user_data['created_at'] = user_data['created_at'].isoformat()
        return UserResponse(**user_data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Lambda pattern: Always close connection
        await close_db_connection(connection)

@app.delete("/api/users/{user_id}")
async def delete_user(user_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a specific user by ID."""
    connection = None
    try:
        # Lambda pattern: Fresh connection per request
        connection = await get_db_connection()
        row = await connection.fetchrow(
            'DELETE FROM users WHERE id = $1 RETURNING *',
            user_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        user_data = dict(row)
        user_data['created_at'] = user_data['created_at'].isoformat()
        return {"detail": "User deleted successfully", "user": UserResponse(**user_data)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Lambda pattern: Always close connection
        await close_db_connection(connection)

@app.get("/")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "lambda-fastapi"}

# Lambda handler - Mangum adapter for AWS Lambda
# This converts AWS Lambda events to ASGI and back
handler = Mangum(app, lifespan="off")
