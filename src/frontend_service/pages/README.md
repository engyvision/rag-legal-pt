# Data Ingestion Control UI

## Overview

The Data Ingestion Control UI provides a comprehensive interface for managing the scraping and ingestion of Portuguese legal documents. This UI allows you to preview CSV entries, selectively scrape documents, configure embedding parameters, and monitor the ingestion process.

## Features

### 1. Document Preview & Selection

- **CSV File Preview**: View all documents from CSV files before scraping
- **Selective Scraping**: Choose specific documents to scrape
- **Batch Selection**: Select all pending, first N documents, or manually pick documents
- **Status Tracking**: See which documents are already scraped vs pending

### 2. Embedding Configuration

- **Dynamic Chunk Size**: Adjust chunk size (100-5000 characters)
- **Overlap Control**: Configure chunk overlap (0-1000 characters)
- **Real-time Estimation**: See estimated chunks for selected documents

### 3. Filtering & Search

- Filter by CSV file source
- Filter by document type (Lei, Decreto-Lei, etc.)
- Filter by status (Pending, Scraped, Failed)

### 4. Progress Monitoring

- Real-time scraping progress
- Success/failure tracking
- Detailed error messages

## Setup

**Note**: This UI is already integrated into the Portuguese Legal Assistant. The setup steps below are for reference only.

### Prerequisites

1. **Both services must be running**:
   - Retrieval Service: `python -m src.retrieval_service.main` (port 8000)
   - Frontend Service: `streamlit run src/frontend_service/app.py` (port 8501)

2. **Required data structure**:
   - CSV files must be in `data/legislationPT/` directory
   - Each CSV should have columns for title, issuing body, description, and URL

3. **API endpoints** (already implemented):
   - `/check-existing-documents` - Check which documents exist
   - `/scrape-document` - Scrape individual documents
   - `/ingestion-stats` - Get ingestion statistics

### Quick Start

1. Ensure both services are running
2. Navigate to http://localhost:8501
3. Click "Data Ingestion Control" in the sidebar
4. Click "🔄 Load/Refresh Document List"
5. Select documents and configure parameters
6. Click "🚀 Start Scraping"

## Usage

### 1. Access the UI

Navigate to the Data Ingestion page in your Streamlit app:

1. Start both services:
   ```bash
   # Start retrieval service
   python -m src.retrieval_service.main
   
   # Start frontend service (in another terminal)
   streamlit run src/frontend_service/app.py
   ```

2. Open browser and go to: `http://localhost:8501`
3. Click "Data Ingestion Control" in the sidebar

### 2. Load Documents

1. Click "🔄 Load/Refresh Document List" to load CSV files
2. The system will read all CSV files from `data/legislationPT/`
3. Document metadata will be extracted automatically

### 3. Configure Parameters

In the sidebar:

- **Chunk Size**: Set the size of text chunks (affects number of embeddings)
- **Chunk Overlap**: Set overlap between chunks (improves context continuity)

### 4. Select Documents

Several selection methods:

- Individual checkboxes for each document
- "Select All Pending" button
- "Select First N Pending" with customizable N
- Manual selection while viewing document details

### 5. Review Selection

The UI shows:

- Total documents available
- Number selected
- Already scraped count
- Estimated total chunks (based on current parameters)

### 6. Start Scraping

1. Click "🚀 Start Scraping" button
2. Monitor progress in real-time
3. View success/failure status for each document
4. Failed documents can be retried

### 7. View Results

After scraping:

- Successful documents show number of chunks created
- Failed documents show error messages
- Refresh the list to see updated statuses

## Best Practices

### Chunk Size Selection

- **Smaller chunks (500-1000)**: Better for precise retrieval, more embeddings
- **Larger chunks (2000-3000)**: More context per chunk, fewer embeddings
- **Default (1000)**: Good balance for most legal documents

### Overlap Configuration

- **No overlap (0)**: Risk losing context at boundaries
- **Small overlap (100-200)**: Good for most cases
- **Large overlap (300-500)**: Use for documents with complex cross-references

### Batch Processing

- Start with small batches (10-20 documents) to test
- Monitor memory usage for large batches
- Use filtering to process specific document types

### Error Handling

- Documents that fail to scrape are skipped (no fake content)
- Check error messages for specific issues:
  - Network timeouts
  - Invalid URLs
  - JavaScript rendering failures
- Retry failed documents with different parameters if needed

## API Integration

### Check Existing Documents

```python
POST /api/v1/check-existing-documents
{
    "urls": ["url1", "url2", ...]
}

Response:
{
    "url1": {
        "exists": true,
        "document_id": "...",
        "last_updated": "...",
        "chunks_count": 5
    }
}
```

### Scrape Document

```python
POST /api/v1/scrape-document
{
    "url": "https://...",
    "document_type": "lei",
    "title": "Lei n.º 23/2023",
    "issuing_body": "Assembleia da República",
    "description": "...",
    "document_number": "23/2023",
    "publication_date": "2023-05-15",
    "chunk_size": 1000,
    "chunk_overlap": 200,
    "metadata": {...}
}

Response:
{
    "status": "success",
    "document_id": "...",
    "chunks_created": 8,
    "text_length": 7500,
    "chunk_size_used": 1000,
    "chunk_overlap_used": 200
}
```

### Get Ingestion Stats

```python
GET /api/v1/ingestion-stats

Response:
{
    "total_documents": 150,
    "total_vectors": 1200,
    "average_chunks_per_document": 8.0,
    "documents_by_type": [...],
    "documents_by_source": [...],
    "recent_documents": [...]
}
```

## Troubleshooting

### Common Issues

1. **"Data directory not found"**

   - Ensure CSV files are in `data/legislationPT/`
   - Check file permissions

2. **Scraping failures**

   - Verify internet connection
   - Check if target website is accessible
   - Try different scraping methods (Playwright vs Selenium)

3. **Memory issues with large batches**

   - Reduce batch size
   - Increase chunk size to create fewer embeddings
   - Process documents by type

4. **Slow performance**
   - Scraping includes delays to be respectful to servers
   - Consider running overnight for large datasets
   - Use multiple workers (future enhancement)

## Integration with Main Application

This Data Ingestion Control UI is integrated into the main Portuguese Legal Assistant application:

- **Navigation**: Available via sidebar button "Data Ingestion Control"
- **Dependencies**: Requires both retrieval service and frontend service to be running
- **Data Source**: Reads CSV files from `data/legislationPT/` directory
- **Output**: Scraped documents are stored in MongoDB and immediately available for queries

## Future Enhancements

Planned improvements:

- Parallel scraping with worker pools
- Incremental updates (detect changed documents)
- Export/import selection sets
- Scheduling for automatic ingestion
- Advanced duplicate detection
- Content change detection
- Document versioning and change tracking
