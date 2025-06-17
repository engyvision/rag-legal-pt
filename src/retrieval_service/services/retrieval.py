"""Retrieval service implementation."""

import logging
import time
from typing import List, Dict, Any, Optional
from datetime import datetime

from ..core.mongodb import mongodb_client
from ..core.embeddings import embeddings_client
from ..core.llm import llm_client
from .translation import translation_service

logger = logging.getLogger(__name__)


class RetrievalService:
    """Service for document retrieval and question answering."""

    async def query(
        self,
        query: str,
        language: str = "pt",
        top_k: int = 5,
        use_llm: bool = True,
        filters: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Process a user query and return relevant documents with optional LLM response."""
        start_time = time.time()

        try:
            # Store original query for response
            original_query = query

            # Translate query to Portuguese if needed for vector search
            query_for_search = query
            if language == "en":
                query_for_search = await translation_service.atranslate_to_portuguese(
                    query
                )
                logger.info(
                    f"Translated query from English to Portuguese: {query} -> {query_for_search}"
                )

            # Generate query embedding using Portuguese query
            query_embedding = await embeddings_client.agenerate_embedding(
                query_for_search
            )

            # Perform vector search
            search_results = await mongodb_client.vector_search(
                query_embedding=query_embedding, limit=top_k, filter=filters
            )

            # Enrich results with document data
            sources = []
            for result in search_results:
                doc_id = result.get("document_id")
                if doc_id:
                    doc = await mongodb_client.get_document_by_id(str(doc_id))
                    if doc:
                        sources.append(
                            {
                                "document_id": str(doc_id),
                                "title": doc.get("title", ""),
                                "text": result.get("text", ""),
                                "document_type": doc.get("document_type"),
                                "document_number": doc.get("document_number"),
                                "publication_date": doc.get("publication_date"),
                                "url": doc.get("url"),
                                "score": result.get("score", 0),
                                "metadata": doc.get("metadata", {}),
                            }
                        )

            # Generate LLM response if requested
            answer = None
            if use_llm and sources:
                answer = await llm_client.agenerate_response(
                    query=original_query,
                    query_for_search=query_for_search,
                    contexts=sources,
                    user_language=language,
                )

            processing_time = time.time() - start_time

            return {
                "query": original_query,
                "user_language": language,
                "answer": answer,
                "sources": sources,
                "search_type": "vector",
                "processing_time": processing_time,
            }

        except Exception as e:
            logger.error(f"Error processing query: {e}")
            raise

    async def search_only(
        self,
        query: str,
        top_k: int = 5,
        search_type: str = "hybrid",
        filters: Optional[Dict] = None,
    ) -> List[Dict[str, Any]]:
        """Perform search without LLM processing."""

        if search_type == "vector":
            # Vector search only
            query_embedding = await embeddings_client.agenerate_embedding(query)
            results = await mongodb_client.vector_search(
                query_embedding=query_embedding, limit=top_k, filter=filters
            )

        elif search_type == "hybrid":
            # Hybrid search (vector + text)
            query_embedding = await embeddings_client.agenerate_embedding(query)
            results = await mongodb_client.hybrid_search(
                query_embedding=query_embedding, text_query=query, limit=top_k
            )

        else:  # text search
            # Text search only
            collection = mongodb_client.async_db[
                mongodb_client.settings.mongodb_collection_documents
            ]
            results = []
            async for doc in (
                collection.find(
                    {"$text": {"$search": query}}, {"score": {"$meta": "textScore"}}
                )
                .sort([("score", {"$meta": "textScore"})])
                .limit(top_k)
            ):
                doc["_id"] = str(doc["_id"])
                results.append(doc)

        return results

    async def analyze_contract(
        self, document_id: str, analysis_type: str = "comprehensive"
    ) -> Dict[str, Any]:
        """Analyze a contract document."""
        start_time = time.time()

        try:
            # Retrieve document
            document = await mongodb_client.get_document_by_id(document_id)
            if not document:
                raise ValueError(f"Document {document_id} not found")

            contract_text = document.get("text", "")

            # Perform analysis
            analysis_result = llm_client.analyze_contract(
                contract_text=contract_text, analysis_type=analysis_type
            )

            # Extract relevant laws
            relevant_laws = await self._find_relevant_laws(contract_text)

            # Parse analysis for structured data
            identified_laws = []
            potential_issues = []
            suggestions = []

            # Simple parsing (in production, use structured output from LLM)
            analysis_text = analysis_result.get("analysis", "")
            lines = analysis_text.split("\n")

            current_section = None
            for line in lines:
                line = line.strip()
                if "legislação" in line.lower() or "leis" in line.lower():
                    current_section = "laws"
                elif "problema" in line.lower() or "questão" in line.lower():
                    current_section = "issues"
                elif "sugest" in line.lower():
                    current_section = "suggestions"
                elif line and current_section:
                    if current_section == "laws" and line.startswith("-"):
                        identified_laws.append(line[1:].strip())
                    elif current_section == "issues" and line.startswith("-"):
                        potential_issues.append(line[1:].strip())
                    elif current_section == "suggestions" and line.startswith("-"):
                        suggestions.append(line[1:].strip())

            processing_time = time.time() - start_time

            return {
                "document_id": document_id,
                "analysis_type": analysis_type,
                "analysis": analysis_text,
                "identified_laws": identified_laws or relevant_laws,
                "potential_issues": potential_issues,
                "suggestions": suggestions,
                "status": analysis_result.get("status", "completed"),
                "processing_time": processing_time,
            }

        except Exception as e:
            logger.error(f"Error analyzing contract: {e}")
            raise

    async def _find_relevant_laws(self, contract_text: str) -> List[str]:
        """Find laws that might be relevant to the contract."""
        # Search for laws mentioned in the contract or related to its content

        # Extract potential law references from text
        import re

        law_pattern = r"(?:Lei|Decreto-Lei|Decreto|Portaria)\s*n\.?º?\s*\d+(?:/\d+)?"
        found_laws = re.findall(law_pattern, contract_text, re.IGNORECASE)

        # Also search for relevant laws based on contract type
        # This would query the database for related laws

        return list(set(found_laws))  # Remove duplicates
