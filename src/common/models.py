"""Common data models shared across services."""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class DocumentType(str, Enum):
    """Types of legal documents."""
    LEI = "lei"
    DECRETO_LEI = "decreto_lei"
    DECRETO = "decreto"
    PORTARIA = "portaria"
    DESPACHO = "despacho"
    RESOLUCAO = "resolucao"
    REGULAMENTO = "regulamento"
    AVISO = "aviso"
    DELIBERACAO = "deliberacao"
    CONTRACT = "contract"
    OTHER = "other"


class DocumentSource(str, Enum):
    """Sources of documents."""
    DIARIO_REPUBLICA = "diario_republica"
    UPLOAD = "upload"
    MANUAL = "manual"
    SCRAPER = "scraper"


@dataclass
class Document:
    """Document model."""
    title: str
    text: str
    source: DocumentSource
    document_type: DocumentType
    document_number: Optional[str] = None
    publication_date: Optional[str] = None
    url: Optional[str] = None
    metadata: Dict[str, Any] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()


@dataclass
class DocumentChunk:
    """Document chunk model."""
    document_id: str
    text: str
    chunk_index: int
    start_char: int
    end_char: int
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class QueryResult:
    """Query result model."""
    document_id: str
    title: str
    text: str
    score: float
    document_type: Optional[str] = None
    publication_date: Optional[str] = None
    url: Optional[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class ContractAnalysis:
    """Contract analysis result model."""
    document_id: str
    analysis_type: str
    summary: str
    identified_laws: List[str]
    potential_issues: List[str]
    suggestions: List[str]
    compliance_status: str
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class AnalysisType(str, Enum):
    """Types of contract analysis."""
    COMPREHENSIVE = "comprehensive"
    SUMMARY = "summary"
    COMPLIANCE = "compliance"
    RISK_ASSESSMENT = "risk_assessment"
