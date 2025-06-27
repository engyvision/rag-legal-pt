"""API routes for the retrieval service."""

from fastapi import APIRouter, HTTPException, UploadFile, File
from typing import List, Optional
import logging
from pydantic import BaseModel
from datetime import datetime

from ..services.retrieval import RetrievalService
from ..services.processing import ProcessingService
from ..core.config import settings
from ..core.mongodb import mongodb_client
from ..core.embeddings import EmbeddingsClient
from src.common.models import DocumentSource
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
embeddings_client = EmbeddingsClient()


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
    Optimized version using MongoDB aggregation.
    """
    try:
        urls = request.get("urls", [])
        existing_docs = {}
        
        from ..core.mongodb import mongodb_client
        from ..core.config import settings
        
        docs_collection = mongodb_client.async_db[settings.mongodb_collection_documents]
        vectors_collection = mongodb_client.async_db[settings.mongodb_collection_vectors]
        
        # Step 1: Get all documents that match the URLs in a single query
        documents = await docs_collection.find(
            {"url": {"$in": urls}}
        ).to_list(length=None)
        
        if not documents:
            return existing_docs
        
        # Create a mapping of document IDs to URLs for later use
        doc_id_to_url = {doc["_id"]: doc["url"] for doc in documents}
        doc_ids = list(doc_id_to_url.keys())
        
        # Step 2: Use aggregation to get chunk information for all documents at once
        pipeline = [
            # Match all chunks for our documents
            {"$match": {"document_id": {"$in": doc_ids}}},
            
            # Group by document_id to get counts and sizes
            {"$group": {
                "_id": "$document_id",
                "num_chunks": {"$sum": 1},
                "chunk_sizes": {"$push": {"$strLenCP": "$text"}},  # Get length of each chunk
                "total_text_length": {"$sum": {"$strLenCP": "$text"}},
                "avg_chunk_size": {"$avg": {"$strLenCP": "$text"}}
            }},
            
            # Optional: Add document info (if you want more details)
            {"$lookup": {
                "from": settings.mongodb_collection_documents,
                "localField": "_id",
                "foreignField": "_id",
                "as": "document_info"
            }},
            
            # Unwind the document info (since it's an array)
            {"$unwind": {
                "path": "$document_info",
                "preserveNullAndEmptyArrays": True
            }},
            
            # Project final fields
            {"$project": {
                "_id": 1,
                "num_chunks": 1,
                "chunk_sizes": 1,
                "total_text_length": 1,
                "avg_chunk_size": {"$round": ["$avg_chunk_size", 0]},
                "document_type": "$document_info.document_type",
                "title": "$document_info.title",
                "updated_at": "$document_info.updated_at",
                "created_at": "$document_info.created_at"
            }}
        ]
        
        # Execute aggregation
        chunk_results = await vectors_collection.aggregate(pipeline).to_list(length=None)
        
        # Create a mapping of document_id to chunk info
        chunk_info_map = {result["_id"]: result for result in chunk_results}
        
        # Step 3: Combine document and chunk information
        for doc in documents:
            doc_id = doc["_id"]
            url = doc["url"]
            chunk_info = chunk_info_map.get(doc_id, {})
            
            existing_docs[url] = {
                "exists": True,
                "document_id": str(doc_id),
                "last_updated": doc.get("updated_at", doc.get("created_at")).isoformat() if doc.get("updated_at") or doc.get("created_at") else None,
                "document_type": doc.get("document_type"),
                "title": doc.get("title"),
                "chunks_count": chunk_info.get("num_chunks", 0),
                "total_text_length": chunk_info.get("total_text_length", 0),
                "avg_chunk_size": chunk_info.get("avg_chunk_size", 0),
                "chunk_sizes": chunk_info.get("chunk_sizes", [])[:5]  # Only first 5 to avoid large response
            }
        
        logger.info(f"Checked {len(urls)} URLs, found {len(existing_docs)} existing documents")
        return existing_docs
        
    except Exception as e:
        logger.error(f"Error checking existing documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/check-existing-documents-simple")
async def check_existing_documents_simple(request: dict):
    """
    Simpler version that just gets chunk counts efficiently.
    """
    try:
        urls = request.get("urls", [])
        
        from ..core.mongodb import mongodb_client
        from ..core.config import settings
        
        docs_collection = mongodb_client.async_db[settings.mongodb_collection_documents]
        
        # Single aggregation pipeline to get everything
        pipeline = [
            # Match documents by URL
            {"$match": {"url": {"$in": urls}}},
            
            # Lookup chunk counts from vectors collection
            {"$lookup": {
                "from": settings.mongodb_collection_vectors,
                "let": {"doc_id": "$_id"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$document_id", "$$doc_id"]}}},
                    {"$count": "count"}
                ],
                "as": "chunk_info"
            }},
            
            # Extract the count from the array
            {"$addFields": {
                "chunks_count": {
                    "$ifNull": [{"$arrayElemAt": ["$chunk_info.count", 0]}, 0]
                }
            }},
            
            # Project only needed fields
            {"$project": {
                "_id": 1,
                "url": 1,
                "document_type": 1,
                "title": 1,
                "updated_at": 1,
                "created_at": 1,
                "chunks_count": 1
            }}
        ]
        
        # Execute aggregation
        results = await docs_collection.aggregate(pipeline).to_list(length=None)
        
        # Convert to expected format
        existing_docs = {}
        for doc in results:
            existing_docs[doc["url"]] = {
                "exists": True,
                "document_id": str(doc["_id"]),
                "last_updated": doc.get("updated_at", doc.get("created_at")).isoformat() if doc.get("updated_at") or doc.get("created_at") else None,
                "document_type": doc.get("document_type"),
                "title": doc.get("title"),
                "chunks_count": doc.get("chunks_count", 0)
            }
        
        logger.info(f"Checked {len(urls)} URLs, found {len(existing_docs)} existing documents (simple)")
        return existing_docs
        
    except Exception as e:
        logger.error(f"Error checking existing documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scrape-document")
async def scrape_document(request: dict):
    """
    Scrape a single document with custom parameters.
    
    Parameters:
    - url: Document URL to scrape
    - document_type: Type of document (lei, decreto_lei, etc.)
    - title: Document title
    - issuing_body: Issuing body/organization
    - description: Document description
    - chunk_size: Text chunk size for embeddings (default from settings)
    - chunk_overlap: Overlap between chunks (default from settings)
    - force_rescrape: Boolean - if True, will delete existing document and re-scrape
    - metadata: Additional metadata dictionary
    
    Returns:
    - status: "success", "re_scraped", or "already_exists"
    - document_id: MongoDB document ID
    - chunks_created: Number of new chunks created
    - chunks_deleted: Number of old chunks deleted (when force_rescrape=True)
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
        
        force_rescrape = request.get("force_rescrape", False)
        chunks_deleted_count = 0
        was_existing = bool(existing)
        
        if existing and not force_rescrape:
            return {
                "status": "already_exists",
                "document_id": str(existing["_id"]),
                "message": "Document already exists in database"
            }
        elif existing and force_rescrape:
            # Delete existing document and all its chunks
            doc_id = existing["_id"]
            
            # Step 1: Delete old chunks for this document (following MongoDB best practices)
            vectors_collection = mongodb_client.async_db[settings.mongodb_collection_vectors]
            chunks_deleted = await vectors_collection.delete_many({"document_id": doc_id})
            chunks_deleted_count = chunks_deleted.deleted_count
            
            # Step 2: Delete the document itself
            docs_collection = mongodb_client.async_db[settings.mongodb_collection_documents]
            await docs_collection.delete_one({"_id": doc_id})
            
            logger.info(f"Force re-scrape: Deleted existing document {doc_id} and {chunks_deleted_count} chunks")
        
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
            "status": "re_scraped" if was_existing and force_rescrape else "success",
            "document_id": doc_id,
            "chunks_created": vectors_created,
            "text_length": len(scraped_content),
            "chunk_size_used": chunk_size,
            "chunk_overlap_used": chunk_overlap,
            "chunks_deleted": chunks_deleted_count
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


@router.get("/document-statistics-by-type")
async def get_document_statistics_by_type():
    """Get comprehensive statistics grouped by document type."""
    try:
        from ..core.mongodb import mongodb_client
        from ..core.config import settings
        
        docs_collection = mongodb_client.async_db[settings.mongodb_collection_documents]
        
        pipeline = [
            # First, get document info with chunk counts
            {"$lookup": {
                "from": settings.mongodb_collection_vectors,
                "let": {"doc_id": "$_id"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$document_id", "$$doc_id"]}}},
                    {"$group": {
                        "_id": None,
                        "count": {"$sum": 1},
                        "total_size": {"$sum": {"$strLenCP": "$text"}}
                    }}
                ],
                "as": "chunk_stats"
            }},
            
            # Extract stats
            {"$addFields": {
                "chunks_count": {"$ifNull": [{"$arrayElemAt": ["$chunk_stats.count", 0]}, 0]},
                "total_text_size": {"$ifNull": [{"$arrayElemAt": ["$chunk_stats.total_size", 0]}, 0]}
            }},
            
            # Group by document type
            {"$group": {
                "_id": "$document_type",
                "doc_count": {"$sum": 1},
                "total_chunks": {"$sum": "$chunks_count"},
                "total_text_size": {"$sum": "$total_text_size"},
                "avg_chunks_per_doc": {"$avg": "$chunks_count"},
                "avg_text_size_per_doc": {"$avg": "$total_text_size"}
            }},
            
            # Sort by document count
            {"$sort": {"doc_count": -1}},
            
            # Format the output
            {"$project": {
                "document_type": "$_id",
                "document_count": "$doc_count",
                "total_chunks": "$total_chunks",
                "total_text_size": "$total_text_size",
                "avg_chunks_per_doc": {"$round": ["$avg_chunks_per_doc", 1]},
                "avg_text_size_per_doc": {"$round": ["$avg_text_size_per_doc", 0]},
                "_id": 0
            }}
        ]
        
        results = await docs_collection.aggregate(pipeline).to_list(length=None)
        
        logger.info(f"Retrieved statistics for {len(results)} document types")
        return {"statistics_by_type": results}
        
    except Exception as e:
        logger.error(f"Error getting document statistics by type: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chunk-anomalies")
async def find_documents_with_chunk_anomalies():
    """Find documents that might need re-chunking."""
    try:
        from ..core.mongodb import mongodb_client
        from ..core.config import settings
        
        docs_collection = mongodb_client.async_db[settings.mongodb_collection_documents]
        
        pipeline = [
            # Get chunk statistics per document
            {"$lookup": {
                "from": settings.mongodb_collection_vectors,
                "let": {"doc_id": "$_id"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$document_id", "$$doc_id"]}}},
                    {"$group": {
                        "_id": None,
                        "count": {"$sum": 1},
                        "sizes": {"$push": {"$strLenCP": "$text"}},
                        "min_size": {"$min": {"$strLenCP": "$text"}},
                        "max_size": {"$max": {"$strLenCP": "$text"}},
                        "avg_size": {"$avg": {"$strLenCP": "$text"}},
                        "std_dev": {"$stdDevPop": {"$strLenCP": "$text"}}
                    }}
                ],
                "as": "chunk_analysis"
            }},
            
            # Unwind and filter
            {"$unwind": "$chunk_analysis"},
            
            # Find anomalies
            {"$match": {
                "$or": [
                    # Very few chunks for a large document
                    {"$and": [
                        {"chunk_analysis.count": {"$lt": 3}},
                        {"chunk_analysis.avg_size": {"$gt": 2000}}
                    ]},
                    # Very small chunks
                    {"chunk_analysis.min_size": {"$lt": 100}},
                    # High variance in chunk sizes
                    {"chunk_analysis.std_dev": {"$gt": 500}},
                    # Suspiciously uniform chunks (might indicate bad chunking)
                    {"chunk_analysis.std_dev": {"$lt": 10}}
                ]
            }},
            
            # Project useful info
            {"$project": {
                "_id": 0,  # Exclude ObjectId to avoid serialization issues
                "document_id": {"$toString": "$_id"},  # Convert ObjectId to string
                "title": 1,
                "document_type": 1,
                "url": 1,
                "chunk_count": "$chunk_analysis.count",
                "avg_chunk_size": {"$round": ["$chunk_analysis.avg_size", 0]},
                "min_chunk_size": "$chunk_analysis.min_size",
                "max_chunk_size": "$chunk_analysis.max_size",
                "size_std_dev": {"$round": ["$chunk_analysis.std_dev", 0]},
                "anomaly_reasons": {
                    "$cond": [
                        {"$lt": ["$chunk_analysis.count", 3]}, 
                        "too_few_chunks", 
                        {"$cond": [
                            {"$lt": ["$chunk_analysis.min_size", 100]},
                            "very_small_chunks",
                            {"$cond": [
                                {"$gt": ["$chunk_analysis.std_dev", 500]},
                                "high_size_variance",
                                "suspiciously_uniform"
                            ]}
                        ]}
                    ]
                }
            }}
        ]
        
        results = await docs_collection.aggregate(pipeline).to_list(length=None)
        
        logger.info(f"Found {len(results)} documents with chunk anomalies")
        return {"anomalous_documents": results}
        
    except Exception as e:
        logger.error(f"Error finding chunk anomalies: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rescrape-candidates")
async def find_rescrape_candidates(days_old: int = 30):
    """Find documents that might need re-scraping."""
    try:
        from ..core.mongodb import mongodb_client
        from ..core.config import settings
        from datetime import datetime, timedelta
        
        docs_collection = mongodb_client.async_db[settings.mongodb_collection_documents]
        
        cutoff_date = datetime.now() - timedelta(days=days_old)
        
        pipeline = [
            # Match old documents
            {"$match": {
                "$or": [
                    {"updated_at": {"$lt": cutoff_date}},
                    {"updated_at": {"$exists": False}}
                ]
            }},
            
            # Get chunk info
            {"$lookup": {
                "from": settings.mongodb_collection_vectors,
                "let": {"doc_id": "$_id"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$document_id", "$$doc_id"]}}},
                    {"$count": "count"}
                ],
                "as": "chunk_info"
            }},
            
            # Check for issues
            {"$match": {
                "$or": [
                    # No chunks at all
                    {"chunk_info": {"$size": 0}},
                    # Very few chunks (might indicate failed scraping)
                    {"$expr": {"$lt": [{"$arrayElemAt": ["$chunk_info.count", 0]}, 2]}}
                ]
            }},
            
            # Project results
            {"$project": {
                "title": 1,
                "url": 1,
                "document_type": 1,
                "last_updated": {"$ifNull": ["$updated_at", "$created_at"]},
                "days_old": {
                    "$divide": [
                        {"$subtract": [datetime.now(), {"$ifNull": ["$updated_at", "$created_at"]}]},
                        1000 * 60 * 60 * 24  # Convert to days
                    ]
                },
                "chunk_count": {"$ifNull": [{"$arrayElemAt": ["$chunk_info.count", 0]}, 0]},
                "needs_rescrape": True
            }},
            
            # Sort by age
            {"$sort": {"days_old": -1}}
        ]
        
        results = await docs_collection.aggregate(pipeline).to_list(length=None)
        
        logger.info(f"Found {len(results)} documents that may need re-scraping")
        return {
            "rescrape_candidates": results,
            "criteria": {
                "days_old_threshold": days_old,
                "min_chunks_threshold": 2
            }
        }
        
    except Exception as e:
        logger.error(f"Error finding rescrape candidates: {e}")
        raise HTTPException(status_code=500, detail=str(e))