# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Portuguese Legal Assistant built with a RAG (Retrieval-Augmented Generation) architecture. The system scrapes Portuguese legal documents, processes them with embeddings, and provides a natural language interface for legal queries.

## Architecture

The project follows a microservices architecture with three main services:

1. **Retrieval Service** (`src/retrieval_service/`): FastAPI backend that handles document retrieval, embeddings, and LLM integration
2. **Frontend Service** (`src/frontend_service/`): Streamlit web interface for user interactions
3. **Scrapers** (`src/scrapers/`): Web scrapers for legal documents from diariodarepublica.pt

**Data Flow**: Legal documents → Scrapers → Cloud Storage → Processing → Embeddings → MongoDB Atlas → Vector Search → LLM Response

## Technology Stack

- **Backend**: FastAPI, Python 3.11+
- **Frontend**: Streamlit
- **Database**: MongoDB Atlas (with vector search)
- **AI/ML**: Google Vertex AI (gemini-embedding-001, gemini-1.5-pro-001)
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
# Initialize sample data
python scripts/init_data.py

# Setup MongoDB collections and indexes
python scripts/setup_mongodb.py

# Run scrapers
docker-compose run --rm scraper
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

## Important Setup Notes

1. **MongoDB Atlas Vector Search**: Must manually create vector index via Atlas UI after running `setup_mongodb.py`
2. **Google Cloud Auth**: Requires service account with AI Platform and Storage permissions
3. **Dependencies**: Services depend on each other - retrieval service must be running before frontend
4. **Vector Index**: Name must be exactly `vector_index` with 3072 dimensions, cosine similarity

## Common Workflows

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

### Adding New Document Types
1. Update schemas in `scripts/setup_mongodb.py`
2. Modify scrapers in `src/scrapers/`
3. Update document processing in `retrieval_service/services/`
4. Add tests for new document types