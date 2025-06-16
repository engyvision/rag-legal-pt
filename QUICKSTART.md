# Quick Start Guide - Portuguese Legal Assistant

## Prerequisites

1. **Google Cloud Account** with a project created
2. **MongoDB Atlas Account** with a cluster set up
3. **Python 3.11+** installed
4. **Docker** and **Docker Compose** installed
5. **gcloud CLI** installed and configured

## Initial Setup

### 1. Clone and Setup Environment

```bash
# Clone the repository
git clone <your-repo-url>
cd rag-legal-pt

# Copy environment variables
cp .env.example .env

# Edit .env with your values
nano .env
```

### 2. Configure Google Cloud

```bash
# Login to Google Cloud
gcloud auth login
gcloud auth application-default login

# Set your project
gcloud config set project YOUR_PROJECT_ID

# Enable required APIs
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    aiplatform.googleapis.com \
    storage.googleapis.com

# Create service account
gcloud iam service-accounts create legal-assistant-sa \
    --display-name="Legal Assistant Service Account"

# Download credentials
gcloud iam service-accounts keys create \
    credentials/service-account.json \
    --iam-account=legal-assistant-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com

# Grant necessary permissions
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:legal-assistant-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:legal-assistant-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/storage.admin"
```

### 3. Setup MongoDB Atlas

1. Create a free cluster at [MongoDB Atlas](https://www.mongodb.com/cloud/atlas)
2. Create a database user and note credentials
3. Get your connection string (MongoDB URI)
4. Update `.env` with your MongoDB URI
5. **Create the database and collections first**:

   ```bash
   # Run the setup script to create database and collections
   python scripts/setup_mongodb.py
   ```

   This will create:

   - Database: `legal_assistant`
   - Collections: `documents`, `vectors`, `queries`

6. **After collections are created**, create Vector Search Index:
   - Go to your cluster in MongoDB Atlas
   - Click on "Search" tab (or "Atlas Search")
   - Click "Create Search Index"
   - Wait 2-3 minutes for index to build
7. **Test the vector search**:
   ```bash
   python scripts/test_vector_search.py
   ```
   This will verify that vector search is working properly.
   - Choose "JSON Editor" configuration method
   - Select database: `legal_assistant`
   - Select collection: `vectors`
   - Index name: `vector_index`
   - Use this configuration:
   ```json
   {
     "fields": [
       {
         "type": "vector",
         "path": "embedding",
         "numDimensions": 3072,
         "similarity": "cosine"
       }
     ]
   }
   ```
   - Click "Create Search Index"

### 4. Create Cloud Storage Bucket

```bash
gsutil mb -p YOUR_PROJECT_ID -l us-central1 gs://legal-docs-bucket-YOUR_PROJECT_ID
```

### 5. Local Development

#### Verify Setup First:

```bash
# Run verification script to check all components
python scripts/verify_setup.py
```

This will check:

- Environment variables
- Google Cloud connection
- MongoDB connection
- Required collections
- Sample data

#### Using Docker Compose:

```bash
# Build and start all services
docker-compose up --build

# Run setup scripts
docker-compose run --rm setup

# Initialize sample data
docker-compose run --rm setup python scripts/init_data.py
```

#### Using Python directly:

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup MongoDB
python scripts/setup_mongodb.py

# Initialize sample data
python scripts/init_data.py

# Start retrieval service
python -m src.retrieval_service.main

# In another terminal, start frontend
streamlit run src/frontend_service/app.py
```

### 6. Deploy to Google Cloud Run

```bash
# Make deploy script executable
chmod +x scripts/deploy.sh

# Run deployment
./scripts/deploy.sh
```

## Testing the Application

### Local Testing

1. **Frontend**: http://localhost:8501
2. **API**: http://localhost:8000
3. **API Docs**: http://localhost:8000/docs

### Sample Queries

Try these queries in the frontend:

- "Quais são os tipos de sociedades comerciais em Portugal?"
- "Como funciona o teletrabalho segundo a legislação portuguesa?"
- "Qual é o período normal de trabalho?"

### API Testing

```bash
# Test health endpoint
curl http://localhost:8000/health

# Test query endpoint
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "O que é uma sociedade por quotas?",
    "top_k": 5,
    "use_llm": true
  }'
```

## Common Issues

### MongoDB Connection Error

- Check your MongoDB URI in `.env`
- Ensure IP whitelist includes your IP (or 0.0.0.0/0 for development)

### Google Cloud Authentication Error

- Ensure `GOOGLE_APPLICATION_CREDENTIALS` points to valid credentials
- Run `gcloud auth application-default login`

### Vector Search Not Working

- Ensure you created the Atlas Search index with the correct JSON format
- Index name must be exactly: `vector_index`
- Wait 2-3 minutes for index to be available
- Run `python scripts/test_vector_search.py` to diagnose issues
- Check that the JSON format matches the current Atlas UI requirements:
  ```json
  {
    "fields": [
      {
        "type": "vector",
        "path": "embedding",
        "numDimensions": 768,
        "similarity": "cosine"
      }
    ]
  }
  ```

## Next Steps

1. **Add More Data**: Run the scraper to get real legal documents

   ```bash
   docker-compose run --rm scraper
   ```

2. **Customize Prompts**: Edit prompts in `src/retrieval_service/core/llm.py`

3. **Add Authentication**: Implement user authentication for production

4. **Monitor Usage**: Set up Google Cloud monitoring and alerts

5. **Scale**: Adjust Cloud Run instance settings based on usage

## Support

For issues or questions:

- Check logs: `docker-compose logs -f`
- Review the main README.md
- Check Google Cloud logs in the Console
