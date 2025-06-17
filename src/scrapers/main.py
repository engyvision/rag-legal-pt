"""Main scraper service for Portuguese legal documents."""

import logging
import asyncio
import os
import sys
from datetime import datetime
import json
from google.cloud import storage
import aiohttp

# Add parent directory to path
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from src.retrieval_service.core.config import settings
from src.scrapers.diario_republica import DiarioRepublicaScraper
from src.scrapers.browse_ai import BrowseAIScraper

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ScraperService:
    """Main scraper service coordinator."""

    def __init__(self):
        self.storage_client = storage.Client()
        self.bucket = self.storage_client.bucket(settings.gcs_bucket_name)
        self.diario_scraper = DiarioRepublicaScraper()
        self.browse_ai_scraper = BrowseAIScraper()

    async def run_daily_scrape(self, use_browse_ai: bool = False, robot_id: str = None):
        """Run daily scraping job."""
        logger.info("Starting daily scrape job...")

        try:
            if use_browse_ai and robot_id:
                # Use Browse AI scraper
                logger.info("Using Browse AI scraper")
                documents = self.browse_ai_scraper.scrape_recent_documents(
                    robot_id=robot_id, days_back=1, max_documents=50
                )
            else:
                # Use traditional scraper
                logger.info("Using traditional scraper")
                documents = self.diario_scraper.scrape_recent_documents(
                    days_back=1, max_documents=50
                )

            logger.info(f"Scraped {len(documents)} documents")

            # Upload to Cloud Storage and trigger processing
            for doc in documents:
                await self._process_document(doc)

            logger.info("Daily scrape completed successfully")

        except Exception as e:
            logger.error(f"Error in daily scrape: {e}")
            raise

    async def scrape_historical(self, start_date: str, end_date: str):
        """Scrape historical documents for a date range."""
        logger.info(f"Scraping historical documents from {start_date} to {end_date}")

        # Implementation for historical scraping
        # This would iterate through the date range and scrape documents

    async def _process_document(self, document: dict):
        """Process a scraped document."""
        try:
            # Generate unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            doc_type = document.get("document_type", "unknown")
            filename = (
                f"{timestamp}_{doc_type}_{document.get('document_number', 'doc')}.json"
            )

            # Upload to Cloud Storage
            blob_name = f"{settings.gcs_raw_prefix}scraped/{filename}"
            blob = self.bucket.blob(blob_name)

            # Upload document as JSON
            blob.upload_from_string(
                json.dumps(document, ensure_ascii=False),
                content_type="application/json",
            )

            logger.info(f"Uploaded document to {blob_name}")

            # Trigger processing via API
            await self._trigger_processing(blob_name, document)

        except Exception as e:
            logger.error(f"Error processing document: {e}")

    async def _trigger_processing(self, gcs_path: str, document: dict):
        """Trigger document processing via retrieval service API."""
        try:
            # In production, this would call the retrieval service API
            # For now, we'll just log it

            retrieval_url = os.getenv("RETRIEVAL_SERVICE_URL", "http://localhost:8000")

            async with aiohttp.ClientSession() as session:
                payload = {
                    "gcs_path": f"gs://{settings.gcs_bucket_name}/{gcs_path}",
                    "metadata": {
                        "title": document.get("title"),
                        "document_type": document.get("document_type"),
                        "document_number": document.get("document_number"),
                        "publication_date": document.get("publication_date"),
                        "url": document.get("url"),
                        "source": "diario_republica",
                    },
                }

                async with session.post(
                    f"{retrieval_url}/api/v1/process", json=payload
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"Document processed: {result.get('document_id')}")
                    else:
                        logger.error(f"Processing failed: {response.status}")

        except Exception as e:
            logger.error(f"Error triggering processing: {e}")


async def main():
    """Main entry point."""
    service = ScraperService()

    # Check for command line arguments
    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "daily":
            await service.run_daily_scrape()
        elif command == "browse-ai" and len(sys.argv) >= 3:
            robot_id = sys.argv[2]
            await service.run_daily_scrape(use_browse_ai=True, robot_id=robot_id)
        elif command == "historical" and len(sys.argv) == 4:
            start_date = sys.argv[2]
            end_date = sys.argv[3]
            await service.scrape_historical(start_date, end_date)
        else:
            logger.error(
                "Invalid command. Use: daily, browse-ai <robot_id>, or historical <start_date> <end_date>"
            )
            sys.exit(1)
    else:
        # Default to daily scrape
        await service.run_daily_scrape()


if __name__ == "__main__":
    asyncio.run(main())
