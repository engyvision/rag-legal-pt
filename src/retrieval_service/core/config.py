"""Configuration settings for the retrieval service."""

from pydantic_settings import BaseSettings
from typing import Optional
import os
from dotenv import load_dotenv

# Load .env file first to ensure it takes precedence
load_dotenv(override=True)


class Settings(BaseSettings):
    """Application settings."""
    
    # Google Cloud
    google_cloud_project: str
    google_application_credentials: Optional[str] = None
    google_cloud_region: str = "us-central1"
    
    # MongoDB Atlas
    mongodb_uri: str
    mongodb_database: str = "legal_assistant"
    mongodb_collection_documents: str = "documents"
    mongodb_collection_vectors: str = "vectors"
    mongodb_vector_index: str = "vector_index"
    
    # Vertex AI
    vertex_ai_location: str = "us-central1"
    embedding_model: str = "gemini-embedding-001"
    embedding_dimensions: int = 3072  # gemini-embedding-001 dimensions
    llm_model: str = "gemini-1.5-pro-001"
    
    # Cloud Storage
    gcs_bucket_name: str
    gcs_raw_prefix: str = "raw/"
    gcs_processed_prefix: str = "processed/"
    
    # Application
    app_env: str = "development"
    debug: bool = True
    log_level: str = "INFO"
    
    # RAG Configuration
    chunk_size: int = 1000
    chunk_overlap: int = 200
    top_k_results: int = 5
    temperature: float = 0.3
    max_output_tokens: int = 2048
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


# Create global settings instance
settings = Settings()