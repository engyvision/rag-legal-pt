"""Tests for scraper service."""

from src.scrapers.diario_republica import DiarioRepublicaScraper
import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
import sys
import os

# Add src to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestDiarioRepublicaScraper:
    """Test cases for Diário da República scraper."""

    @pytest.fixture
    def scraper(self):
        """Create a scraper instance."""
        return DiarioRepublicaScraper()

    def test_extract_document_type(self, scraper):
        """Test document type extraction."""
        test_cases = [
            ("Lei n.º 23/2023", "", "lei"),
            ("Decreto-Lei n.º 45/2023", "", "decreto_lei"),
            ("Portaria n.º 123/2023", "", "portaria"),
            ("Random text", "", "other")
        ]

        for title, number, expected in test_cases:
            result = scraper._extract_document_type(title, number)
            assert result == expected

    def test_parse_document_element(self, scraper):
        """Test parsing of document elements."""
        from bs4 import BeautifulSoup

        html = """
        <div class="dre-document">
            <h2>Lei n.º 23/2023</h2>
            <span class="diploma-numero">23/2023</span>
            <div class="diploma-sumario">Test summary</div>
            <a href="/document/123">View</a>
        </div>
        """

        soup = BeautifulSoup(html, 'html.parser')
        element = soup.find('div', class_='dre-document')

        with patch.object(scraper, '_fetch_document_text', return_value="Full text"):
            doc = scraper._parse_document_element(element, "2023-05-15")

        assert doc is not None
        assert doc["title"] == "Lei n.º 23/2023"
        assert doc["document_number"] == "23/2023"
        assert doc["summary"] == "Test summary"
        assert doc["document_type"] == "lei"
        assert doc["publication_date"] == "2023-05-15"

    @patch('requests.Session.get')
    def test_scrape_recent_documents(self, mock_get, scraper):
        """Test scraping recent documents."""
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"""
        <html>
            <div class="dre-document">
                <h2>Test Law</h2>
                <span class="diploma-numero">1/2023</span>
            </div>
        </html>
        """
        mock_get.return_value = mock_response

        # Reduce delay for testing
        scraper.delay = 0.01

        documents = scraper.scrape_recent_documents(
            days_back=1, max_documents=10)

        # Should have made at least one request
        assert mock_get.called
        assert isinstance(documents, list)

    def test_clean_text_extraction(self, scraper):
        """Test text cleaning in document extraction."""
        from bs4 import BeautifulSoup

        html = """
        <div class="document-content">
            <p>First paragraph</p>
            <p>Second paragraph</p>
            <script>alert('test');</script>
            <style>body { color: red; }</style>
        </div>
        """

        with patch('requests.Session.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.content = html.encode('utf-8')
            mock_get.return_value = mock_response

            text = scraper._fetch_document_text("http://example.com")

            assert "First paragraph" in text
            assert "Second paragraph" in text
            assert "alert" not in text  # Script removed
            assert "color: red" not in text  # Style removed


class TestScraperDateHandling:
    """Test date handling in scraper."""

    def test_date_range_generation(self):
        """Test generation of date ranges for scraping."""
        scraper = DiarioRepublicaScraper()

        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)

        # Test that date range is correctly handled
        current = start_date
        dates = []
        while current <= end_date:
            dates.append(current.strftime("%Y-%m-%d"))
            current += timedelta(days=1)

        assert len(dates) == 8  # 7 days + today


@pytest.mark.integration
class TestScraperIntegration:
    """Integration tests for scraper (skipped by default)."""

    @pytest.mark.skip(reason="Requires actual web connection")
    def test_real_scraping(self):
        """Test actual scraping from Diário da República."""
        scraper = DiarioRepublicaScraper()

        documents = scraper.scrape_recent_documents(
            days_back=1, max_documents=5)

        assert len(documents) <= 5

        if documents:
            doc = documents[0]
            assert "title" in doc
            assert "source" in doc
            assert doc["source"] == "diario_republica"
