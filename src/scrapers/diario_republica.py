"""Scraper for Diário da República website."""

import requests
from bs4 import BeautifulSoup
import logging
import time
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import re
from urllib.parse import urljoin, urlparse
import json

logger = logging.getLogger(__name__)


class DiarioRepublicaScraper:
    """Scraper for Portuguese legal documents from Diário da República."""

    def __init__(self, base_url: str = "https://diariodarepublica.pt"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "Mozilla/5.0 (Legal Assistant Bot) Educational Purpose"}
        )
        self.delay = 1.5  # Seconds between requests

    def scrape_recent_documents(
        self, days_back: int = 7, max_documents: int = 100
    ) -> List[Dict[str, Any]]:
        """Scrape recent documents from the last N days."""
        documents = []

        # Generate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        logger.info(f"Scraping documents from {start_date} to {end_date}")

        current_date = start_date
        while current_date <= end_date and len(documents) < max_documents:
            date_str = current_date.strftime("%Y-%m-%d")

            try:
                # Scrape documents for this date
                daily_docs = self._scrape_date(date_str)
                documents.extend(daily_docs)

                logger.info(f"Found {len(daily_docs)} documents for {date_str}")

            except Exception as e:
                logger.error(f"Error scraping {date_str}: {e}")

            current_date += timedelta(days=1)
            time.sleep(self.delay)

        return documents[:max_documents]

    def _scrape_date(self, date_str: str) -> List[Dict[str, Any]]:
        """Scrape documents for a specific date."""
        # This is a simplified example - actual implementation would need
        # to handle the specific structure of diariodarepublica.pt

        documents = []

        # Construct URL for the date
        url = f"{self.base_url}/home/-/dre/dia/{date_str}"

        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "html.parser")

            # Find document listings (adjust selectors based on actual site structure)
            doc_elements = soup.find_all("div", class_="dre-document") or soup.find_all(
                "article", class_="diploma"
            )

            for elem in doc_elements:
                doc = self._parse_document_element(elem, date_str)
                if doc:
                    documents.append(doc)

        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")

        return documents

    def _parse_document_element(
        self, element: BeautifulSoup, date_str: str
    ) -> Optional[Dict[str, Any]]:
        """Parse a document element from the page."""
        try:
            # Extract basic information
            title = element.find("h2") or element.find("h3")
            title_text = title.get_text(strip=True) if title else ""

            # Extract document number/ID
            doc_number = element.find("span", class_="diploma-numero")
            doc_number_text = doc_number.get_text(strip=True) if doc_number else ""

            # Extract summary
            summary = element.find("div", class_="diploma-sumario") or element.find(
                "p", class_="summary"
            )
            summary_text = summary.get_text(strip=True) if summary else ""

            # Extract link to full document
            link = element.find("a", href=True)
            doc_url = urljoin(self.base_url, link["href"]) if link else ""

            # Extract document type
            doc_type = self._extract_document_type(title_text, doc_number_text)

            # Create document object
            document = {
                "source": "diario_republica",
                "title": title_text,
                "document_number": doc_number_text,
                "summary": summary_text,
                "url": doc_url,
                "document_type": doc_type,
                "publication_date": date_str,
                "scraped_at": datetime.now().isoformat(),
                "metadata": {"source_url": self.base_url, "date_str": date_str},
            }

            # Fetch full text if URL is available
            if doc_url:
                time.sleep(self.delay)
                full_text = self._fetch_document_text(doc_url)
                if full_text:
                    document["full_text"] = full_text
                    document["text_length"] = len(full_text)

            return document

        except Exception as e:
            logger.error(f"Error parsing document element: {e}")
            return None

    def _fetch_document_text(self, url: str) -> Optional[str]:
        """Fetch the full text of a document."""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "html.parser")

            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()

            # Find main content area (adjust based on site structure)
            content = (
                soup.find("div", class_="diploma-texto")
                or soup.find("div", class_="document-content")
                or soup.find("main")
            )

            if content:
                # Extract text and clean it
                text = content.get_text(separator="\n", strip=True)

                # Clean up text
                # Remove excessive newlines
                text = re.sub(r"\n{3,}", "\n\n", text)
                # Remove excessive spaces
                text = re.sub(r" {2,}", " ", text)

                return text

            # Fallback to body text
            return soup.get_text(separator="\n", strip=True)

        except Exception as e:
            logger.error(f"Error fetching document text from {url}: {e}")
            return None

    def _extract_document_type(self, title: str, number: str) -> str:
        """Extract document type from title and number."""
        # Common Portuguese legal document types
        type_patterns = {
            "lei": r"Lei n\.?º?\s*\d+",
            "decreto_lei": r"Decreto-Lei n\.?º?\s*\d+",
            "decreto": r"Decreto n\.?º?\s*\d+",
            "portaria": r"Portaria n\.?º?\s*\d+",
            "despacho": r"Despacho n\.?º?\s*\d+",
            "resolucao": r"Resolução.*n\.?º?\s*\d+",
            "regulamento": r"Regulamento n\.?º?\s*\d+",
            "aviso": r"Aviso n\.?º?\s*\d+",
            "deliberacao": r"Deliberação n\.?º?\s*\d+",
        }

        combined_text = f"{title} {number}".lower()

        for doc_type, pattern in type_patterns.items():
            if re.search(pattern, combined_text, re.IGNORECASE):
                return doc_type

        return "other"

    def scrape_by_search(
        self, search_term: str, max_results: int = 50
    ) -> List[Dict[str, Any]]:
        """Scrape documents by search term."""
        documents = []

        # Construct search URL (adjust based on actual site)
        search_url = f"{self.base_url}/pesquisa/-/search/{search_term}/basic"

        try:
            response = self.session.get(search_url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "html.parser")

            # Parse search results
            # This would need to be adjusted based on actual site structure

        except Exception as e:
            logger.error(f"Error searching for '{search_term}': {e}")

        return documents

    def scrape_document_content(self, url: str) -> Optional[str]:
        """Public method to scrape content from a single URL."""
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