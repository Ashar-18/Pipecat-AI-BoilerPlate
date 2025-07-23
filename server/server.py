#
# Copyright (c) 2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#
import asyncio
import os
from contextlib import asynccontextmanager
from typing import Any, Dict

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
import aiomysql
from fastapi.middleware.cors import CORSMiddleware

# Load environment variables (for local development)
# On Heroku, environment variables are set directly via config vars.
load_dotenv(override=True)

from bot_fast_api import run_bot


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles FastAPI startup and shutdown."""
    print("FastAPI app starting up...")
    yield  # Application runs here
    print("FastAPI app shutting down...")


# Initialize FastAPI app with lifespan manager
app = FastAPI(lifespan=lifespan)

# Configure CORS to allow requests from any origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# New: Add a simple root route to check if the backend is working

# DB config
DB_CONFIG = {
    "host": os.getenv("db_ip"),
    "port": 3306,
    "user": os.getenv("user"),  
    "password": os.getenv("password"),
    "db": os.getenv("db")
}

# Request schema


class EmailCheckRequest(BaseModel):
    email: EmailStr

# Response schema


class EmailCheckResponse(BaseModel):
    message: str
    status: bool


@app.post("/check-email", response_model=EmailCheckResponse)
async def check_email(data: EmailCheckRequest):
    try:
        conn = await aiomysql.connect(**DB_CONFIG)
        async with conn.cursor() as cur:
            await cur.execute("SELECT 1 FROM users WHERE email=%s LIMIT 1", (data.email,))
            result = await cur.fetchone()
        conn.close()

        if result:
            return {"message": "Email found", "status": True}
        else:
            return JSONResponse(status_code=404, content={"message": "Email not found", "status": False})

    except HTTPException as he:
        # Let FastAPI handle it
        raise he
    except Exception as e:
        print(f"Error checking email: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.get("/")
async def read_root():
    """
    Root endpoint to confirm the backend is running.
    """
    return {"message": "Welcome to AiJoe Backend! The API is running."}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("WebSocket connection accepted")
    try:
        await run_bot(websocket)
    except Exception as e:
        print(f"Exception in run_bot: {e}")


@app.post("/connect")
async def bot_connect(request: Request) -> Dict[Any, Any]:
    ws_url = "ws://localhost:7860/ws"
    return {"ws_url": ws_url}


async def main():
    tasks = []
    try:
        config = uvicorn.Config(app, host="0.0.0.0", port=7860)
        server = uvicorn.Server(config)
        tasks.append(server.serve())

        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        print("Tasks cancelled (probably due to shutdown).")


if __name__ == "__main__":
    asyncio.run(main())