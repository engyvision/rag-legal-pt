# Portuguese Legal Assistant RAG

rag-legal-pt/
├── .devcontainer/
│ ├── Dockerfile
│ └── devcontainer.json
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
├── docker-compose.yml
├── src/
│ ├── **init**.py
│ ├── frontend_service/
│ │ ├── **init**.py
│ │ ├── Dockerfile
│ │ ├── app.py
│ │ ├── pages/
│ │ │ ├── **init**.py
│ │ │ ├── query.py
│ │ │ └── upload.py
│ │ └── requirements.txt
│ ├── retrieval_service/
│ │ ├── **init**.py
│ │ ├── Dockerfile
│ │ ├── main.py
│ │ ├── api/
│ │ │ ├── **init**.py
│ │ │ ├── routes.py
│ │ │ └── models.py
│ │ ├── core/
│ │ │ ├── **init**.py
│ │ │ ├── config.py
│ │ │ ├── embeddings.py
│ │ │ ├── mongodb.py
│ │ │ └── llm.py
│ │ ├── services/
│ │ │ ├── **init**.py
│ │ │ ├── retrieval.py
│ │ │ └── processing.py
│ │ └── requirements.txt
│ ├── scrapers/
│ │ ├── **init**.py
│ │ ├── Dockerfile
│ │ ├── main.py
│ │ ├── diario_republica.py
│ │ └── requirements.txt
│ └── common/
│ ├── **init**.py
│ ├── models.py
│ └── utils.py
├── scripts/
│ ├── setup_mongodb.py
│ ├── init_data.py
│ └── deploy.sh
└── tests/
├── **init**.py
├── test_retrieval.py
└── test_scraper.py

# Portuguese Legal Assistant RAG Architecture

## Overview

A Retrieval-Augmented Generation (RAG) system for Portuguese law that enables users to ask questions in natural language and retrieve relevant legal information. Built using Google Cloud Platform services integrated with MongoDB Atlas for vector storage and search.

## Architecture Components

### 1. Data Ingestion Pipeline

- **Web Scraper Service** (Cloud Run)
  - Scrapes legal documents from diariodarepublica.pt
  - Extracts and processes Portuguese legal texts
  - Stores raw documents in Cloud Storage

### 2. Data Processing Pipeline

- **Document Processor** (Cloud Run)
  - Reads raw documents from Cloud Storage
  - Chunks documents into semantic segments
  - Generates embeddings using Vertex AI text-embedding models
  - Stores processed documents and vectors in MongoDB Atlas

### 3. Storage Layer

- **Cloud Storage**: Raw legal documents and user uploads
- **MongoDB Atlas**:
  - Document storage with metadata
  - Vector embeddings with Atlas Vector Search
  - Search indices for hybrid search (keyword + semantic)

### 4. Application Services

- **Frontend Service** (Cloud Run)
  - Python/Streamlit web interface
  - Natural language query input
  - **Data Ingestion Control Panel** - Web-based UI for managing document scraping
  - Document upload functionality (Stage 2)
- **Retrieval Service** (Cloud Run)
  - Query processing and expansion
  - Vector similarity search via MongoDB Atlas
  - Context retrieval and ranking
  - Integration with Vertex AI for LLM responses
  - **Data ingestion API endpoints** for UI-controlled scraping

### 5. AI/ML Components

- **Vertex AI**:
  - Text embeddings (gemini-embedding-001)
  - Gemini Pro for response generation
  - Document analysis and summarization

## Data Flow

1. **Ingestion**: Legal documents scraped via UI or CLI → Cloud Storage
2. **Processing**: Documents → Chunks → Embeddings → MongoDB Atlas
3. **Query**: User question → Embedding → Vector search → Relevant contexts
4. **Response**: Contexts + Query → LLM → Natural language answer with citations

## Key Features

### Data Management
- **Web-based Data Ingestion Control Panel**: User-friendly interface for managing document scraping
- **Selective Document Scraping**: Choose specific documents from CSV files to scrape
- **Configurable Embedding Parameters**: Adjust chunk size and overlap with real-time estimates
- **Progress Monitoring**: Track scraping success/failure with detailed feedback
- **Duplicate Detection**: Automatically skip already-scraped documents

### Query Interface
- Natural language queries in Portuguese
- Semantic search with vector embeddings
- Context-aware responses with legal citations
- Multi-language support (Portuguese/English)

## Technology Stack

- **Google Cloud Platform**:
  - Cloud Run (containerized services)
  - Cloud Storage (document storage)
  - Vertex AI (embeddings & LLM)
  - Cloud Build (CI/CD)
- **MongoDB Atlas**:

  - Document database
  - Vector search capabilities
  - Aggregation pipelines

- **Python Stack**:
  - FastAPI (backend APIs)
  - Streamlit (frontend)
  - pymongo (MongoDB driver)
  - google-cloud-aiplatform (Vertex AI)
  - beautifulsoup4 (web scraping)

## MVP Development Stages

### Stage 1: Basic Q&A (2-3 weeks)

1. Simple web scraper for sample laws
2. Basic document processing pipeline
3. Vector search implementation
4. Simple query interface
5. LLM integration for answers

### Stage 2: Document Analysis (2-3 weeks)

1. Contract upload functionality
2. Document type classification
3. Relevant law identification
4. Summary and flaw detection
5. Enhanced UI/UX

### Stage 3: Production Ready (2-3 weeks)

1. Full scraping pipeline
2. Incremental updates
3. User authentication
4. Performance optimization
5. Monitoring and logging

## Security Considerations

- API key management via Secret Manager
- VPC for service communication
- IAM roles for service accounts
- Data encryption at rest and in transit

## Scalability

- Horizontal scaling with Cloud Run
- MongoDB Atlas auto-scaling
- Batch processing for large document sets
- Caching layer for frequent queries
