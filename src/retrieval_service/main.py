"""Main FastAPI application for the retrieval service."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import logging
import uvicorn
from contextlib import asynccontextmanager

from .core.config import settings
from .core.mongodb import mongodb_client
from .core.embeddings import embeddings_client
from .core.llm import llm_client
from .api import routes

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Use the global client instances from core modules


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    # Startup
    logger.info("Starting retrieval service...")
    mongodb_client.connect()
    mongodb_client.create_vector_index()
    logger.info("Retrieval service started successfully")

    yield

    # Shutdown
    logger.info("Shutting down retrieval service...")
    mongodb_client.close()
    logger.info("Retrieval service shut down")


# Create FastAPI app
app = FastAPI(
    title="Portuguese Legal Assistant Retrieval Service",
    description="RAG service for Portuguese legal document retrieval",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(routes.router, prefix="/api/v1")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Portuguese Legal Assistant Retrieval Service",
        "status": "running",
        "version": "1.0.0",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Check MongoDB connection
        mongodb_client.client.admin.command("ping")
        return {
            "status": "healthy",
            "mongodb": "connected",
            "embeddings": "ready",
            "llm": "ready",
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unhealthy")


if __name__ == "__main__":
    import os

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "src.retrieval_service.main:app",
        host="0.0.0.0",
        port=port,
        reload=settings.debug,
    )
# This allows running the app with `python -m src.retrieval_service.main`
# or `uvicorn src.retrieval_service.main:app --reload`
# when developing.
# Note: Ensure that the `src` directory is in your PYTHONPATH.
