import uvicorn
import os
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

sys.path.append(os.path.dirname(__file__))

import auth_router
import summarize_router
import history_router
import database
import models_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup
    models_db.Base.metadata.create_all(bind=database.engine)
    yield

app = FastAPI(title="AI Article Summarizer API", lifespan=lifespan)

# Health check endpoint for Render
@app.get("/")
async def health_check():
    return {"message": "AI Article Summarizer API is running"}

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:8081",
        "http://127.0.0.1:8081",
        "http://localhost:5000",
        "http://127.0.0.1:5000",
        # Add production URLs here when deploying
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve React build files (for production single-service deployment)
if os.path.exists("frontend/dist"):
    app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="static")

# Include routers
app.include_router(auth_router.router, prefix="/api", tags=["Authentication"])
app.include_router(summarize_router.router, prefix="/api", tags=["Summarization"])
app.include_router(history_router.router, prefix="/api", tags=["History"])

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    print(f"Server running at http://0.0.0.0:{port}")
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
