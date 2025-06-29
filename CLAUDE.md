# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Portuguese Legal Assistant built with a RAG (Retrieval-Augmented Generation) architecture. The system scrapes Portuguese legal documents, processes them with embeddings, and provides a natural language interface for legal queries.

## Architecture

The project follows a microservices architecture with three main services:

1. **Retrieval Service** (`src/retrieval_service/`): FastAPI backend that handles document retrieval, embeddings, and LLM integration
2. **Frontend Service** (`src/frontend_service/`): Streamlit web interface for user interactions
3. **Legal Document Scraper** (`scripts/scrape_legislation.py`): Scrapes Portuguese legal documents from diariodarepublica.pt using CSV metadata

**Data Flow**: CSV metadata → Web scraping (diariodarepublica.pt) → Document processing → Embeddings → MongoDB Atlas → Vector Search → LLM Response

## Technology Stack

- **Backend**: FastAPI, Python 3.11+
- **Frontend**: Streamlit
- **Database**: MongoDB Atlas (with vector search)
- **AI/ML**: Google Vertex AI (gemini-embedding-001, gemini-1.5-pro-001)
- **Web Scraping**: Playwright + Selenium (JavaScript rendering)
- **Cloud**: Google Cloud Platform (Cloud Run, Cloud Storage)
- **Containerization**: Docker with docker-compose

## Key Commands

### Development Setup
```bash
# Setup environment
cp .env.example .env
python scripts/setup_mongodb.py

# Local development with Docker
docker-compose up --build

# Run individual services
python -m src.retrieval_service.main        # API server on port 8000
streamlit run src/frontend_service/app.py   # Frontend on port 8501

# Access Data Ingestion UI
# Navigate to http://localhost:8501 and click "Data Ingestion Control" in sidebar
```

### Testing
```bash
# Run all tests
pytest tests/

# Run specific test files
pytest tests/test_retrieval.py
pytest tests/test_scrapper.py

# Test setup and connections
python scripts/verify_setup.py
python scripts/test_vector_search.py
```

### Data Management
```bash
# Setup MongoDB collections and indexes
python scripts/setup_mongodb.py

# Initialize sample data (for testing)
python scripts/init_data.py

# Scrape real Portuguese legal documents from CSV data
python scripts/scrape_legislation.py

# Verify setup and connections
python scripts/verify_setup.py

# Test vector search functionality
python scripts/test_vector_search.py
```

### Deployment
```bash
# Deploy to Google Cloud Run
chmod +x scripts/deploy.sh
./scripts/deploy.sh
```

### Code Quality
```bash
# Format code
black src/ tests/ scripts/

# Lint code
flake8 src/ tests/ scripts/
```

## Environment Variables

Required environment variables (see `.env.example`):
- `GOOGLE_CLOUD_PROJECT`: GCP project ID
- `MONGODB_URI`: MongoDB Atlas connection string
- `GOOGLE_APPLICATION_CREDENTIALS`: Path to GCP service account JSON
- `GCS_BUCKET_NAME`: Cloud Storage bucket name
- `VERTEX_AI_LOCATION`: GCP region for Vertex AI (default: us-central1)

## Key Configuration

- **Embeddings**: gemini-embedding-001 (3072 dimensions)
- **LLM**: gemini-1.5-pro-001
- **Chunk Size**: 1000 characters with 200 overlap
- **Vector Search**: MongoDB Atlas with cosine similarity
- **Database**: legal_assistant (collections: documents, vectors, queries)

## Document Schema

Documents are stored in MongoDB with the following structure:

```python
{
    # Core document fields (from the legal document itself)
    "title": "Lei n.º 23/2023 - Regime Jurídico das Sociedades Comerciais",
    "text": "Full document text content...",
    "document_type": "lei",
    "document_number": "23/2023",
    "publication_date": "2023-05-15",
    "issuing_body": "Assembleia da República",     # Root-level field
    "description": "Estabelece o regime...",       # Root-level field
    "category": "legislação_geral",                # Auto-categorized
    "keywords": ["lei", "legislação", "sociedade", "comercial", "empresa"],  # Auto-extracted
    "source": "scraper",
    "url": "https://dre.pt/exemplo/lei-23-2023",
    
    # Process/system metadata only
    "metadata": {
        "csv_file": "Lei.csv",
        "scraped_at": "2024-01-15T10:30:00",
        "raw_csv_data": {...},
        "scraping_method": "selenium",
        "processing_version": "1.0"
    },
    
    "created_at": ISODate(),
    "updated_at": ISODate()
}
```

**Key Schema Notes:**
- `issuing_body` and `description` are **root-level fields** (moved from metadata in v1.0)
- `category` is auto-assigned based on document type (legislação_geral, decretos_executivos, regulamentação_setorial)
- `keywords` are auto-extracted from title/description using legal domain terms
- `metadata` contains only process-related information, not document content
- All root-level fields have database indexes for efficient querying
- Use the migration script `temp/migrate_document_schema.py` when upgrading from older schemas

**Categories:**
- `legislação_geral`: Laws and Decree-Laws
- `decretos_executivos`: Presidential/Government Decrees  
- `regulamentação_setorial`: Sector-specific regulations (Portarias)

## Important Setup Notes

1. **MongoDB Atlas Vector Search**: Must manually create vector index via Atlas UI after running `setup_mongodb.py`
2. **Google Cloud Auth**: Requires service account with AI Platform and Storage permissions
3. **Dependencies**: Services depend on each other - retrieval service must be running before frontend
4. **Vector Index**: Name must be exactly `vector_index` with 3072 dimensions, cosine similarity

## Common Workflows

### Managing Document Ingestion

**Recommended Approach: Web UI**
1. Start both services (`docker-compose up --build`)
2. Navigate to http://localhost:8501
3. Click "Data Ingestion Control" in sidebar
4. Load documents from CSV files in `data/legislationPT/`
5. Select specific documents or batch selections
6. Configure embedding parameters (chunk size, overlap)
7. Monitor scraping progress with real-time feedback
8. View ingestion statistics and success/failure rates

**Key UI Features:**
- Selective document scraping (avoid processing unwanted documents)
- Parameter control with visual chunk estimates
- Duplicate prevention (automatically skip already-scraped documents)
- Progress monitoring with detailed error reporting
- Filter by document type, CSV file, or existing status

**Alternative: Command Line** (for automation)
```bash
python scripts/scrape_legislation.py
```

### Adding New Features
1. Implement in appropriate service directory
2. Add corresponding tests in `tests/`
3. Update configuration in `core/config.py` if needed
4. Test locally with docker-compose
5. Run linting and tests before deployment

### Debugging Vector Search
1. Check MongoDB Atlas vector index status
2. Run `python scripts/test_vector_search.py`
3. Verify embeddings are generated correctly
4. Check MongoDB logs for search errors

### Schema Migration
When upgrading from older document schemas, run these scripts in order:

#### 1. Move Fields from Metadata to Root Level
```bash
# Preview changes without applying them
python temp/migrate_document_schema.py --dry-run

# Run the migration
python temp/migrate_document_schema.py

# Verify migration completed successfully
python temp/migrate_document_schema.py --verify-only
```

#### 2. Add Category and Keywords to Existing Documents
```bash
# Preview what fields would be added
python temp/add_category_keywords.py --dry-run

# Add category and keywords to existing documents
python temp/add_category_keywords.py

# Verify all documents have the new fields
python temp/add_category_keywords.py --verify-only
```

**Migration Details:**
- **migrate_document_schema.py**: Moves `issuing_body` and `description` from `metadata` to root level
- **add_category_keywords.py**: Adds `category` (based on document type) and `keywords` (extracted from title/description)
- Both scripts are idempotent (safe to run multiple times)
- Comprehensive logging and verification
- Use `--dry-run` to preview changes before applying

### Portuguese Legal Document Scraper

The main scraper (`scripts/scrape_legislation.py`) processes Portuguese legal documents from CSV files in `data/legislationPT/`:

**Supported Document Types:**
- Lei (Laws)
- Decreto-Lei (Decree-Laws) 
- Decreto (Decrees)
- Portaria (Ordinances)

**Features:**
- Reads CSV metadata (title, issuing body, description, links)
- Scrapes full legal text from diariodarepublica.pt using Playwright
- Extracts document numbers and publication dates
- Only stores documents with real legal content (no fallback/fake content)
- Generates embeddings and stores in MongoDB with vector search

**CSV Structure:**
Each CSV file contains the last 4 columns with:
- Document title with number and date
- Issuing body/ministry
- Document description
- Link to full document on diariodarepublica.pt

### Adding New Document Types
1. Add new CSV file to `data/legislationPT/` with same column structure
2. Update `DOCUMENT_TYPE_MAPPING` in `scripts/scrape_legislation.py`
3. Add corresponding `DocumentType` enum in `src/common/models.py`
4. Update column mappings in `CSV_COLUMN_MAPPING` if needed
5. Test with new document type