"""Document processing service."""

import logging
import time
from typing import Dict, Any, Optional
from datetime import datetime
import io
import PyPDF2
import docx
from google.cloud import storage

from ..core.config import settings
from ..core.mongodb import mongodb_client
from ..core.embeddings import embeddings_client

logger = logging.getLogger(__name__)


class ProcessingService:
    """Service for processing and indexing documents."""

    def __init__(self):
        self.storage_client = storage.Client()
        self.bucket = self.storage_client.bucket(settings.gcs_bucket_name)

    async def process_upload(self, file, document_type: str = "legal_document") -> Dict[str, Any]:
        """Process an uploaded file."""
        start_time = time.time()

        try:
            # Read file content
            content = await file.read()
            filename = file.filename

            # Extract text based on file type
            if filename.endswith(".pdf"):
                text = self._extract_pdf_text(io.BytesIO(content))
            elif filename.endswith(".txt"):
                text = content.decode("utf-8", errors="ignore")
            elif filename.endswith(".docx"):
                text = self._extract_docx_text(io.BytesIO(content))
            else:
                raise ValueError(f"Unsupported file type: {filename}")

            # Upload to Cloud Storage
            blob_name = f"{settings.gcs_raw_prefix}{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
            blob = self.bucket.blob(blob_name)
            blob.upload_from_string(content)

            # Create document in MongoDB
            document = {
                "title": filename,
                "text": text,
                "source": "upload",
                "document_type": document_type,
                "filename": filename,
                "gcs_path": f"gs://{settings.gcs_bucket_name}/{blob_name}",
                "metadata": {
                    "uploaded_at": datetime.now().isoformat(),
                    "file_size": len(content),
                    "content_type": file.content_type,
                },
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }

            doc_id = await mongodb_client.insert_document(document)

            # Process and create vector embeddings
            chunks_created = await self._create_embeddings(doc_id, text)

            processing_time = time.time() - start_time

            return {
                "document_id": doc_id,
                "filename": filename,
                "document_type": document_type,
                "status": "processed",
                "gcs_path": f"gs://{settings.gcs_bucket_name}/{blob_name}",
                "processing_time": processing_time,
                "chunks_created": chunks_created,
            }

        except Exception as e:
            logger.error(f"Error processing upload: {e}")
            raise

    async def process_document(self, gcs_path: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Process a document from Cloud Storage."""
        try:
            # Parse GCS path
            if not gcs_path.startswith("gs://"):
                raise ValueError("Invalid GCS path format")

            path_parts = gcs_path[5:].split("/", 1)
            bucket_name = path_parts[0]
            blob_name = path_parts[1] if len(path_parts) > 1 else ""

            # Download from Cloud Storage
            bucket = self.storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            content = blob.download_as_bytes()

            # Extract text
            if blob_name.endswith(".pdf"):
                text = self._extract_pdf_text(io.BytesIO(content))
            elif blob_name.endswith(".txt"):
                text = content.decode("utf-8", errors="ignore")
            elif blob_name.endswith(".docx"):
                text = self._extract_docx_text(io.BytesIO(content))
            else:
                text = content.decode("utf-8", errors="ignore")

            # Create document
            document = {
                "title": metadata.get("title", blob_name.split("/")[-1]),
                "text": text,
                "source": metadata.get("source", "gcs"),
                "document_type": metadata.get("document_type", "legal_document"),
                "gcs_path": gcs_path,
                "metadata": metadata or {},
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }

            # Add metadata fields
            for field in ["document_number", "publication_date", "url"]:
                if field in metadata:
                    document[field] = metadata[field]

            doc_id = await mongodb_client.insert_document(document)

            # Create embeddings
            await self._create_embeddings(doc_id, text)

            return doc_id

        except Exception as e:
            logger.error(f"Error processing document from GCS: {e}")
            raise

    async def _create_embeddings(
        self,
        document_id: str,
        text: str,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        document_type: Optional[str] = None,
    ) -> int:
        """Create embeddings for document chunks using article-aware chunking."""
        try:
            # Get document type if not provided
            if not document_type:
                doc = await mongodb_client.get_document_by_id(document_id)
                document_type = doc.get("document_type") if doc else None

            # Chunk the text with article awareness
            chunks = embeddings_client.chunk_text(
                text,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                use_article_chunking=True,
                document_type=document_type,
            )

            if not chunks:
                logger.warning(f"No chunks created for document {document_id}")
                return 0

            # Log chunking statistics
            article_chunks = sum(1 for c in chunks if c.get("metadata", {}).get("chunk_type") == "articles")
            other_chunks = len(chunks) - article_chunks
            logger.info(f"Document chunking: {article_chunks} article-based chunks, {other_chunks} other chunks")

            # Generate embeddings in batches
            chunk_texts = [chunk["text"] for chunk in chunks]
            embeddings = await embeddings_client.agenerate_embeddings_batch(chunk_texts, batch_size=5)

            # Store vectors with enhanced metadata
            from bson import ObjectId

            vectors_created = 0

            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                # Enhance metadata with article information
                chunk_metadata = chunk.get("metadata", {})

                vector_doc = {
                    "document_id": ObjectId(document_id),
                    "text": chunk["text"],
                    "embedding": embedding,
                    "chunk_index": i,
                    "metadata": {
                        "start_char": chunk.get("start_char", 0),
                        "end_char": chunk.get("end_char", len(chunk["text"])),
                        "chunk_size": len(chunk["text"]),
                        "chunk_type": chunk_metadata.get("chunk_type", "unknown"),
                        "article_count": chunk_metadata.get("article_count", 0),
                        "article_numbers": chunk_metadata.get("article_numbers", []),
                        "article_range": chunk_metadata.get("article_range", ""),
                        "document_type": document_type,
                    },
                    "created_at": datetime.now(),
                }

                await mongodb_client.insert_vector(vector_doc)
                vectors_created += 1

            logger.info(f"Created {vectors_created} vectors for document {document_id}")
            return vectors_created

        except Exception as e:
            logger.error(f"Error creating embeddings: {e}")
            raise

    def _extract_pdf_text(self, file_obj: io.BytesIO) -> str:
        """Extract text from PDF file."""
        try:
            reader = PyPDF2.PdfReader(file_obj)
            text = ""

            for page in reader.pages:
                text += page.extract_text() + "\n"

            return text.strip()

        except Exception as e:
            logger.error(f"Error extracting PDF text: {e}")
            return ""

    def _extract_docx_text(self, file_obj: io.BytesIO) -> str:
        """Extract text from DOCX file."""
        try:
            doc = docx.Document(file_obj)
            text = ""

            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"

            return text.strip()

        except Exception as e:
            logger.error(f"Error extracting DOCX text: {e}")
            return ""

    async def reprocess_document(self, document_id: str) -> Dict[str, Any]:
        """Reprocess an existing document to update embeddings."""
        try:
            # Get document
            document = await mongodb_client.get_document_by_id(document_id)
            if not document:
                raise ValueError(f"Document {document_id} not found")

            # Delete existing vectors
            vectors_collection = mongodb_client.async_db[settings.mongodb_collection_vectors]
            from bson import ObjectId

            delete_result = await vectors_collection.delete_many({"document_id": ObjectId(document_id)})

            logger.info(f"Deleted {delete_result.deleted_count} existing vectors")

            # Recreate embeddings
            chunks_created = await self._create_embeddings(document_id, document.get("text", ""))

            # Update document timestamp
            docs_collection = mongodb_client.async_db[settings.mongodb_collection_documents]
            await docs_collection.update_one({"_id": ObjectId(document_id)}, {"$set": {"updated_at": datetime.now()}})

            return {
                "document_id": document_id,
                "vectors_deleted": delete_result.deleted_count,
                "vectors_created": chunks_created,
                "status": "reprocessed",
            }

        except Exception as e:
            logger.error(f"Error reprocessing document: {e}")
            raise
