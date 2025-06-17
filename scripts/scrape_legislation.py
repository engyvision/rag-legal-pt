"""Scrape Portuguese legal documents from CSV files and diariodarepublica.pt."""

import os
import sys
import csv
import re
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import requests
from bs4 import BeautifulSoup
import time

# Add src to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.common.models import DocumentType, DocumentSource
from src.retrieval_service.core.embeddings import EmbeddingsClient
from src.retrieval_service.core.mongodb import MongoDBClient
from src.retrieval_service.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Document type mappings
DOCUMENT_TYPE_MAPPING = {
    "Lei.csv": DocumentType.LEI,
    "Decreto-Lei.csv": DocumentType.DECRETO_LEI,
    "Decreto.csv": DocumentType.DECRETO,
    "Portaria.csv": DocumentType.PORTARIA,
}

# CSV column mappings - last 4 columns are what we need
CSV_COLUMN_MAPPING = {
    "Lei.csv": {
        "title": "Law Title",
        "issuing_body": "Issuing Body", 
        "description": "Description",
        "link": "Law Link"
    },
    "Decreto-Lei.csv": {
        "title": "Decree Title",
        "issuing_body": "Ministry",
        "description": "Description-2", 
        "link": "Decree Link"
    },
    "Decreto.csv": {
        "title": "Decree Title-2",
        "issuing_body": "Issuing Body-2",
        "description": "Description-3",
        "link": "Decree Link-2"
    },
    "Portaria.csv": {
        "title": "Title", 
        "issuing_body": "Sector",
        "description": "Description-4",
        "link": "Link"
    }
}


class LegislationScraper:
    """Scrapes Portuguese legal documents from CSV files and websites."""
    
    def __init__(self):
        self.mongodb_client = MongoDBClient()
        self.embeddings_client = EmbeddingsClient()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
    def extract_document_number(self, title: str, doc_type: DocumentType) -> Optional[str]:
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
        
        # Fallback: try to extract any number/year pattern
        fallback_match = re.search(r"n\.º (\d+/\d+)", title)
        if fallback_match:
            return fallback_match.group(1)
            
        return None
    
    def extract_publication_date(self, title: str) -> Optional[str]:
        """Extract publication date from title."""
        # Look for date patterns like 2021-11-04
        date_match = re.search(r"(\d{4}-\d{2}-\d{2})", title)
        if date_match:
            return date_match.group(1)
        return None
        
    def read_csv_file(self, file_path: Path) -> List[Dict]:
        """Read and parse CSV file."""
        filename = file_path.name
        column_mapping = CSV_COLUMN_MAPPING.get(filename, {})
        
        if not column_mapping:
            logger.warning(f"No column mapping found for {filename}, using generic mapping")
            # Use generic mapping for unknown files
            column_mapping = {
                "title": "Title",
                "issuing_body": "Issuing Body",
                "description": "Description", 
                "link": "Link"
            }
        
        documents = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                
                for row in reader:
                    # Extract the last 4 columns dynamically
                    fieldnames = reader.fieldnames
                    if len(fieldnames) >= 4:
                        last_4_columns = fieldnames[-4:]
                        
                        # Map to our standard structure
                        doc_data = {
                            "title": row.get(last_4_columns[0], "").strip(),
                            "issuing_body": row.get(last_4_columns[1], "").strip(),
                            "description": row.get(last_4_columns[2], "").strip(),
                            "link": row.get(last_4_columns[3], "").strip(),
                            "raw_row": row  # Keep original data for reference
                        }
                        
                        if doc_data["title"] and doc_data["link"]:
                            documents.append(doc_data)
                        
        except Exception as e:
            logger.error(f"Error reading CSV file {file_path}: {e}")
            
        return documents
    
    def scrape_document_content(self, url: str) -> Optional[str]:
        """Scrape document content from diariodarepublica.pt using Playwright for JS rendering."""
        try:
            logger.info(f"Scraping content from: {url}")
            
            # Try Playwright approach for JavaScript rendering  
            try:
                import asyncio
                import nest_asyncio
                nest_asyncio.apply()  # Allow nested event loops
                content = asyncio.run(self.scrape_with_playwright(url))
                if content:
                    return content
            except Exception as e:
                logger.warning(f"Playwright failed: {e}")
            
            # Fallback to Selenium if Playwright fails
            logger.warning("Playwright failed, trying Selenium fallback...")
            content = self.scrape_with_selenium(url)
            if content:
                return content
            
            # Final fallback to requests approach (likely won't work for dynamic content)
            logger.warning("Both Playwright and Selenium failed, trying requests fallback...")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for the main content area (static content)
            content_selectors = [
                '.Fragmento_Texto',
                '.diploma-fragmento', 
                '.content-body',
                '.document-content',
                '#content',
                '.main-content'
            ]
            
            content = None
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    content = content_elem.get_text(strip=True)
                    logger.debug(f"Found content with selector '{selector}': {len(content)} chars")
                    break
            
            # Clean up the content
            if content:
                content = re.sub(r'\s+', ' ', content)
                content = re.sub(r'\n\s*\n', '\n\n', content)
                
            logger.info(f"Final content length: {len(content) if content else 0} characters")
            return content if content and len(content) > 100 else None
            
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return None
    
    async def scrape_with_playwright(self, url: str) -> Optional[str]:
        """Scrape content using Playwright for JavaScript rendering."""
        try:
            from playwright.async_api import async_playwright
            
            async with async_playwright() as p:
                browser_options = {
                    'headless': True,
                    'args': [
                        '--no-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-gpu',
                        '--disable-software-rasterizer'
                    ]
                }
                
                browser = await p.chromium.launch(**browser_options)
                page = await browser.new_page()
                
                try:
                    await page.set_extra_http_headers({
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    })
                    
                    logger.info("Loading page with Playwright...")
                    await page.goto(url, wait_until='networkidle', timeout=30000)
                    await page.wait_for_selector('.Fragmento_Texto', timeout=20000)
                    
                    # Extract structured content
                    document_parts = []
                    
                    # Get main document intro
                    try:
                        intro_text = await page.text_content('div.Fragmento_Texto.diploma-fragmento')
                        if intro_text and intro_text.strip():
                            document_parts.append("=== DOCUMENTO ===")
                            document_parts.append(intro_text.strip())
                            document_parts.append("")
                    except:
                        pass
                    
                    # Get all articles
                    article_containers = await page.query_selector_all('div.fragmento-full-width')
                    
                    for container in article_containers:
                        try:
                            title_elem = await container.query_selector('.Fragmento_Titulo')
                            title = await title_elem.text_content() if title_elem else ""
                            
                            subject_elem = await container.query_selector('.Fragmento_Epigrafe')
                            subject = await subject_elem.text_content() if subject_elem else ""
                            
                            content_elem = await container.query_selector('.Fragmento_Texto.diploma-fragmento')
                            content = await content_elem.text_content() if content_elem else ""
                            
                            if title or subject or content:
                                if title and title.strip():
                                    document_parts.append(f"=== {title.strip().upper()} ===")
                                if subject and subject.strip():
                                    document_parts.append(subject.strip())
                                if content and content.strip():
                                    document_parts.append(content.strip())
                                document_parts.append("")
                                
                        except Exception as e:
                            logger.debug(f"Error processing article: {e}")
                            continue
                    
                    full_content = '\n'.join(document_parts).strip()
                    
                    if len(full_content) > 500:
                        logger.info(f"✓ Playwright extracted {len(full_content)} characters")
                        return full_content
                    else:
                        logger.warning(f"Playwright extracted insufficient content: {len(full_content)} chars")
                        return None
                        
                finally:
                    await browser.close()
                    
        except ImportError:
            logger.warning("Playwright not available")
            return None
        except Exception as e:
            logger.error(f"Playwright error: {e}")
            return None
    
    def scrape_with_selenium(self, url: str) -> Optional[str]:
        """Scrape content using Selenium for JavaScript rendering."""
        try:
            from selenium import webdriver
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.webdriver.chrome.options import Options
            from selenium.common.exceptions import TimeoutException, WebDriverException
            from webdriver_manager.chrome import ChromeDriverManager
            from selenium.webdriver.chrome.service import Service
            
            # Chrome options for headless browsing
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--disable-extensions')
            options.add_argument('--disable-plugins')
            
            # Use webdriver-manager to handle Chrome driver setup
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            
            try:
                logger.info("Loading page with Selenium...")
                driver.get(url)
                
                # Wait for the content to load (look for article elements)
                wait = WebDriverWait(driver, 20)
                wait.until(EC.presence_of_element_located((By.CLASS_NAME, "Fragmento_Texto")))
                
                # Extract structured content
                document_parts = []
                
                # Get main document title and intro
                try:
                    intro_elem = driver.find_element(By.CSS_SELECTOR, "div.Fragmento_Texto.diploma-fragmento")
                    if intro_elem:
                        intro_text = intro_elem.text.strip()
                        if intro_text:
                            document_parts.append("=== DOCUMENTO ===")
                            document_parts.append(intro_text)
                            document_parts.append("")
                except:
                    pass
                
                # Get all articles
                article_containers = driver.find_elements(By.CSS_SELECTOR, "div.fragmento-full-width")
                
                for container in article_containers:
                    try:
                        # Get article title
                        title_elem = container.find_element(By.CSS_SELECTOR, ".Fragmento_Titulo")
                        title = title_elem.text.strip() if title_elem else ""
                        
                        # Get article subject/epigraph
                        subject_elem = container.find_element(By.CSS_SELECTOR, ".Fragmento_Epigrafe")
                        subject = subject_elem.text.strip() if subject_elem else ""
                        
                        # Get article content
                        content_elem = container.find_element(By.CSS_SELECTOR, ".Fragmento_Texto.diploma-fragmento")
                        content = content_elem.text.strip() if content_elem else ""
                        
                        # Build article section
                        if title or subject or content:
                            if title:
                                document_parts.append(f"=== {title.upper()} ===")
                            if subject:
                                document_parts.append(subject)
                            if content:
                                document_parts.append(content)
                            document_parts.append("")
                            
                    except Exception as e:
                        logger.debug(f"Error processing article container: {e}")
                        continue
                
                # Combine all parts
                full_content = '\n'.join(document_parts).strip()
                
                if len(full_content) > 500:  # Substantial content
                    logger.info(f"✓ Selenium extracted {len(full_content)} characters")
                    return full_content
                else:
                    logger.warning(f"Selenium extracted insufficient content: {len(full_content)} chars")
                    return None
                    
            finally:
                driver.quit()
                
        except ImportError:
            logger.warning("Selenium not available - install with: pip install selenium")
            return None
        except (TimeoutException, WebDriverException) as e:
            logger.error(f"Selenium error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected Selenium error: {e}")
            return None
    
    async def process_csv_files(self, data_dir: Path) -> List[Dict]:
        """Process all CSV files in the data directory."""
        all_documents = []
        
        csv_files = list(data_dir.glob("*.csv"))
        logger.info(f"Found {len(csv_files)} CSV files")
        
        for csv_file in csv_files:
            logger.info(f"Processing {csv_file.name}")
            
            # Determine document type
            doc_type = DOCUMENT_TYPE_MAPPING.get(csv_file.name, DocumentType.OTHER)
            
            # Read CSV data
            csv_documents = self.read_csv_file(csv_file)
            logger.info(f"Found {len(csv_documents)} documents in {csv_file.name}")
            
            # Process each document
            for doc_data in csv_documents:
                try:
                    # Extract metadata
                    document_number = self.extract_document_number(doc_data["title"], doc_type)
                    publication_date = self.extract_publication_date(doc_data["title"])
                    
                    # Scrape content
                    scraped_content = self.scrape_document_content(doc_data["link"])
                    
                    if not scraped_content:
                        logger.error(f"❌ SKIPPING - Could not scrape real content for: {doc_data['title']}")
                        logger.error(f"   URL: {doc_data['link']}")
                        logger.error(f"   Reason: No real legal text could be extracted")
                        continue  # Skip this document entirely - no fake content!
                    
                    # Create document record
                    document = {
                        "title": doc_data["title"],
                        "text": scraped_content,
                        "document_type": doc_type,
                        "document_number": document_number,
                        "publication_date": publication_date,
                        "source": DocumentSource.SCRAPER,
                        "url": doc_data["link"],
                        "metadata": {
                            "issuing_body": doc_data["issuing_body"],
                            "description": doc_data["description"],
                            "csv_file": csv_file.name,
                            "scraped_at": datetime.now().isoformat(),
                            "raw_csv_data": doc_data["raw_row"]
                        },
                        "created_at": datetime.now(),
                        "updated_at": datetime.now()
                    }
                    
                    all_documents.append(document)
                    
                    # Add delay to be respectful to the server
                    time.sleep(1)
                    
                except Exception as e:
                    logger.error(f"Error processing document {doc_data['title']}: {e}")
                    continue
        
        return all_documents
    
    async def store_documents(self, documents: List[Dict]):
        """Store documents and create embeddings."""
        logger.info(f"Storing {len(documents)} documents...")
        
        try:
            self.mongodb_client.connect()
            
            for doc_data in documents:
                logger.info(f"Processing document: {doc_data['title']}")
                
                # Check if document already exists
                existing = await self.mongodb_client.async_db[
                    settings.mongodb_collection_documents
                ].find_one({
                    "url": doc_data["url"],
                    "source": DocumentSource.SCRAPER
                })
                
                if existing:
                    logger.info(f"Document already exists, skipping: {doc_data['title']}")
                    continue
                
                # Insert document
                doc_id = await self.mongodb_client.insert_document(doc_data)
                logger.info(f"Inserted document with ID: {doc_id}")
                
                # Create chunks and embeddings
                text = doc_data["text"]
                chunks = self.embeddings_client.chunk_text(text)
                logger.info(f"Created {len(chunks)} chunks")
                
                # Generate embeddings
                chunk_texts = [chunk["text"] for chunk in chunks]
                embeddings = await self.embeddings_client.agenerate_embeddings_batch(
                    chunk_texts,
                    batch_size=5
                )
                
                # Store vectors
                from bson import ObjectId
                for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                    vector_doc = {
                        "document_id": ObjectId(doc_id),
                        "text": chunk["text"],
                        "embedding": embedding,
                        "chunk_index": i,
                        "metadata": {
                            "start_char": chunk["start_char"],
                            "end_char": chunk["end_char"],
                            "document_type": doc_data["document_type"],
                            "document_title": doc_data["title"],
                            "document_number": doc_data["document_number"],
                            "issuing_body": doc_data["metadata"]["issuing_body"]
                        },
                        "created_at": datetime.now()
                    }
                    
                    await self.mongodb_client.insert_vector(vector_doc)
                
                logger.info(f"Created {len(chunks)} vectors for document")
        
        except Exception as e:
            logger.error(f"Error storing documents: {e}")
            raise
        
        finally:
            self.mongodb_client.close()


async def main():
    """Main function to run the scraper."""
    logger.info("Starting legislation scraping process...")
    
    # Initialize scraper
    scraper = LegislationScraper()
    
    # Set data directory
    data_dir = Path(__file__).parent.parent / "data" / "legislationPT"
    
    if not data_dir.exists():
        logger.error(f"Data directory not found: {data_dir}")
        return
    
    try:
        # Process CSV files and scrape content
        documents = await scraper.process_csv_files(data_dir)
        logger.info(f"Successfully processed {len(documents)} documents")
        
        if documents:
            # Store in MongoDB
            await scraper.store_documents(documents)
            logger.info("Document storage completed!")
            
            # Display statistics
            scraper.mongodb_client.connect()
            doc_count = await scraper.mongodb_client.async_db[
                settings.mongodb_collection_documents
            ].count_documents({"source": DocumentSource.SCRAPER})
            
            vector_count = await scraper.mongodb_client.async_db[
                settings.mongodb_collection_vectors
            ].count_documents({})
            
            logger.info(f"Total scraped documents in DB: {doc_count}")
            logger.info(f"Total vectors in DB: {vector_count}")
            
        else:
            logger.warning("No documents were processed")
            
    except Exception as e:
        logger.error(f"Scraping process failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())