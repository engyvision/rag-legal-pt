# Scripts Directory

This directory contains the core scripts for the Portuguese Legal Assistant RAG system.

## Production Scripts

### Data Management
- **`setup_mongodb.py`** - Initialize MongoDB collections and indexes
- **`scrape_legislation.py`** - Main scraper for Portuguese legal documents from CSV data
- **`init_data.py`** - Initialize sample data for testing

### Testing & Verification
- **`verify_setup.py`** - Verify system setup and connections
- **`test_vector_search.py`** - Test vector search functionality

### Deployment
- **`deploy.sh`** - Deploy to Google Cloud Run

## Usage

### Initial Setup
```bash
# 1. Setup MongoDB
python scripts/setup_mongodb.py

# 2. Verify connections
python scripts/verify_setup.py
```

### Data Population
```bash
# Option 1: Real legal documents (production)
# RECOMMENDED: Use the Data Ingestion Control UI in the web interface
# Navigate to http://localhost:8501 and click "Data Ingestion Control" in sidebar

# Alternative: Command line scraping (for automation)
python scripts/scrape_legislation.py

# Option 2: Sample data (testing)
python scripts/init_data.py
```

### Testing
```bash
# Test vector search
python scripts/test_vector_search.py
```

## Legal Document Scraper Details

### Web UI Approach (Recommended)

For a more user-friendly approach, use the **Data Ingestion Control UI** in the web interface:

- **Access**: Navigate to http://localhost:8501 → "Data Ingestion Control"
- **Features**: 
  - Browse and select specific documents before scraping
  - Configure embedding parameters with real-time estimates
  - Monitor progress with success/failure tracking
  - Filter by document type, CSV file, or status
  - Automatic duplicate prevention
- **Benefits**: Better control, visibility, and error handling than command-line

### Command Line Approach

The `scrape_legislation.py` script (still available for automation):

1. **Reads CSV files** from `data/legislationPT/` (Lei.csv, Decreto-Lei.csv, etc.)
2. **Extracts metadata** (title, document number, publication date, issuing body)
3. **Scrapes full legal text** from diariodarepublica.pt using Playwright
4. **Stores in MongoDB** with embeddings for vector search
5. **Only stores real content** - documents that can't be scraped are skipped

**Requirements:**
- Playwright browser dependencies (installed via `playwright install chromium`)
- Active internet connection
- Valid MongoDB Atlas connection
- Google Vertex AI credentials

**Output:**
- Real Portuguese legal documents in MongoDB
- Generated embeddings for semantic search
- Ready for RAG queries via the frontend