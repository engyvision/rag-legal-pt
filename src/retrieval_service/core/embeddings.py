"""Vertex AI embeddings generation with article-based chunking for legal documents."""

from typing import List, Dict, Any
import logging
import vertexai
from vertexai.language_models import TextEmbeddingModel, TextEmbeddingInput
from .config import settings
import asyncio
from concurrent.futures import ThreadPoolExecutor
import re

logger = logging.getLogger(__name__)



class EmbeddingsClient:
    """Client for generating text embeddings using Vertex AI with article-aware chunking."""

    def __init__(self):
        self.model = None
        self.executor = ThreadPoolExecutor(max_workers=4)
        self._initialize()

    def _initialize(self):
        """Initialize Vertex AI and embedding model."""
        try:
            vertexai.init(
                project=settings.google_cloud_project,
                location=settings.vertex_ai_location,
            )

            self.model = TextEmbeddingModel.from_pretrained(settings.embedding_model)
            logger.info(f"Initialized embedding model: {settings.embedding_model}")

        except Exception as e:
            logger.error(f"Failed to initialize embeddings client: {e}")
            raise

    def generate_embedding(self, text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> List[float]:
        """Generate embedding for a single text."""
        try:
            text_input = TextEmbeddingInput(text=self.prepare_text_for_embedding(text), task_type=task_type)

            embeddings = self.model.get_embeddings([text_input])
            return embeddings[0].values
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise

    def generate_embeddings_batch(
        self,
        texts: List[str],
        task_type: str = "RETRIEVAL_DOCUMENT",
        batch_size: int = 5,
    ) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        all_embeddings = []

        for i, text in enumerate(texts):
            try:
                embedding = self.generate_embedding(text, task_type)
                all_embeddings.append(embedding)

                if (i + 1) % batch_size == 0:
                    logger.info(f"Processed {i + 1}/{len(texts)} embeddings")

            except Exception as e:
                logger.error(f"Error generating embedding for text {i}: {e}")
                all_embeddings.append([0.0] * settings.embedding_dimensions)

        return all_embeddings

    async def agenerate_embedding(self, text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> List[float]:
        """Async wrapper for embedding generation."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self.generate_embedding, text, task_type)

    async def agenerate_embeddings_batch(
        self,
        texts: List[str],
        task_type: str = "RETRIEVAL_DOCUMENT",
        batch_size: int = 5,
    ) -> List[List[float]]:
        """Async wrapper for batch embedding generation."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self.generate_embeddings_batch, texts, task_type, batch_size)

    def prepare_text_for_embedding(self, text: str, max_length: int = 8000) -> str:
        """Prepare text for embedding generation."""
        text = text.strip()
        text = " ".join(text.split())

        if len(text) > max_length:
            text = text[:max_length] + "..."

        return text

    def chunk_text(
        self,
        text: str,
        chunk_size: int = None,
        chunk_overlap: int = None,
        use_article_chunking: bool = True,
        document_type: str = None,
    ) -> List[Dict[str, Any]]:
        """
        Split text into chunks using article-aware chunking for legal documents.

        Args:
            text: The text to chunk
            chunk_size: Maximum chunk size in characters
            chunk_overlap: Not used in article chunking but kept for compatibility
            use_article_chunking: Whether to use article-based chunking
            document_type: Type of document (lei, decreto_lei, etc.)

        Returns:
            List of chunk dictionaries with text and metadata
        """
        chunk_size = chunk_size or settings.chunk_size

        # Use article-based chunking for legal documents
        if use_article_chunking and document_type in ["lei", "decreto_lei", "decreto", "portaria", "regulamento"]:
            logger.info(f"Using article-based chunking for {document_type} document")
            from .article_chunking import LegalDocumentChunker as ArticleChunker
            chunker = ArticleChunker(max_chunk_size=chunk_size)
            chunks = chunker.chunk_legal_document(text)

            # Convert to expected format
            formatted_chunks = []
            start_char = 0

            for chunk in chunks:
                chunk_text = chunk["text"]
                end_char = start_char + len(chunk_text)

                formatted_chunk = {
                    "text": chunk_text,
                    "start_char": start_char,
                    "end_char": end_char,
                    "chunk_index": chunk.get("chunk_index", len(formatted_chunks)),
                    "metadata": chunk.get("metadata", {}),
                }

                formatted_chunks.append(formatted_chunk)
                start_char = end_char + 2  # Account for paragraph break

            return formatted_chunks

        # Fallback to character-based chunking
        else:
            logger.info("Using character-based chunking")
            return self._chunk_text_by_characters(text, chunk_size, chunk_overlap or 200)

    def _chunk_text_by_characters(self, text: str, chunk_size: int, chunk_overlap: int) -> List[Dict[str, Any]]:
        """Original character-based chunking as fallback."""
        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size
            chunk_text = text[start:end]

            # Try to break at sentence boundary
            if end < len(text):
                last_period = chunk_text.rfind(".")
                last_newline = chunk_text.rfind("\n")
                split_point = max(last_period, last_newline)

                if split_point > chunk_size * 0.5:
                    chunk_text = chunk_text[: split_point + 1]
                    end = start + split_point + 1

            chunks.append(
                {
                    "text": chunk_text.strip(),
                    "start_char": start,
                    "end_char": end,
                    "chunk_index": len(chunks),
                    "metadata": {"chunk_type": "character_based", "article_count": 0},
                }
            )

            start = end - chunk_overlap

        return chunks


# Global embeddings client instance
embeddings_client = EmbeddingsClient()
