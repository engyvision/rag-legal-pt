"""Vertex AI embeddings generation."""

from typing import List, Dict, Any
import logging
import vertexai
from vertexai.language_models import TextEmbeddingModel, TextEmbeddingInput
from .config import settings
import asyncio
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


class EmbeddingsClient:
    """Client for generating text embeddings using Vertex AI."""

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

    def generate_embedding(
        self, text: str, task_type: str = "RETRIEVAL_DOCUMENT"
    ) -> List[float]:
        """Generate embedding for a single text using gemini-embedding-001."""
        try:
            # Prepare text for embedding with task type
            text_input = TextEmbeddingInput(
                text=self.prepare_text_for_embedding(text), task_type=task_type
            )

            # Generate embedding (gemini-embedding-001 returns full dimensions by default)
            embeddings = self.model.get_embeddings([text_input])
            return embeddings[0].values
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise

    def generate_embeddings_batch(
        self,
        texts: List[str],
        task_type: str = "RETRIEVAL_DOCUMENT",
        batch_size: int = 5,  # Still used for error handling and logging
    ) -> List[List[float]]:
        """Generate embeddings for multiple texts (one at a time for gemini-embedding-001)."""
        all_embeddings = []

        for i, text in enumerate(texts):
            try:
                # gemini-embedding-001 processes one input at a time
                embedding = self.generate_embedding(text, task_type)
                all_embeddings.append(embedding)

                if (i + 1) % batch_size == 0:
                    logger.info(f"Processed {i + 1}/{len(texts)} embeddings")

            except Exception as e:
                logger.error(f"Error generating embedding for text {i}: {e}")
                # Return empty embedding for failed text
                all_embeddings.append([0.0] * settings.embedding_dimensions)

        return all_embeddings

    async def agenerate_embedding(
        self, text: str, task_type: str = "RETRIEVAL_DOCUMENT"
    ) -> List[float]:
        """Async wrapper for embedding generation."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor, self.generate_embedding, text, task_type
        )

    async def agenerate_embeddings_batch(
        self,
        texts: List[str],
        task_type: str = "RETRIEVAL_DOCUMENT",
        batch_size: int = 5,
    ) -> List[List[float]]:
        """Async wrapper for batch embedding generation."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor, self.generate_embeddings_batch, texts, task_type, batch_size
        )

    def prepare_text_for_embedding(self, text: str, max_length: int = 8000) -> str:
        """Prepare text for embedding generation.

        gemini-embedding-001 has a limit of 2048 tokens per input,
        and approximately 20,000 tokens max request limit.
        """
        # Clean and truncate text
        text = text.strip()

        # Replace multiple whitespaces with single space
        text = " ".join(text.split())

        # Truncate if too long (gemini-embedding-001 has 2048 token limit per input)
        # Using character-based approximation: ~4 chars per token
        if len(text) > max_length:
            text = text[:max_length] + "..."

        return text

    def chunk_text(
        self, text: str, chunk_size: int = None, chunk_overlap: int = None
    ) -> List[Dict[str, Any]]:
        """Split text into chunks for embedding."""
        chunk_size = chunk_size or settings.chunk_size
        chunk_overlap = chunk_overlap or settings.chunk_overlap

        # Simple character-based chunking
        # In production, use more sophisticated chunking (e.g., by sentence)
        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size
            chunk_text = text[start:end]

            # Find last complete sentence if possible
            if end < len(text):
                last_period = chunk_text.rfind(".")
                last_newline = chunk_text.rfind("\n")
                split_point = max(last_period, last_newline)

                if split_point > chunk_size * 0.5:  # Only split if we keep >50%
                    chunk_text = chunk_text[: split_point + 1]
                    end = start + split_point + 1

            chunks.append(
                {
                    "text": chunk_text.strip(),
                    "start_char": start,
                    "end_char": end,
                    "chunk_index": len(chunks),
                }
            )

            start = end - chunk_overlap

        return chunks


# Global embeddings client instance
embeddings_client = EmbeddingsClient()
