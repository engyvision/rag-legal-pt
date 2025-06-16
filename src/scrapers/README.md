# Scrapers Module

This module contains web scrapers for Portuguese legal documents.

## Structure

```
scrapers/
├── main.py                 # Orchestrator that runs scrapers
├── diario_republica.py     # Scraper for diariodarepublica.pt
├── requirements.txt        # Scraper-specific dependencies
└── Dockerfile             # Container for running scrapers
```

## Why This Structure?

- **Simple and flat**: Easy to understand and navigate
- **Modular**: Each scraper is a separate file
- **Extensible**: Easy to add new scrapers (just add a new .py file)
- **MVP-friendly**: No over-engineering for a hackathon project

## Adding a New Scraper

1. Create a new file (e.g., `novo_portal.py`)
2. Implement a scraper class with a common interface
3. Import and use it in `main.py`

Example:

```python
# novo_portal.py
class NovoPortalScraper:
    def scrape_recent_documents(self, days_back=7, max_documents=100):
        # Implementation here
        pass
```

## Running Scrapers

```bash
# Run all daily scrapers
python -m src.scrapers.main daily

# Run historical scraping
python -m src.scrapers.main historical 2023-01-01 2023-12-31

# Using Docker
docker-compose run --rm scraper
```

## Future Improvements

When the MVP is working and you need to scale:

- Add a base scraper class for common functionality
- Implement retry logic and rate limiting
- Add scraper scheduling and monitoring
- Store scraper state for incremental updates
