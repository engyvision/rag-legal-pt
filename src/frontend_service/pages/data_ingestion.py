"""Data Ingestion Control UI for Portuguese Legal Assistant."""

import streamlit as st
import requests
import os
import csv
import re
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import time

# Add parent directory to path for imports
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from src.common.models import DocumentType
from src.retrieval_service.core.config import settings

# Configuration
RETRIEVAL_SERVICE_URL = os.getenv("RETRIEVAL_SERVICE_URL", "http://localhost:8000")
API_BASE = f"{RETRIEVAL_SERVICE_URL}/api/v1"

# Document type mappings (same as in scraper)
DOCUMENT_TYPE_MAPPING = {
    "Lei.csv": DocumentType.LEI,
    "Decreto-Lei.csv": DocumentType.DECRETO_LEI,
    "Decreto.csv": DocumentType.DECRETO,
    "Portaria.csv": DocumentType.PORTARIA,
}

# Page configuration
st.set_page_config(
    page_title="Data Ingestion Control",
    page_icon="📊",
    layout="wide",
)

# Custom CSS for better UI
st.markdown(
    """
<style>
    .preview-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 0.5rem;
        border: 1px solid #e0e0e0;
    }
    .scraped-indicator {
        color: #28a745;
        font-weight: bold;
    }
    .pending-indicator {
        color: #ffc107;
        font-weight: bold;
    }
    .stats-box {
        background-color: #e8f4f9;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .parameter-box {
        background-color: #fff3cd;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    .analytics-card {
        background-color: #ffffff;
        padding: 1.5rem;
        border-radius: 0.75rem;
        margin: 1rem 0;
        border: 1px solid #e1e5e9;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .analytics-header {
        font-size: 1.1rem;
        font-weight: 600;
        margin-bottom: 1rem;
        color: #1f2937;
    }
    .metric-card {
        background-color: #f8fafc;
        padding: 0.75rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
        border-left: 4px solid #3b82f6;
    }
    .warning-card {
        border-left-color: #f59e0b;
        background-color: #fffbeb;
    }
    .error-card {
        border-left-color: #ef4444;
        background-color: #fef2f2;
    }
    .success-card {
        border-left-color: #10b981;
        background-color: #f0fdf4;
    }
</style>
""",
    unsafe_allow_html=True,
)

# Initialize session state
if "selected_documents" not in st.session_state:
    st.session_state.selected_documents = set()
if "chunk_size" not in st.session_state:
    st.session_state.chunk_size = settings.chunk_size
if "chunk_overlap" not in st.session_state:
    st.session_state.chunk_overlap = settings.chunk_overlap
if "documents_data" not in st.session_state:
    st.session_state.documents_data = []
if "scraping_in_progress" not in st.session_state:
    st.session_state.scraping_in_progress = False
if "analytics_data" not in st.session_state:
    st.session_state.analytics_data = {
        "type_stats": None,
        "chunk_anomalies": None,
        "rescrape_candidates": None,
        "last_updated": None,
    }
if "show_analytics" not in st.session_state:
    st.session_state.show_analytics = False
if "force_rescrape" not in st.session_state:
    st.session_state.force_rescrape = False
if "use_article_chunking" not in st.session_state:
    st.session_state.use_article_chunking = True


def extract_document_number(title: str, doc_type: DocumentType) -> Optional[str]:
    """Extract document number from title."""
    patterns = {
        DocumentType.LEI: r"Lei n\.º (\d+/\d+)",
        DocumentType.DECRETO_LEI: r"Decreto-Lei n\.º (\d+/\d+)",
        DocumentType.DECRETO: r"Decreto n\.º (\d+/\d+)",
        DocumentType.PORTARIA: r"Portaria n\.º (\d+/\d+)",
    }

    pattern = patterns.get(doc_type)
    if pattern:
        match = re.search(pattern, title)
        if match:
            return match.group(1)
    return None


def extract_publication_date(title: str) -> Optional[str]:
    """Extract publication date from title."""
    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", title)
    if date_match:
        return date_match.group(1)
    return None


def estimate_chunks(text_length: int, chunk_size: int, chunk_overlap: int) -> int:
    """Estimate number of chunks for a given text length."""
    if text_length <= chunk_size:
        return 1

    # Calculate effective chunk size (accounting for overlap)
    effective_chunk_size = chunk_size - chunk_overlap
    chunks = 1 + ((text_length - chunk_size) // effective_chunk_size)
    if (text_length - chunk_size) % effective_chunk_size > 0:
        chunks += 1

    return chunks


def generate_document_hash(url: str) -> str:
    """Generate a hash for document identification."""
    return hashlib.md5(url.encode()).hexdigest()[:16]


async def check_existing_documents(documents: List[Dict]) -> Dict[str, Dict]:
    """Check which documents already exist in the database."""
    existing_docs = {}

    try:
        # Call API to check existing documents
        response = requests.post(
            f"{API_BASE}/check-existing-documents", json={"urls": [doc["link"] for doc in documents]}
        )

        if response.status_code == 200:
            existing_docs = response.json()
    except:
        # If API call fails, we'll assume no documents exist
        pass

    return existing_docs


def read_csv_files(data_dir: Path) -> List[Dict]:
    """Read all CSV files and extract document information."""
    all_documents = []

    csv_files = list(data_dir.glob("*.csv"))

    for csv_file in csv_files:
        doc_type = DOCUMENT_TYPE_MAPPING.get(csv_file.name, DocumentType.OTHER)

        try:
            with open(csv_file, "r", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)

                for idx, row in enumerate(reader):
                    # Extract the last 4 columns
                    fieldnames = reader.fieldnames
                    if len(fieldnames) >= 4:
                        last_4_columns = fieldnames[-4:]

                        doc_data = {
                            "id": f"{csv_file.name}_{idx}",
                            "csv_file": csv_file.name,
                            "title": row.get(last_4_columns[0], "").strip(),
                            "issuing_body": row.get(last_4_columns[1], "").strip(),
                            "description": row.get(last_4_columns[2], "").strip(),
                            "link": row.get(last_4_columns[3], "").strip(),
                            "document_type": doc_type,
                            "document_number": None,
                            "publication_date": None,
                            "hash": None,
                            "estimated_length": 5000,  # Default estimate
                            "is_scraped": False,
                            "last_scraped": None,
                            "scrape_status": "pending",
                        }

                        # Extract metadata
                        doc_data["document_number"] = extract_document_number(doc_data["title"], doc_type)
                        doc_data["publication_date"] = extract_publication_date(doc_data["title"])
                        doc_data["hash"] = generate_document_hash(doc_data["link"])

                        if doc_data["title"] and doc_data["link"]:
                            all_documents.append(doc_data)

        except Exception as e:
            st.error(f"Error reading {csv_file.name}: {e}")

    return all_documents


def scrape_selected_documents(
    selected_docs: List[Dict], chunk_size: int, chunk_overlap: int, force_rescrape: bool = False
):
    """Scrape selected documents with progress tracking."""
    progress_bar = st.progress(0)
    status_text = st.empty()
    results_container = st.container()

    total_docs = len(selected_docs)
    successful = 0
    failed = 0

    for idx, doc in enumerate(selected_docs):
        progress = (idx + 1) / total_docs
        progress_bar.progress(progress)
        status_text.text(f"Scraping {idx + 1}/{total_docs}: {doc['title'][:50]}...")

        try:
            # Call the scraping API endpoint
            response = requests.post(
                f"{API_BASE}/scrape-document",
                json={
                    "url": doc["link"],
                    "document_type": doc["document_type"],
                    "title": doc["title"],
                    "issuing_body": doc["issuing_body"],
                    "description": doc["description"],
                    "document_number": doc["document_number"],
                    "publication_date": doc["publication_date"],
                    "chunk_size": chunk_size,
                    "chunk_overlap": chunk_overlap,
                    "force_rescrape": force_rescrape,
                    "use_article_chunking": st.session_state.use_article_chunking,
                    "metadata": {
                        "csv_file": doc["csv_file"],
                        "manual_ingestion": True,
                        "ingestion_timestamp": datetime.now().isoformat(),
                    },
                },
                timeout=60,
            )

            if response.status_code == 200:
                result = response.json()
                successful += 1
                with results_container:
                    status = result.get("status", "success")
                    chunks_created = result.get("chunks_created", 0)
                    chunks_deleted = result.get("chunks_deleted", 0)
                    chunking_method = result.get("chunking_method", "unknown")
                    article_stats = result.get("article_stats", {})

                    # Build status message
                    status_msg = f"✅ {doc['title'][:50]}..."

                    if status == "re_scraped":
                        status_msg += f" - Re-scraped: {chunks_deleted} old → {chunks_created} new chunks"
                    elif status == "already_exists":
                        st.info(f"ℹ️ {doc['title'][:50]}... - Already exists, skipped")
                        continue
                    else:
                        status_msg += f" - {chunks_created} chunks created"

                    # Add chunking method info
                    if chunking_method == "article_based":
                        articles_found = article_stats.get("unique_articles_found", 0)
                        status_msg += f" 📄 ({articles_found} articles detected)"
                    else:
                        status_msg += " 📝 (character-based)"

                    st.success(status_msg)

                    # Show detailed stats in expander
                    if article_stats and article_stats.get("article_based_chunks", 0) > 0:
                        with st.expander(f"📊 Chunking details"):
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Articles Found", article_stats.get("unique_articles_found", 0))
                            with col2:
                                st.metric("Article Chunks", article_stats.get("article_based_chunks", 0))
                            with col3:
                                st.metric(
                                    "Other Chunks",
                                    article_stats.get("preamble_chunks", 0) + article_stats.get("other_chunks", 0),
                                )

                            # Show sample articles
                            if article_stats.get("articles_list"):
                                st.caption("Sample articles: " + ", ".join(article_stats["articles_list"][:5]))
            else:
                failed += 1
                with results_container:
                    st.error(f"❌ {doc['title'][:50]}... - Error: {response.status_code}")
                    if response.status_code != 200:
                        try:
                            error_detail = response.json().get("detail", "Unknown error")
                            with results_container:
                                st.error(f"Details: {error_detail}")
                        except:
                            pass

        except Exception as e:
            failed += 1
            with results_container:
                st.error(f"❌ {doc['title'][:50]}... - Error: {str(e)}")

        # Add delay to be respectful
        time.sleep(1)

    progress_bar.empty()
    status_text.empty()

    return successful, failed


def fetch_analytics_data():
    """Fetch all analytics data from the API endpoints."""
    analytics = {
        "type_stats": None,
        "chunk_anomalies": None,
        "rescrape_candidates": None,
        "last_updated": datetime.now(),
    }

    try:
        # Fetch document statistics by type
        response = requests.get(f"{API_BASE}/document-statistics-by-type")
        if response.status_code == 200:
            analytics["type_stats"] = response.json().get("statistics_by_type", [])
    except Exception as e:
        st.error(f"Error fetching type statistics: {e}")

    try:
        # Fetch chunk anomalies
        response = requests.get(f"{API_BASE}/chunk-anomalies")
        if response.status_code == 200:
            analytics["chunk_anomalies"] = response.json().get("anomalous_documents", [])
    except Exception as e:
        st.error(f"Error fetching chunk anomalies: {e}")

    try:
        # Fetch re-scrape candidates
        response = requests.get(f"{API_BASE}/rescrape-candidates?days_old=30")
        if response.status_code == 200:
            analytics["rescrape_candidates"] = response.json().get("rescrape_candidates", [])
    except Exception as e:
        st.error(f"Error fetching rescrape candidates: {e}")

    return analytics


def render_type_statistics_card(type_stats):
    """Render document type statistics card."""
    if not type_stats:
        st.warning("No type statistics available")
        return

    st.markdown('<div class="analytics-card">', unsafe_allow_html=True)
    st.markdown('<div class="analytics-header">📊 Document Type Distribution</div>', unsafe_allow_html=True)

    # Show top 5 document types
    top_types = type_stats[:5]

    for stat in top_types:
        doc_type = stat.get("document_type", "Unknown")
        doc_count = stat.get("document_count", 0)
        avg_chunks = stat.get("avg_chunks_per_doc", 0)
        avg_size = stat.get("avg_text_size_per_doc", 0)

        col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
        with col1:
            st.markdown(f"**{doc_type}**")
        with col2:
            st.metric("Docs", f"{doc_count:,}")
        with col3:
            st.metric("Avg Chunks", f"{avg_chunks:.1f}")
        with col4:
            st.metric("Avg Size", f"{avg_size:,.0f}")

    st.markdown("</div>", unsafe_allow_html=True)


def render_quality_issues_card(chunk_anomalies):
    """Render quality issues card."""
    st.markdown('<div class="analytics-card">', unsafe_allow_html=True)
    st.markdown('<div class="analytics-header">⚠️ Quality Issues</div>', unsafe_allow_html=True)

    if not chunk_anomalies:
        st.markdown('<div class="success-card metric-card">✅ No quality issues detected</div>', unsafe_allow_html=True)
    else:
        # Group by anomaly type
        anomaly_counts = {}
        for doc in chunk_anomalies:
            reason = doc.get("anomaly_reasons", "unknown")
            anomaly_counts[reason] = anomaly_counts.get(reason, 0) + 1

        # Display summary
        st.markdown(
            f'<div class="warning-card metric-card">Found {len(chunk_anomalies)} documents with issues</div>',
            unsafe_allow_html=True,
        )

        # Show breakdown by issue type
        for reason, count in anomaly_counts.items():
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                reason_display = reason.replace("_", " ").title()
                st.write(f"• {reason_display}")
            with col2:
                st.metric("Count", count)
            with col3:
                if st.button(f"Select", key=f"select_anomaly_{reason}"):
                    # Select documents with this anomaly type
                    for doc in chunk_anomalies:
                        if doc.get("anomaly_reasons") == reason:
                            # Find matching document in session state by URL
                            for session_doc in st.session_state.documents_data:
                                if session_doc["link"] == doc.get("url"):
                                    st.session_state.selected_documents.add(session_doc["id"])
                    st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


def render_maintenance_card(rescrape_candidates):
    """Render maintenance recommendations card."""
    st.markdown('<div class="analytics-card">', unsafe_allow_html=True)
    st.markdown('<div class="analytics-header">🔧 Maintenance Recommendations</div>', unsafe_allow_html=True)

    if not rescrape_candidates:
        st.markdown('<div class="success-card metric-card">✅ No maintenance needed</div>', unsafe_allow_html=True)
    else:
        # Group by age buckets
        age_buckets = {"0-7 days": 0, "8-30 days": 0, "31-90 days": 0, "90+ days": 0}

        for doc in rescrape_candidates:
            days_old = doc.get("days_old", 0)
            if days_old <= 7:
                age_buckets["0-7 days"] += 1
            elif days_old <= 30:
                age_buckets["8-30 days"] += 1
            elif days_old <= 90:
                age_buckets["31-90 days"] += 1
            else:
                age_buckets["90+ days"] += 1

        st.markdown(
            f'<div class="warning-card metric-card">Found {len(rescrape_candidates)} documents needing attention</div>',
            unsafe_allow_html=True,
        )

        # Show age distribution
        for bucket, count in age_buckets.items():
            if count > 0:
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.write(f"• {bucket} old")
                with col2:
                    st.metric("Count", count)
                with col3:
                    if st.button(f"Select", key=f"select_rescrape_{bucket}"):
                        # Select documents in this age bucket
                        for doc in rescrape_candidates:
                            days_old = doc.get("days_old", 0)
                            if (
                                (bucket == "0-7 days" and days_old <= 7)
                                or (bucket == "8-30 days" and 8 <= days_old <= 30)
                                or (bucket == "31-90 days" and 31 <= days_old <= 90)
                                or (bucket == "90+ days" and days_old > 90)
                            ):
                                # Find matching document in session state by URL
                                for session_doc in st.session_state.documents_data:
                                    if session_doc["link"] == doc.get("url"):
                                        st.session_state.selected_documents.add(session_doc["id"])
                        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


def render_chunking_methods_card():
    """Render chunking methods distribution card."""
    st.markdown('<div class="analytics-card">', unsafe_allow_html=True)
    st.markdown('<div class="analytics-header">🔄 Chunking Methods Used</div>', unsafe_allow_html=True)

    try:
        # Query to get chunking method distribution
        response = requests.get(f"{API_BASE}/chunking-method-stats")
        if response.status_code == 200:
            stats = response.json().get("chunking_stats", {})

            total = sum(stats.values())
            if total > 0:
                for method, count in stats.items():
                    percentage = (count / total) * 100
                    col1, col2, col3 = st.columns([2, 1, 1])
                    with col1:
                        method_display = "Article-based" if method == "articles" else method.replace("_", " ").title()
                        st.write(f"• {method_display}")
                    with col2:
                        st.metric("Count", f"{count:,}")
                    with col3:
                        st.metric("Percent", f"{percentage:.1f}%")
            else:
                st.info("No chunking data available yet")
        else:
            st.warning("Could not load chunking statistics")
    except Exception as e:
        st.error(f"Error loading chunking stats: {e}")

    st.markdown("</div>", unsafe_allow_html=True)


def main():
    st.title("📊 Data Ingestion Control Panel")

    # Sidebar for parameters
    with st.sidebar:
        st.header("⚙️ Embedding Parameters")

        chunk_size = st.number_input(
            "Chunk Size",
            min_value=100,
            max_value=5000,
            value=st.session_state.chunk_size,
            step=100,
            help="Size of text chunks for embeddings",
        )

        chunk_overlap = st.number_input(
            "Chunk Overlap",
            min_value=0,
            max_value=1000,
            value=st.session_state.chunk_overlap,
            step=50,
            help="Overlap between consecutive chunks",
        )
        st.divider()
        st.header("📄 Chunking Method")

        use_article_chunking = st.checkbox(
            "Use Article-based Chunking",
            value=st.session_state.use_article_chunking,
            help="""
            **Article-based chunking**: 
            - Preserves article boundaries
            - Groups small articles together
            - Better semantic coherence
            - Recommended for legal documents
            
            **Character-based chunking**:
            - Fixed size chunks
            - May split articles
            - Use for non-structured text
            """,
        )

        st.session_state.use_article_chunking = use_article_chunking

        if use_article_chunking:
            st.info("🎯 Article chunking will preserve the natural structure of legal documents")
        else:
            st.warning("⚠️ Character chunking may split articles mid-content")

        # Update session state
        st.session_state.chunk_size = chunk_size
        st.session_state.chunk_overlap = chunk_overlap

        st.divider()

        # Selection controls
        st.header("🎯 Selection Controls")

        if st.button("Select All Pending"):
            for doc in st.session_state.documents_data:
                if doc["scrape_status"] == "pending":
                    st.session_state.selected_documents.add(doc["id"])
            st.rerun()

        if st.button("Clear Selection"):
            st.session_state.selected_documents.clear()
            st.rerun()

        max_docs = st.number_input(
            "Max Documents to Select",
            min_value=1,
            max_value=1000,
            value=50,
            help="Maximum number of documents to select at once",
        )

        if st.button(f"Select First {max_docs} Pending"):
            count = 0
            for doc in st.session_state.documents_data:
                if doc["scrape_status"] == "pending" and count < max_docs:
                    st.session_state.selected_documents.add(doc["id"])
                    count += 1
            st.rerun()

        st.divider()

        # Re-scraping options
        st.header("🔄 Re-scraping Options")

        force_rescrape = st.checkbox(
            "Force Re-scrape",
            help="Re-scrape documents even if they already exist. This will delete old chunks and create new ones with current parameters.",
        )

        if force_rescrape:
            st.warning("⚠️ This will delete existing chunks and re-create them with new parameters!")

        # Store in session state
        st.session_state.force_rescrape = force_rescrape

    # Main content area
    data_dir = Path("data/legislationPT")

    if not data_dir.exists():
        st.error(f"Data directory not found: {data_dir}")
        st.info("Please ensure the CSV files are placed in data/legislationPT/")
        return

    # Load documents
    if st.button("🔄 Load/Refresh Document List"):
        with st.spinner("Loading documents from CSV files..."):
            documents = read_csv_files(data_dir)

            # Check which documents already exist in the database
            with st.spinner("Checking existing documents in database..."):
                try:
                    # Make the API call to check existing documents
                    response = requests.post(
                        f"{API_BASE}/check-existing-documents", json={"urls": [doc["link"] for doc in documents]}
                    )

                    if response.status_code == 200:
                        existing_docs = response.json()

                        # Update document statuses based on database check
                        for doc in documents:
                            if doc["link"] in existing_docs:
                                doc_info = existing_docs[doc["link"]]
                                doc["is_scraped"] = True
                                doc["scrape_status"] = "scraped"
                                doc["last_scraped"] = doc_info.get("last_updated", "Unknown")

                                # Store actual chunk information
                                doc["actual_chunks"] = doc_info.get("chunks_count", 0)
                                doc["actual_text_length"] = doc_info.get("total_text_length", 0)
                                doc["avg_chunk_size"] = doc_info.get("avg_chunk_size", 0)

                                # Update estimated length with actual if available
                                if doc_info.get("total_text_length", 0) > 0:
                                    doc["estimated_length"] = doc_info["total_text_length"]

                        st.success(f"Loaded {len(documents)} documents from CSV files")
                        st.info(f"Found {len(existing_docs)} documents already in database")

                        # Show some statistics
                        total_chunks = sum(doc.get("actual_chunks", 0) for doc in documents if doc["is_scraped"])
                        total_text = sum(doc.get("actual_text_length", 0) for doc in documents if doc["is_scraped"])

                        if total_chunks > 0:
                            avg_chunk_size = total_text // total_chunks if total_chunks > 0 else 0
                            col1, col2 = st.columns(2)
                            with col1:
                                st.metric("Total Existing Chunks", f"{total_chunks:,}")
                            with col2:
                                st.metric("Average Chunk Size", f"{avg_chunk_size:,} chars")

                    else:
                        st.warning("Could not check existing documents in database")
                        st.success(f"Loaded {len(documents)} documents from CSV files")

                except Exception as e:
                    st.error(f"Error checking database: {str(e)}")
                    st.success(f"Loaded {len(documents)} documents from CSV files (database check failed)")

            st.session_state.documents_data = documents

    if not st.session_state.documents_data:
        st.info("Click 'Load/Refresh Document List' to start")
        return

    # Add database sync status summary
    scraped_count = sum(1 for doc in st.session_state.documents_data if doc["is_scraped"])
    pending_count = len(st.session_state.documents_data) - scraped_count

    st.info(
        f"""
    **Database Sync Status:**
    - ✅ Already in database: {scraped_count}
    - ⏳ Not yet scraped: {pending_count}
    - 📊 Total documents: {len(st.session_state.documents_data)}
    """
    )

    # Add refresh button to re-check database status without reloading CSVs
    if st.button("🔄 Refresh Database Status", help="Check database again without reloading CSV files"):
        if st.session_state.documents_data:
            with st.spinner("Checking database status..."):
                try:
                    response = requests.post(
                        f"{API_BASE}/check-existing-documents",
                        json={"urls": [doc["link"] for doc in st.session_state.documents_data]},
                    )

                    if response.status_code == 200:
                        existing_docs = response.json()

                        # Update statuses
                        updated_count = 0
                        for doc in st.session_state.documents_data:
                            if doc["link"] in existing_docs and not doc["is_scraped"]:
                                doc_info = existing_docs[doc["link"]]
                                doc["is_scraped"] = True
                                doc["scrape_status"] = "scraped"
                                doc["last_scraped"] = doc_info.get("last_updated", "Unknown")
                                doc["actual_chunks"] = doc_info.get("chunks_count", 0)
                                updated_count += 1

                        st.success(f"Updated status for {updated_count} documents")
                        st.rerun()
                    else:
                        st.error(f"Failed to check database: HTTP {response.status_code}")
                except Exception as e:
                    st.error(f"Error checking database: {str(e)}")

    # Display statistics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Documents", len(st.session_state.documents_data))

    with col2:
        selected_count = len(st.session_state.selected_documents)
        st.metric("Selected", selected_count)

    with col3:
        scraped_count = sum(1 for doc in st.session_state.documents_data if doc["is_scraped"])
        st.metric("Already Scraped", scraped_count)

    with col4:
        # Calculate chunks more accurately
        total_chunks = 0
        for doc in st.session_state.documents_data:
            if doc["id"] in st.session_state.selected_documents:
                if doc["is_scraped"] and "actual_chunks" in doc:
                    # Use actual chunks for already scraped docs
                    total_chunks += doc["actual_chunks"]
                else:
                    # Use estimate for unscraped docs
                    total_chunks += estimate_chunks(doc["estimated_length"], chunk_size, chunk_overlap)

        st.metric("Total Chunks", f"{total_chunks:,}")

    # Advanced Analytics Section
    st.divider()

    # Analytics header with toggle
    col1, col2 = st.columns([3, 1])
    with col1:
        st.header("🔍 Advanced Analytics")
    with col2:
        if st.button("🔄 Refresh Analytics", help="Fetch latest analytics data"):
            with st.spinner("Fetching analytics data..."):
                st.session_state.analytics_data = fetch_analytics_data()
                st.session_state.show_analytics = True
            st.rerun()

    # Show/hide analytics toggle
    if st.checkbox("Show Advanced Analytics", value=st.session_state.show_analytics):
        st.session_state.show_analytics = True

        # Fetch analytics data if not available
        if (
            st.session_state.analytics_data["type_stats"] is None
            or st.session_state.analytics_data["chunk_anomalies"] is None
            or st.session_state.analytics_data["rescrape_candidates"] is None
        ):
            with st.spinner("Loading analytics data..."):
                st.session_state.analytics_data = fetch_analytics_data()

        # Display analytics cards in columns
        col1, col2 = st.columns(2)

        with col1:
            # Document Type Statistics
            render_type_statistics_card(st.session_state.analytics_data["type_stats"])

            # Quality Issues
            render_quality_issues_card(st.session_state.analytics_data["chunk_anomalies"])

        with col2:
            # Maintenance Recommendations
            render_maintenance_card(st.session_state.analytics_data["rescrape_candidates"])

            # Analytics summary
            st.markdown('<div class="analytics-card">', unsafe_allow_html=True)
            st.markdown('<div class="analytics-header">📈 Quick Summary</div>', unsafe_allow_html=True)

            if st.session_state.analytics_data["last_updated"]:
                st.caption(
                    f"Last updated: {st.session_state.analytics_data['last_updated'].strftime('%Y-%m-%d %H:%M:%S')}"
                )

            # Summary metrics
            type_count = len(st.session_state.analytics_data["type_stats"] or [])
            anomaly_count = len(st.session_state.analytics_data["chunk_anomalies"] or [])
            rescrape_count = len(st.session_state.analytics_data["rescrape_candidates"] or [])

            st.metric("Document Types", type_count)
            st.metric("Quality Issues", anomaly_count)
            st.metric("Maintenance Items", rescrape_count)

            st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.session_state.show_analytics = False

    # Scraping controls
    st.divider()

    col1, col2 = st.columns([3, 1])

    with col1:
        if st.session_state.selected_documents:
            st.info(
                f"Ready to scrape {len(st.session_state.selected_documents)} documents with {total_chunks} estimated chunks"
            )

    with col2:
        if st.button("🚀 Start Scraping", type="primary", disabled=not st.session_state.selected_documents):
            st.session_state.scraping_in_progress = True

    # Document preview with filters
    st.divider()
    st.header("📄 Document Preview")

    # Filters
    col1, col2, col3 = st.columns(3)

    with col1:
        filter_csv = st.selectbox(
            "Filter by CSV File", ["All"] + list(set(doc["csv_file"] for doc in st.session_state.documents_data))
        )

    with col2:
        filter_type = st.selectbox(
            "Filter by Document Type",
            ["All"] + list(set(doc["document_type"] for doc in st.session_state.documents_data)),
        )

    with col3:
        filter_status = st.selectbox("Filter by Status", ["All", "Pending", "Scraped", "Failed"])

    # Apply filters
    filtered_docs = st.session_state.documents_data

    if filter_csv != "All":
        filtered_docs = [doc for doc in filtered_docs if doc["csv_file"] == filter_csv]

    if filter_type != "All":
        filtered_docs = [doc for doc in filtered_docs if doc["document_type"] == filter_type]

    if filter_status != "All":
        if filter_status == "Pending":
            filtered_docs = [doc for doc in filtered_docs if doc["scrape_status"] == "pending"]
        elif filter_status == "Scraped":
            filtered_docs = [doc for doc in filtered_docs if doc["is_scraped"]]
        elif filter_status == "Failed":
            filtered_docs = [doc for doc in filtered_docs if doc["scrape_status"] == "failed"]

    # Display documents in a scrollable container
    st.markdown(f"Showing {len(filtered_docs)} documents")

    # Create a container for documents
    doc_container = st.container()

    with doc_container:
        for doc in filtered_docs[:100]:  # Limit display to 100 for performance
            col1, col2, col3, col4 = st.columns([0.5, 3, 2, 1])

            with col1:
                # Checkbox for selection
                is_selected = st.checkbox(
                    f"Select document {doc['id']}",
                    key=f"select_{doc['id']}",
                    value=doc["id"] in st.session_state.selected_documents,
                    label_visibility="hidden",
                )

                if is_selected and doc["id"] not in st.session_state.selected_documents:
                    st.session_state.selected_documents.add(doc["id"])
                elif not is_selected and doc["id"] in st.session_state.selected_documents:
                    st.session_state.selected_documents.remove(doc["id"])

            with col2:
                # Document info
                st.markdown(f"**{doc['title'][:80]}...**")
                st.caption(f"{doc['issuing_body']} | {doc['document_type']}")

                # Show chunk information
                if doc["is_scraped"] and "actual_chunks" in doc:
                    # Show actual chunks and text length
                    st.caption(
                        f"📊 Chunks: {doc['actual_chunks']} | " f"📝 Length: {doc.get('actual_text_length', 0):,} chars"
                    )
                else:
                    # Show estimated chunks for unscraped documents
                    est_chunks = estimate_chunks(doc["estimated_length"], chunk_size, chunk_overlap)
                    st.caption(
                        f"📊 Est. chunks: ~{est_chunks} | " f"📝 Est. length: ~{doc['estimated_length']:,} chars"
                    )

            with col3:
                # Status and metadata
                if doc["is_scraped"]:
                    st.markdown('<span class="scraped-indicator">✅ Scraped</span>', unsafe_allow_html=True)
                    if doc["last_scraped"]:
                        try:
                            last_scraped = datetime.fromisoformat(doc["last_scraped"].replace("Z", "+00:00"))
                            formatted_date = last_scraped.strftime("%Y-%m-%d %H:%M")
                            st.caption(f"Last: {formatted_date}")
                        except:
                            st.caption(f"Last: {doc['last_scraped']}")

                    # Show average chunk size if available
                    if doc.get("avg_chunk_size"):
                        st.caption(f"Avg chunk: {doc['avg_chunk_size']:,} chars")
                else:
                    st.markdown('<span class="pending-indicator">⏳ Pending</span>', unsafe_allow_html=True)

                if doc["document_number"]:
                    st.caption(f"№ {doc['document_number']}")

            with col4:
                # Actions
                if st.button("🔗", key=f"link_{doc['id']}", help="Open document link"):
                    st.markdown(f"[Open Link]({doc['link']})")

            st.divider()

    # Scraping execution
    if st.session_state.scraping_in_progress:
        st.header("🔄 Scraping Progress")

        selected_docs = [
            doc for doc in st.session_state.documents_data if doc["id"] in st.session_state.selected_documents
        ]

        if selected_docs:
            # Run scraping (now synchronous)
            successful, failed = scrape_selected_documents(
                selected_docs, chunk_size, chunk_overlap, st.session_state.get("force_rescrape", False)
            )

            st.success(f"✅ Scraping completed! Successful: {successful}, Failed: {failed}")

            # Clear selection and reset state
            st.session_state.selected_documents.clear()
            st.session_state.scraping_in_progress = False

            # Refresh button
            if st.button("🔄 Refresh Document List"):
                st.rerun()
        else:
            st.error("No documents selected for scraping!")
            st.session_state.scraping_in_progress = False


if __name__ == "__main__":
    main()
