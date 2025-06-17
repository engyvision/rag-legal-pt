"""Common utility functions."""

import re
import hashlib
import unicodedata
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def clean_text(text: str) -> str:
    """Clean and normalize text."""
    # Remove extra whitespace
    text = re.sub(r"\s+", " ", text)

    # Normalize unicode characters
    text = unicodedata.normalize("NFKC", text)

    # Remove zero-width characters
    text = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", text)

    # Trim
    text = text.strip()

    return text


def extract_law_references(text: str) -> List[Dict[str, str]]:
    """Extract references to laws from text."""
    patterns = {
        "lei": r"Lei\s+n\.?º?\s*(\d+(?:[/-]\d+)*)",
        "decreto_lei": r"Decreto-Lei\s+n\.?º?\s*(\d+(?:[/-]\d+)*)",
        "decreto": r"Decreto\s+n\.?º?\s*(\d+(?:[/-]\d+)*)",
        "portaria": r"Portaria\s+n\.?º?\s*(\d+(?:[/-]\d+)*)",
        "despacho": r"Despacho\s+n\.?º?\s*(\d+(?:[/-]\d+)*)",
        "resolucao": r"Resolução.*?\s+n\.?º?\s*(\d+(?:[/-]\d+)*)",
    }

    references = []

    for doc_type, pattern in patterns.items():
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            references.append(
                {
                    "type": doc_type,
                    "number": match.group(1),
                    "full_reference": match.group(0),
                    "position": match.start(),
                }
            )

    # Sort by position in text
    references.sort(key=lambda x: x["position"])

    return references


def extract_dates(text: str) -> List[Dict[str, Any]]:
    """Extract dates from Portuguese text."""
    # Common Portuguese date patterns
    patterns = [
        # DD de MÊS de AAAA
        r"(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})",
        # DD/MM/AAAA or DD-MM-AAAA
        r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})",
        # AAAA-MM-DD
        r"(\d{4})-(\d{2})-(\d{2})",
    ]

    month_map = {
        "janeiro": 1,
        "fevereiro": 2,
        "março": 3,
        "abril": 4,
        "maio": 5,
        "junho": 6,
        "julho": 7,
        "agosto": 8,
        "setembro": 9,
        "outubro": 10,
        "novembro": 11,
        "dezembro": 12,
    }

    dates = []

    for pattern in patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            try:
                if len(match.groups()) == 3:
                    if match.group(2).lower() in month_map:
                        # Portuguese month name
                        day = int(match.group(1))
                        month = month_map[match.group(2).lower()]
                        year = int(match.group(3))
                    elif "-" in match.group(0) and match.group(1) > 1900:
                        # ISO format YYYY-MM-DD
                        year = int(match.group(1))
                        month = int(match.group(2))
                        day = int(match.group(3))
                    else:
                        # Numeric format DD/MM/YYYY
                        day = int(match.group(1))
                        month = int(match.group(2))
                        year = int(match.group(3))

                    # Validate date
                    date_obj = datetime(year, month, day)

                    dates.append(
                        {
                            "date": date_obj.strftime("%Y-%m-%d"),
                            "original": match.group(0),
                            "position": match.start(),
                        }
                    )

            except (ValueError, IndexError):
                # Invalid date, skip
                continue

    # Remove duplicates and sort
    seen = set()
    unique_dates = []
    for date in dates:
        if date["date"] not in seen:
            seen.add(date["date"])
            unique_dates.append(date)

    unique_dates.sort(key=lambda x: x["position"])

    return unique_dates


def generate_document_id(text: str, metadata: Dict[str, Any] = None) -> str:
    """Generate a unique document ID based on content."""
    # Combine text and metadata for uniqueness
    content = text

    if metadata:
        # Add key metadata fields
        for key in ["document_number", "publication_date", "source"]:
            if key in metadata:
                content += f"|{key}:{metadata[key]}"

    # Generate hash
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def chunk_text_by_sections(
    text: str, max_chunk_size: int = 1000
) -> List[Dict[str, Any]]:
    """Chunk text by sections (articles, chapters, etc.)."""
    # Common section markers in Portuguese legal texts
    section_patterns = [
        r"^Artigo\s+\d+\.?º?",
        r"^Art\.\s+\d+\.?º?",
        r"^CAPÍTULO\s+[IVXLCDM]+",
        r"^TÍTULO\s+[IVXLCDM]+",
        r"^SECÇÃO\s+[IVXLCDM]+",
        r"^§\s*\d+",
    ]

    combined_pattern = "|".join(f"({p})" for p in section_patterns)

    chunks = []
    current_chunk = ""
    current_start = 0

    lines = text.split("\n")

    for i, line in enumerate(lines):
        # Check if this line starts a new section
        if re.match(combined_pattern, line.strip(), re.IGNORECASE):
            # Save current chunk if it exists
            if current_chunk.strip():
                chunks.append(
                    {
                        "text": current_chunk.strip(),
                        "start_line": current_start,
                        "end_line": i - 1,
                        "type": "section",
                    }
                )

            # Start new chunk
            current_chunk = line + "\n"
            current_start = i
        else:
            # Add to current chunk
            potential_chunk = current_chunk + line + "\n"

            # Check if adding this line would exceed max size
            if len(potential_chunk) > max_chunk_size and current_chunk.strip():
                # Save current chunk
                chunks.append(
                    {
                        "text": current_chunk.strip(),
                        "start_line": current_start,
                        "end_line": i - 1,
                        "type": "partial",
                    }
                )

                # Start new chunk with current line
                current_chunk = line + "\n"
                current_start = i
            else:
                current_chunk = potential_chunk

    # Save final chunk
    if current_chunk.strip():
        chunks.append(
            {
                "text": current_chunk.strip(),
                "start_line": current_start,
                "end_line": len(lines) - 1,
                "type": "section",
            }
        )

    return chunks


def validate_document_number(doc_type: str, doc_number: str) -> bool:
    """Validate document number format."""
    patterns = {
        "lei": r"^\d+/\d{4}$",
        "decreto_lei": r"^\d+/\d{4}$",
        "decreto": r"^\d+/\d{4}$",
        "portaria": r"^\d+/\d{4}$",
        "despacho": r"^\d+/\d{4}$",
    }

    pattern = patterns.get(doc_type)
    if pattern:
        return bool(re.match(pattern, doc_number))

    return True  # Default to valid for unknown types


def format_date_portuguese(date_str: str) -> str:
    """Format date in Portuguese format."""
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")

        months = [
            "janeiro",
            "fevereiro",
            "março",
            "abril",
            "maio",
            "junho",
            "julho",
            "agosto",
            "setembro",
            "outubro",
            "novembro",
            "dezembro",
        ]

        return f"{date_obj.day} de {months[date_obj.month - 1]} de {date_obj.year}"

    except ValueError:
        return date_str
