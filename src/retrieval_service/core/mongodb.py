"""MongoDB Atlas connection and operations."""

from pymongo import MongoClient
from motor.motor_asyncio import AsyncIOMotorClient
from typing import List, Dict, Any, Optional
import logging
from .config import settings

logger = logging.getLogger(__name__)


class MongoDBClient:
    """MongoDB Atlas client for vector search and document storage."""

    def __init__(self):
        self.client = None
        self.async_client = None
        self.db = None
        self.async_db = None

    def connect(self):
        """Establish connection to MongoDB Atlas."""
        try:
            # Synchronous client
            self.client = MongoClient(settings.mongodb_uri)
            self.db = self.client[settings.mongodb_database]

            # Asynchronous client
            self.async_client = AsyncIOMotorClient(settings.mongodb_uri)
            self.async_db = self.async_client[settings.mongodb_database]

            # Test connection
            self.client.admin.command("ping")
            logger.info("Connected to MongoDB Atlas")

        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise

    def create_vector_index(self):
        """Create vector search index if it doesn't exist."""
        try:
            collection = self.db[settings.mongodb_collection_vectors]

            # Note: This is just for documentation purposes
            # The actual index must be created via MongoDB Atlas UI
            logger.info("Vector search index configuration for MongoDB Atlas:")
            logger.info("Index name: vector_index")
            logger.info("Collection: vectors")
            logger.info("JSON configuration:")
            logger.info(
                f"""
{{
  "fields": [{{
    "type": "vector",
    "path": "embedding",
    "numDimensions": {settings.embedding_dimensions},
    "similarity": "cosine"
  }}]
}}
            """
            )
            logger.info("Please create this index manually in MongoDB Atlas Search UI")

        except Exception as e:
            logger.warning(f"Index creation note: {e}")

    async def insert_document(self, document: Dict[str, Any]) -> str:
        """Insert a document with metadata."""
        collection = self.async_db[settings.mongodb_collection_documents]
        result = await collection.insert_one(document)
        return str(result.inserted_id)

    async def insert_vector(self, vector_doc: Dict[str, Any]) -> str:
        """Insert a vector document."""
        collection = self.async_db[settings.mongodb_collection_vectors]
        result = await collection.insert_one(vector_doc)
        return str(result.inserted_id)

    async def vector_search(
        self,
        query_embedding: List[float],
        limit: int = 5,
        filter: Optional[Dict] = None,
    ) -> List[Dict[str, Any]]:
        """Perform vector similarity search."""
        collection = self.async_db[settings.mongodb_collection_vectors]

        # Build the search query
        search_query = {
            "index": settings.mongodb_vector_index,
            "path": "embedding",
            "queryVector": query_embedding,
            "numCandidates": limit * 10,
            "limit": limit,
        }

        # Add filter if provided
        if filter:
            search_query["filter"] = filter

        pipeline = [
            {"$vectorSearch": search_query},
            {
                "$project": {
                    "_id": 1,
                    "document_id": 1,
                    "text": 1,
                    "metadata": 1,
                    "score": {"$meta": "vectorSearchScore"},
                }
            },
        ]

        results = []
        try:
            async for doc in collection.aggregate(pipeline):
                results.append(doc)
        except Exception as e:
            if "Atlas Search index" in str(e) or "vector_index" in str(e):
                logger.error(
                    f"Vector search index not found. Please create it in MongoDB Atlas. Error: {e}"
                )
                logger.error(
                    "Follow the instructions in the setup output or see MongoDB Atlas Setup Guide"
                )
                # Return empty results instead of crashing
                return []
            else:
                raise

        return results

    async def hybrid_search(
        self, query_embedding: List[float], text_query: str, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Perform hybrid search combining vector and text search."""
        # Vector search results
        vector_results = await self.vector_search(query_embedding, limit)

        # Text search on documents collection
        text_collection = self.async_db[settings.mongodb_collection_documents]
        text_results = []

        async for doc in (
            text_collection.find(
                {"$text": {"$search": text_query}}, {"score": {"$meta": "textScore"}}
            )
            .sort([("score", {"$meta": "textScore"})])
            .limit(limit)
        ):
            text_results.append(doc)

        # Combine and deduplicate results
        combined = {}

        # Add vector results with higher weight
        for doc in vector_results:
            doc_id = str(doc.get("document_id", doc["_id"]))
            combined[doc_id] = {**doc, "combined_score": doc.get("score", 0) * 0.7}

        # Add text results
        for doc in text_results:
            doc_id = str(doc["_id"])
            if doc_id in combined:
                combined[doc_id]["combined_score"] += doc.get("score", 0) * 0.3
            else:
                combined[doc_id] = {**doc, "combined_score": doc.get("score", 0) * 0.3}

        # Sort by combined score
        results = sorted(
            combined.values(), key=lambda x: x["combined_score"], reverse=True
        )[:limit]

        return results

    async def get_document_by_id(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a document by ID."""
        collection = self.async_db[settings.mongodb_collection_documents]
        from bson import ObjectId

        try:
            return await collection.find_one({"_id": ObjectId(doc_id)})
        except:
            return await collection.find_one({"_id": doc_id})

    def close(self):
        """Close MongoDB connections."""
        if self.client:
            self.client.close()
        if self.async_client:
            self.async_client.close
        logger.info("MongoDB connections closed")


# Global MongoDB client instance
mongodb_client = MongoDBClient()
