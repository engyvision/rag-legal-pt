"""API routes for the retrieval service."""

from fastapi import APIRouter, HTTPException, UploadFile, File
from typing import List, Optional
import logging
from pydantic import BaseModel

from ..services.retrieval import RetrievalService
from ..services.processing import ProcessingService
from .models import (
    QueryRequest,
    QueryResponse,
    DocumentUploadResponse,
    DocumentProcessRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize services
retrieval_service = RetrievalService()
processing_service = ProcessingService()


@router.post("/query", response_model=QueryResponse)
async def query_documents(request: QueryRequest):
    """
    Query legal documents using natural language.
    """
    try:
        logger.info(f"Processing query: {request.query}")

        # Perform retrieval
        response = await retrieval_service.query(
            query=request.query,
            language=request.language,
            top_k=request.top_k,
            use_llm=request.use_llm,
            filters=request.filters,
        )

        return QueryResponse(**response)

    except Exception as e:
        logger.error(f"Query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search", response_model=List[dict])
async def search_documents(request: QueryRequest):
    """
    Search for relevant documents without LLM processing.
    """
    try:
        results = await retrieval_service.search_only(
            query=request.query,
            top_k=request.top_k,
            search_type=request.search_type,
            filters=request.filters,
        )

        return results

    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...), document_type: Optional[str] = "legal_document"
):
    """
    Upload a document for processing.
    """
    try:
        # Validate file
        if not file.filename.endswith((".pdf", ".txt", ".docx")):
            raise HTTPException(
                status_code=400,
                detail="Unsupported file format. Use PDF, TXT, or DOCX.",
            )

        # Process upload
        result = await processing_service.process_upload(
            file=file, document_type=document_type
        )

        return DocumentUploadResponse(**result)

    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/process")
async def process_document(request: DocumentProcessRequest):
    """
    Process a document from Cloud Storage.
    """
    try:
        result = await processing_service.process_document(
            gcs_path=request.gcs_path, metadata=request.metadata
        )

        return {"status": "processed", "document_id": result}

    except Exception as e:
        logger.error(f"Processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-contract")
async def analyze_contract(
    file: UploadFile = File(...), analysis_type: str = "comprehensive"
):
    """
    Analyze a contract document (Stage 2 feature).
    """
    try:
        # Upload and process
        upload_result = await processing_service.process_upload(
            file=file, document_type="contract"
        )

        # Analyze contract
        analysis = await retrieval_service.analyze_contract(
            document_id=upload_result["document_id"], analysis_type=analysis_type
        )

        return analysis

    except Exception as e:
        logger.error(f"Contract analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/document/{document_id}")
async def get_document(document_id: str):
    """
    Retrieve a specific document by ID.
    """
    try:
        from ..core.mongodb import mongodb_client

        document = await mongodb_client.get_document_by_id(document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        # Convert ObjectId to string
        document["_id"] = str(document["_id"])

        return document

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document retrieval error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_statistics():
    """
    Get service statistics.
    """
    try:
        from ..core.mongodb import mongodb_client
        from ..core.config import settings

        docs_collection = mongodb_client.async_db[settings.mongodb_collection_documents]
        vectors_collection = mongodb_client.async_db[
            settings.mongodb_collection_vectors
        ]

        doc_count = await docs_collection.count_documents({})
        vector_count = await vectors_collection.count_documents({})

        return {
            "total_documents": doc_count,
            "total_vectors": vector_count,
            "embedding_model": settings.embedding_model,
            "llm_model": settings.llm_model,
        }

    except Exception as e:
        logger.error(f"Statistics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# This code defines the API routes for the retrieval service, including endpoints for querying documents,
# uploading documents, processing documents, analyzing contracts, and retrieving statistics.
# It uses FastAPI to create the routes and handle requests, with appropriate error handling and logging.
# This code is part of the Portuguese Legal Assistant project, which provides a retrieval service for legal documents.
