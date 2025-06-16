"""Pydantic models for API requests and responses."""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class QueryRequest(BaseModel):
    """Request model for document queries."""
    query: str = Field(..., description="Natural language query in Portuguese")
    top_k: int = Field(
        5, ge=1, le=20, description="Number of results to return")
    use_llm: bool = Field(
        True, description="Whether to use LLM for response generation")
    search_type: str = Field(
        "hybrid", description="Type of search: vector, text, or hybrid")
    filters: Optional[Dict[str, Any]] = Field(
        None, description="MongoDB filters to apply")


class DocumentSource(BaseModel):
    """Model for document sources in responses."""
    document_id: str
    title: str
    text: str
    document_type: Optional[str] = None
    document_number: Optional[str] = None
    publication_date: Optional[str] = None
    url: Optional[str] = None
    score: float = Field(..., ge=0, le=1)
    metadata: Optional[Dict[str, Any]] = None


class QueryResponse(BaseModel):
    """Response model for document queries."""
    query: str
    answer: Optional[str] = Field(None, description="LLM-generated answer")
    sources: List[DocumentSource]
    search_type: str
    processing_time: float
    timestamp: datetime = Field(default_factory=datetime.now)


class DocumentUploadResponse(BaseModel):
    """Response model for document uploads."""
    document_id: str
    filename: str
    document_type: str
    status: str
    gcs_path: Optional[str] = None
    processing_time: float
    chunks_created: Optional[int] = None


class DocumentProcessRequest(BaseModel):
    """Request model for document processing."""
    gcs_path: str = Field(..., description="Path to document in Cloud Storage")
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Document metadata")
    chunk_size: Optional[int] = Field(
        None, description="Override default chunk size")
    chunk_overlap: Optional[int] = Field(
        None, description="Override default chunk overlap")


class ContractAnalysisRequest(BaseModel):
    """Request model for contract analysis."""
    document_id: Optional[str] = None
    contract_text: Optional[str] = None
    analysis_type: str = Field(
        "comprehensive",
        description="Type of analysis: comprehensive, summary, or compliance"
    )


class ContractAnalysisResponse(BaseModel):
    """Response model for contract analysis."""
    document_id: Optional[str]
    analysis_type: str
    analysis: str
    identified_laws: List[str]
    potential_issues: List[str]
    suggestions: List[str]
    status: str
    processing_time: float


class SearchResult(BaseModel):
    """Model for search results."""
    document_id: str
    title: str
    text_snippet: str
    score: float
    document_type: Optional[str] = None
    publication_date: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    """Model for error responses."""
    error: str
    detail: Optional[str] = None
    status_code: int
    timestamp: datetime = Field(default_factory=datetime.now)
