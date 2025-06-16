"""Tests for retrieval service."""

from src.common.utils import extract_law_references, clean_text, extract_dates
from src.retrieval_service.core.embeddings import EmbeddingsClient
from src.retrieval_service.services.retrieval import RetrievalService
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
import sys
import os

# Add src to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestRetrievalService:
    """Test cases for retrieval service."""

    @pytest.fixture
    def retrieval_service(self):
        """Create a retrieval service instance."""
        return RetrievalService()

    @pytest.mark.asyncio
    async def test_query_with_llm(self, retrieval_service):
        """Test query with LLM response."""
        # Mock dependencies
        with patch('src.retrieval_service.services.retrieval.embeddings_client') as mock_embeddings, \
                patch('src.retrieval_service.services.retrieval.mongodb_client') as mock_mongodb, \
                patch('src.retrieval_service.services.retrieval.llm_client') as mock_llm:

            # Setup mocks
            mock_embeddings.agenerate_embedding = AsyncMock(
                return_value=[0.1] * 768
            )

            mock_mongodb.vector_search = AsyncMock(return_value=[
                {
                    "document_id": "123",
                    "text": "Sample legal text",
                    "score": 0.95
                }
            ])

            mock_mongodb.get_document_by_id = AsyncMock(return_value={
                "_id": "123",
                "title": "Test Law",
                "document_type": "lei",
                "publication_date": "2023-01-01"
            })

            mock_llm.agenerate_response = AsyncMock(
                return_value="This is a test response about Portuguese law."
            )

            # Execute query
            result = await retrieval_service.query(
                query="What is the test law about?",
                top_k=5,
                use_llm=True
            )

            # Assertions
            assert result["query"] == "What is the test law about?"
            assert result["answer"] == "This is a test response about Portuguese law."
            assert len(result["sources"]) == 1
            assert result["sources"][0]["title"] == "Test Law"

    @pytest.mark.asyncio
    async def test_search_only(self, retrieval_service):
        """Test search without LLM."""
        with patch('src.retrieval_service.services.retrieval.embeddings_client') as mock_embeddings, \
                patch('src.retrieval_service.services.retrieval.mongodb_client') as mock_mongodb:

            mock_embeddings.agenerate_embedding = AsyncMock(
                return_value=[0.1] * 768
            )

            mock_mongodb.vector_search = AsyncMock(return_value=[
                {"_id": "1", "text": "Result 1", "score": 0.9},
                {"_id": "2", "text": "Result 2", "score": 0.8}
            ])

            results = await retrieval_service.search_only(
                query="test query",
                top_k=10,
                search_type="vector"
            )

            assert len(results) == 2
            assert results[0]["score"] == 0.9


class TestTextProcessing:
    """Test text processing utilities."""

    def test_extract_law_references(self):
        """Test extraction of law references."""
        text = """
        De acordo com a Lei n.º 23/2023 e o Decreto-Lei n.º 45/2023,
        bem como a Portaria n.º 123/2023, estabelece-se o seguinte...
        """

        references = extract_law_references(text)

        assert len(references) == 3
        assert references[0]["type"] == "lei"
        assert references[0]["number"] == "23/2023"
        assert references[1]["type"] == "decreto_lei"
        assert references[2]["type"] == "portaria"

    def test_extract_dates(self):
        """Test date extraction."""
        text = """
        A lei foi publicada em 15 de maio de 2023.
        Entra em vigor no dia 01/06/2023.
        Revoga a lei anterior de 2022-12-31.
        """

        dates = extract_dates(text)

        assert len(dates) == 3
        assert dates[0]["date"] == "2023-05-15"
        assert dates[1]["date"] == "2023-06-01"
        assert dates[2]["date"] == "2022-12-31"

    def test_clean_text(self):
        """Test text cleaning."""
        text = "  This   has  extra   spaces  \n\n\n and newlines  "
        cleaned = clean_text(text)

        assert cleaned == "This has extra spaces and newlines"


class TestEmbeddings:
    """Test embeddings functionality."""

    def test_chunk_text(self):
        """Test text chunking."""
        client = EmbeddingsClient()

        text = "A" * 2500  # Long text
        chunks = client.chunk_text(text, chunk_size=1000, chunk_overlap=200)

        assert len(chunks) == 3
        assert len(chunks[0]["text"]) <= 1000
        assert chunks[1]["start_char"] == 800  # 1000 - 200 overlap

    def test_prepare_text_for_embedding(self):
        """Test text preparation."""
        client = EmbeddingsClient()

        text = "  Multiple   spaces   " + "X" * 3000
        prepared = client.prepare_text_for_embedding(text, max_length=100)

        assert prepared.startswith("Multiple spaces")
        assert len(prepared) <= 103  # 100 + "..."
        assert prepared.endswith("...")


@pytest.mark.asyncio
async def test_contract_analysis():
    """Test contract analysis functionality."""
    service = RetrievalService()

    with patch('src.retrieval_service.services.retrieval.mongodb_client') as mock_mongodb, \
            patch('src.retrieval_service.services.retrieval.llm_client') as mock_llm:

        mock_mongodb.get_document_by_id = AsyncMock(return_value={
            "_id": "123",
            "text": "Sample contract text",
            "document_type": "contract"
        })

        mock_llm.analyze_contract = Mock(return_value={
            "analysis": "Contract analysis result",
            "status": "completed"
        })

        result = await service.analyze_contract(
            document_id="123",
            analysis_type="summary"
        )

        assert result["document_id"] == "123"
        assert result["analysis_type"] == "summary"
        assert "analysis" in result
