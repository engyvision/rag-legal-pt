#!/bin/bash

# Deploy script for Portuguese Legal Assistant to Google Cloud Run

set -e

# Configuration
PROJECT_ID=${GOOGLE_CLOUD_PROJECT}
REGION=${GOOGLE_CLOUD_REGION:-us-central1}
REPOSITORY="legal-assistant"
RETRIEVAL_SERVICE="retrieval-service"
FRONTEND_SERVICE="frontend-service"
SCRAPER_SERVICE="scraper-service"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting deployment to Google Cloud Run...${NC}"

# Check if required environment variables are set
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}Error: GOOGLE_CLOUD_PROJECT is not set${NC}"
    exit 1
fi

# Set Google Cloud project
echo -e "${YELLOW}Setting Google Cloud project...${NC}"
gcloud config set project $PROJECT_ID

# Verify authentication
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    echo -e "${RED}Error: No active Google Cloud authentication found${NC}"
    echo -e "${YELLOW}Please run: gcloud auth login${NC}"
    exit 1
fi

# Enable required APIs
echo -e "${YELLOW}Enabling required APIs...${NC}"
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    aiplatform.googleapis.com \
    storage.googleapis.com

# Create Artifact Registry repository if it doesn't exist
echo -e "${YELLOW}Creating Artifact Registry repository...${NC}"
gcloud artifacts repositories create $REPOSITORY \
    --repository-format=docker \
    --location=$REGION \
    --description="Portuguese Legal Assistant Docker images" || true

# Configure Docker authentication
echo -e "${YELLOW}Configuring Docker authentication...${NC}"
gcloud auth configure-docker ${REGION}-docker.pkg.dev --quiet

# Verify Docker authentication
echo -e "${YELLOW}Verifying Docker authentication...${NC}"
if ! gcloud auth print-access-token | docker login -u oauth2accesstoken --password-stdin https://${REGION}-docker.pkg.dev; then
    echo -e "${RED}Docker authentication failed${NC}"
    exit 1
fi

# Get the project number for the default Compute Engine service account
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

# Grant Secret Manager access to the service account
echo -e "${YELLOW}Granting Secret Manager access to service account...${NC}"
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${COMPUTE_SA}" \
    --role="roles/secretmanager.secretAccessor"

# Enable Secret Manager API
gcloud services enable secretmanager.googleapis.com

# Create MongoDB URI secret if it doesn't exist
echo -e "${YELLOW}Creating MongoDB URI secret...${NC}"
if [ -n "$MONGODB_URI" ]; then
    echo -n "$MONGODB_URI" | gcloud secrets create mongodb-uri \
        --data-file=- \
        --replication-policy="automatic" || \
    echo -n "$MONGODB_URI" | gcloud secrets versions add mongodb-uri \
        --data-file=-
else
    echo -e "${RED}Warning: MONGODB_URI environment variable not set${NC}"
    echo -e "${YELLOW}Please set MONGODB_URI before deployment or create the secret manually${NC}"
fi

# Build and push Docker images
echo -e "${GREEN}Building Docker image...${NC}"

# Single Docker image for all services
IMAGE_NAME="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/legal-assistant:latest"

echo -e "${YELLOW}Building application image...${NC}"
docker build -t ${IMAGE_NAME} .

echo -e "${YELLOW}Pushing image to Artifact Registry...${NC}"
# Retry push up to 3 times with increasing timeouts
for i in {1..3}; do
    echo -e "${YELLOW}Push attempt $i/3...${NC}"
    if timeout 600 docker push ${IMAGE_NAME}; then
        echo -e "${GREEN}Image pushed successfully${NC}"
        break
    else
        if [ $i -eq 3 ]; then
            echo -e "${RED}Failed to push image after 3 attempts${NC}"
            exit 1
        fi
        echo -e "${YELLOW}Push failed, retrying in 10 seconds...${NC}"
        sleep 10
    fi
done

# Deploy to Cloud Run
echo -e "${GREEN}Deploying to Cloud Run...${NC}"

# Deploy Retrieval Service
echo -e "${YELLOW}Deploying retrieval service...${NC}"
gcloud run deploy ${RETRIEVAL_SERVICE} \
    --image ${IMAGE_NAME} \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT_ID}" \
    --set-env-vars "VERTEX_AI_LOCATION=${REGION}" \
    --set-env-vars "GCS_BUCKET_NAME=${GCS_BUCKET_NAME}" \
    --set-secrets "MONGODB_URI=mongodb-uri:latest" \
    --memory 2Gi \
    --cpu 2 \
    --timeout 300 \
    --command python,-m,src.retrieval_service.main

# Get Retrieval Service URL
RETRIEVAL_URL=$(gcloud run services describe ${RETRIEVAL_SERVICE} --region $REGION --format "value(status.url)")

# Deploy Frontend Service
echo -e "${YELLOW}Deploying frontend service...${NC}"
gcloud run deploy ${FRONTEND_SERVICE} \
    --image ${IMAGE_NAME} \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --set-env-vars "RETRIEVAL_SERVICE_URL=${RETRIEVAL_URL}" \
    --memory 1Gi \
    --cpu 1 \
    --command streamlit,run,src/frontend_service/app.py,--server.port,8080,--server.address,0.0.0.0

# Get Frontend Service URL
FRONTEND_URL=$(gcloud run services describe ${FRONTEND_SERVICE} --region $REGION --format "value(status.url)")

# Create Cloud Storage bucket if it doesn't exist
echo -e "${YELLOW}Creating Cloud Storage bucket...${NC}"
gsutil mb -p $PROJECT_ID -l $REGION gs://${GCS_BUCKET_NAME} || true

# Set bucket permissions
gsutil iam ch allUsers:objectViewer gs://${GCS_BUCKET_NAME}

# Deploy Cloud Scheduler job for scraper (optional)
echo -e "${YELLOW}Setting up Cloud Scheduler for scraper...${NC}"
gcloud scheduler jobs create http scrape-legal-docs \
    --location=$REGION \
    --schedule="0 2 * * *" \
    --uri="${RETRIEVAL_URL}/api/v1/scrape" \
    --http-method=POST || true

echo -e "${GREEN}Deployment completed successfully!${NC}"
echo -e "${GREEN}Frontend URL: ${FRONTEND_URL}${NC}"
echo -e "${GREEN}Retrieval API URL: ${RETRIEVAL_URL}${NC}"