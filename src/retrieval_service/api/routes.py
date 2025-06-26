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

# Add these routes to src/retrieval_service/api/routes.py after the existing routes

@router.post("/check-existing-documents")
async def check_existing_documents(request: dict):
    """
    Check which documents already exist in the database.
    """
    try:
        urls = request.get("urls", [])
        existing_docs = {}
        
        from ..core.mongodb import mongodb_client
        
        # Query documents by URL
        docs_collection = mongodb_client.async_db[settings.mongodb_collection_documents]
        
        for url in urls:
            doc = await docs_collection.find_one({"url": url})
            if doc:
                existing_docs[url] = {
                    "exists": True,
                    "document_id": str(doc["_id"]),
                    "last_updated": doc.get("updated_at", doc.get("created_at")).isoformat(),
                    "document_type": doc.get("document_type"),
                    "chunks_count": await mongodb_client.async_db[
                        settings.mongodb_collection_vectors
                    ].count_documents({"document_id": doc["_id"]})
                }
        
        return existing_docs
        
    except Exception as e:
        logger.error(f"Error checking existing documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scrape-document")
async def scrape_document(request: dict):
    """
    Scrape a single document with custom parameters.
    """
    try:
        from src.scrapers.diario_republica import DiarioRepublicaScraper
        
        # Extract parameters
        url = request.get("url")
        document_type = request.get("document_type")
        title = request.get("title")
        issuing_body = request.get("issuing_body")
        description = request.get("description")
        document_number = request.get("document_number")
        publication_date = request.get("publication_date")
        chunk_size = request.get("chunk_size", settings.chunk_size)
        chunk_overlap = request.get("chunk_overlap", settings.chunk_overlap)
        metadata = request.get("metadata", {})
        
        if not url:
            raise HTTPException(status_code=400, detail="URL is required")
        
        # Initialize scraper
        scraper = DiarioRepublicaScraper()
        
        # Check if document already exists
        existing = await mongodb_client.async_db[
            settings.mongodb_collection_documents
        ].find_one({"url": url})
        
        if existing:
            return {
                "status": "already_exists",
                "document_id": str(existing["_id"]),
                "message": "Document already exists in database"
            }
        
        # Scrape content
        scraped_content = scraper.scrape_document_content(url)
        
        if not scraped_content:
            raise HTTPException(
                status_code=400, 
                detail="Could not scrape content from the provided URL"
            )
        
        # Create document
        document = {
            "title": title,
            "text": scraped_content,
            "document_type": document_type,
            "document_number": document_number,
            "publication_date": publication_date,
            "issuing_body": issuing_body,
            "description": description,
            "source": DocumentSource.SCRAPER,
            "url": url,
            "metadata": metadata,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        
        # Insert document
        doc_id = await mongodb_client.insert_document(document)
        
        # Create embeddings with custom parameters
        chunks = embeddings_client.chunk_text(
            scraped_content,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        
        # Generate embeddings
        chunk_texts = [chunk["text"] for chunk in chunks]
        embeddings = await embeddings_client.agenerate_embeddings_batch(
            chunk_texts,
            batch_size=5
        )
        
        # Store vectors
        from bson import ObjectId
        vectors_created = 0
        
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            vector_doc = {
                "document_id": ObjectId(doc_id),
                "text": chunk["text"],
                "embedding": embedding,
                "chunk_index": i,
                "metadata": {
                    "start_char": chunk["start_char"],
                    "end_char": chunk["end_char"],
                    "document_type": document_type,
                    "document_title": title,
                    "issuing_body": issuing_body
                },
                "created_at": datetime.now()
            }
            
            await mongodb_client.insert_vector(vector_doc)
            vectors_created += 1
        
        return {
            "status": "success",
            "document_id": doc_id,
            "chunks_created": vectors_created,
            "text_length": len(scraped_content),
            "chunk_size_used": chunk_size,
            "chunk_overlap_used": chunk_overlap
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error scraping document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ingestion-stats")
async def get_ingestion_stats():
    """
    Get statistics about the data ingestion process.
    """
    try:
        from ..core.mongodb import mongodb_client
        
        docs_collection = mongodb_client.async_db[settings.mongodb_collection_documents]
        vectors_collection = mongodb_client.async_db[settings.mongodb_collection_vectors]
        
        # Get document counts by type
        pipeline = [
            {"$group": {"_id": "$document_type", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        
        doc_types = []
        async for result in docs_collection.aggregate(pipeline):
            doc_types.append({
                "type": result["_id"],
                "count": result["count"]
            })
        
        # Get document counts by source
        source_pipeline = [
            {"$group": {"_id": "$source", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        
        doc_sources = []
        async for result in docs_collection.aggregate(source_pipeline):
            doc_sources.append({
                "source": result["_id"],
                "count": result["count"]
            })
        
        # Get recent documents
        recent_docs = []
        async for doc in docs_collection.find().sort("created_at", -1).limit(10):
            recent_docs.append({
                "title": doc.get("title", ""),
                "document_type": doc.get("document_type"),
                "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None
            })
        
        # Calculate average chunks per document
        total_docs = await docs_collection.count_documents({})
        total_vectors = await vectors_collection.count_documents({})
        avg_chunks = total_vectors / total_docs if total_docs > 0 else 0
        
        return {
            "total_documents": total_docs,
            "total_vectors": total_vectors,
            "average_chunks_per_document": round(avg_chunks, 2),
            "documents_by_type": doc_types,
            "documents_by_source": doc_sources,
            "recent_documents": recent_docs
        }
        
    except Exception as e:
        logger.error(f"Error getting ingestion stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))