"""Data Ingestion Control UI for Portuguese Legal Assistant."""

import streamlit as st
import pandas as pd
import requests
import os
import csv
import re
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json

# Add parent directory to path for imports
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from src.common.models import DocumentType, DocumentSource
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
st.markdown("""
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
</style>
""", unsafe_allow_html=True)

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


def extract_document_number(title: str, doc_type: DocumentType) -> Optional[str]:
    """Extract document number from title."""
    patterns = {
        DocumentType.LEI: r"Lei n\.º (\d+/\d+)",
        DocumentType.DECRETO_LEI: r"Decreto-Lei n\.º (\d+/\d+)",
        DocumentType.DECRETO: r"Decreto n\.º (\d+/\d+)",
        DocumentType.PORTARIA: r"Portaria n\.º (\d+/\d+)"
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
            f"{API_BASE}/check-existing-documents",
            json={"urls": [doc["link"] for doc in documents]}
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
            with open(csv_file, 'r', encoding='utf-8') as csvfile:
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
                            "scrape_status": "pending"
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


async def scrape_selected_documents(selected_docs: List[Dict], chunk_size: int, chunk_overlap: int):
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
                    "metadata": {
                        "csv_file": doc["csv_file"],
                        "manual_ingestion": True,
                        "ingestion_timestamp": datetime.now().isoformat()
                    }
                },
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                successful += 1
                with results_container:
                    st.success(f"✅ {doc['title'][:50]}... - {result.get('chunks_created', 0)} chunks created")
            else:
                failed += 1
                with results_container:
                    st.error(f"❌ {doc['title'][:50]}... - Error: {response.status_code}")
                    
        except Exception as e:
            failed += 1
            with results_container:
                st.error(f"❌ {doc['title'][:50]}... - Error: {str(e)}")
        
        # Add delay to be respectful
        await asyncio.sleep(1)
    
    progress_bar.empty()
    status_text.empty()
    
    return successful, failed


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
            help="Size of text chunks for embeddings"
        )
        
        chunk_overlap = st.number_input(
            "Chunk Overlap",
            min_value=0,
            max_value=1000,
            value=st.session_state.chunk_overlap,
            step=50,
            help="Overlap between consecutive chunks"
        )
        
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
            help="Maximum number of documents to select at once"
        )
        
        if st.button(f"Select First {max_docs} Pending"):
            count = 0
            for doc in st.session_state.documents_data:
                if doc["scrape_status"] == "pending" and count < max_docs:
                    st.session_state.selected_documents.add(doc["id"])
                    count += 1
            st.rerun()
    
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
            st.session_state.documents_data = documents
            
            # Check existing documents
            # Note: This would require implementing the check-existing-documents endpoint
            # For now, we'll simulate this
            st.success(f"Loaded {len(documents)} documents from CSV files")
    
    if not st.session_state.documents_data:
        st.info("Click 'Load/Refresh Document List' to start")
        return
    
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
        # Estimate total chunks for selected documents
        total_chunks = sum(
            estimate_chunks(doc["estimated_length"], chunk_size, chunk_overlap)
            for doc in st.session_state.documents_data
            if doc["id"] in st.session_state.selected_documents
        )
        st.metric("Estimated Chunks", total_chunks)
    
    # Scraping controls
    st.divider()
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        if st.session_state.selected_documents:
            st.info(f"Ready to scrape {len(st.session_state.selected_documents)} documents with {total_chunks} estimated chunks")
    
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
            "Filter by CSV File",
            ["All"] + list(set(doc["csv_file"] for doc in st.session_state.documents_data))
        )
    
    with col2:
        filter_type = st.selectbox(
            "Filter by Document Type",
            ["All"] + list(set(doc["document_type"] for doc in st.session_state.documents_data))
        )
    
    with col3:
        filter_status = st.selectbox(
            "Filter by Status",
            ["All", "Pending", "Scraped", "Failed"]
        )
    
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
                    label_visibility="hidden"
                )
                
                if is_selected and doc["id"] not in st.session_state.selected_documents:
                    st.session_state.selected_documents.add(doc["id"])
                elif not is_selected and doc["id"] in st.session_state.selected_documents:
                    st.session_state.selected_documents.remove(doc["id"])
            
            with col2:
                # Document info
                st.markdown(f"**{doc['title'][:80]}...**")
                st.caption(f"{doc['issuing_body']} | {doc['document_type']}")
                
                # Estimated chunks for this document
                est_chunks = estimate_chunks(doc["estimated_length"], chunk_size, chunk_overlap)
                st.caption(f"📊 Estimated chunks: {est_chunks}")
            
            with col3:
                # Status and metadata
                if doc["is_scraped"]:
                    st.markdown('<span class="scraped-indicator">✅ Scraped</span>', unsafe_allow_html=True)
                    if doc["last_scraped"]:
                        st.caption(f"Last: {doc['last_scraped']}")
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
            doc for doc in st.session_state.documents_data
            if doc["id"] in st.session_state.selected_documents
        ]
        
        if selected_docs:
            # Run scraping
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            successful, failed = loop.run_until_complete(
                scrape_selected_documents(selected_docs, chunk_size, chunk_overlap)
            )
            
            st.success(f"✅ Scraping completed! Successful: {successful}, Failed: {failed}")
            
            # Clear selection and reset state
            st.session_state.selected_documents.clear()
            st.session_state.scraping_in_progress = False
            
            # Refresh button
            if st.button("🔄 Refresh Document List"):
                st.rerun()


if __name__ == "__main__":
    main()