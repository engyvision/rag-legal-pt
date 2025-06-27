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