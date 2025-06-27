"""Article-based chunking for Portuguese legal documents."""

import re
import logging
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Article:
    """Represents an article in a legal document."""

    number: str
    title: str
    content: str
    full_text: str  # Combined title + content
    char_count: int

    @property
    def is_empty(self) -> bool:
        return len(self.content.strip()) == 0


class LegalDocumentChunker:
    """Chunks legal documents based on article structure."""

    def __init__(self, max_chunk_size: int = 1000, min_chunk_size: int = 200):
        self.max_chunk_size = max_chunk_size
        self.min_chunk_size = min_chunk_size

        # Portuguese article patterns (based on real scraped content)
        self.article_patterns = [
            # From diariodarepublica.pt scraper (=== wrapper format)
            r"=== (ARTIGO\s+\d+\.º) ===\s*\n([^\n]*)",  # === ARTIGO 1.º ===\nTítulo
            r"=== (ARTIGO\s+[IVXLCDM]+) ===\s*\n([^\n]*)", # === ARTIGO I ===\nTítulo
            # Standard patterns without wrapper (fallback)
            r"(Artigo\s+\d+\.º)\s*\n([^\n]*)",  # Artigo 1.º\nTítulo
            r"(Art\.\s+\d+\.º)\s*\n([^\n]*)",   # Art. 1.º\nTítulo
            r"(ARTIGO\s+\d+\.º)\s*\n([^\n]*)", # ARTIGO 1.º\nTítulo
            r"(Artigo\s+\d+\.º)\s*[-–—]\s*([^\n]*)", # Artigo 1.º - Título
        ]

        # Patterns for other structural elements
        self.chapter_patterns = [
            r"(?:^|\n)(CAPÍTULO\s+[IVXLCDM]+)\s*\n([^\n]+)?",
            r"(?:^|\n)(TÍTULO\s+[IVXLCDM]+)\s*\n([^\n]+)?",
            r"(?:^|\n)(SECÇÃO\s+[IVXLCDM]+)\s*\n([^\n]+)?",
        ]

        # Combined pattern for article detection
        self.article_pattern = re.compile("|".join(self.article_patterns), re.IGNORECASE | re.MULTILINE)
        self.structural_pattern = re.compile(
            "|".join(self.chapter_patterns + self.article_patterns), re.IGNORECASE | re.MULTILINE
        )

    def extract_articles(self, text: str) -> Tuple[str, List[Article]]:
        """Extract preamble and articles from the document text."""
        articles = []

        # Find all structural elements
        matches = list(self.structural_pattern.finditer(text))

        if not matches:
            # No articles found, treat as single chunk
            return text, []

        # Extract preamble (text before first article)
        first_match = matches[0]
        preamble = text[: first_match.start()].strip()

        # Process each match
        for i, match in enumerate(matches):
            # Get matched groups (different patterns have different groups)
            groups = [g for g in match.groups() if g is not None]

            if len(groups) >= 1:
                article_num = groups[0].strip()
                article_title = groups[1].strip() if len(groups) > 1 else ""

                # Check if this is an article (not chapter/title/section)
                is_article = any(
                    re.search(pattern, f"{article_num}\n{article_title}", re.IGNORECASE)
                    for pattern in self.article_patterns
                )

                if is_article:
                    # Get content until next structural element or end of text
                    start_pos = match.end()
                    end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(text)

                    content = text[start_pos:end_pos].strip()

                    # Create article object
                    full_text = f"{article_num}"
                    if article_title:
                        full_text += f"\n{article_title}"
                    full_text += f"\n{content}"

                    article = Article(
                        number=article_num,
                        title=article_title,
                        content=content,
                        full_text=full_text,
                        char_count=len(full_text),
                    )

                    if not article.is_empty:
                        articles.append(article)

        return preamble, articles

    def create_chunks_from_articles(self, articles: List[Article]) -> List[Dict[str, Any]]:
        """Create chunks from articles, combining small articles when possible."""
        chunks = []
        current_chunk_articles = []
        current_chunk_size = 0

        for article in articles:
            # If single article exceeds max size, it gets its own chunk
            if article.char_count > self.max_chunk_size:
                # First, save any accumulated articles
                if current_chunk_articles:
                    chunks.append(self._create_chunk_dict(current_chunk_articles))
                    current_chunk_articles = []
                    current_chunk_size = 0

                # Add the large article as its own chunk
                chunks.append(self._create_chunk_dict([article]))

            # If adding this article would exceed max size, save current chunk
            elif current_chunk_size + article.char_count > self.max_chunk_size:
                if current_chunk_articles:
                    chunks.append(self._create_chunk_dict(current_chunk_articles))

                # Start new chunk with this article
                current_chunk_articles = [article]
                current_chunk_size = article.char_count

            # Otherwise, add article to current chunk
            else:
                current_chunk_articles.append(article)
                current_chunk_size += article.char_count

        # Don't forget the last chunk
        if current_chunk_articles:
            chunks.append(self._create_chunk_dict(current_chunk_articles))

        return chunks

    def _create_chunk_dict(self, articles: List[Article]) -> Dict[str, Any]:
        """Create a chunk dictionary from a list of articles."""
        # Combine article texts
        combined_text = "\n\n".join(article.full_text for article in articles)

        # Create metadata
        article_numbers = [a.number for a in articles]
        metadata = {
            "chunk_type": "articles",
            "article_count": len(articles),
            "article_numbers": article_numbers,
            "first_article": article_numbers[0] if article_numbers else None,
            "last_article": article_numbers[-1] if article_numbers else None,
        }

        return {"text": combined_text, "metadata": metadata, "char_count": len(combined_text)}

    def chunk_legal_document(self, text: str) -> List[Dict[str, Any]]:
        """
        Main method to chunk a legal document by articles.

        Returns list of chunks with metadata about which articles they contain.
        """
        chunks = []
        chunk_index = 0

        # Extract preamble and articles
        preamble, articles = self.extract_articles(text)

        # Handle preamble (intro text before first article)
        if preamble and len(preamble.strip()) > self.min_chunk_size:
            # Split preamble if it's too large
            if len(preamble) > self.max_chunk_size:
                preamble_chunks = self._chunk_text_fallback(preamble, is_preamble=True)
                for pc in preamble_chunks:
                    pc["chunk_index"] = chunk_index
                    chunks.append(pc)
                    chunk_index += 1
            else:
                chunks.append(
                    {
                        "text": preamble,
                        "metadata": {"chunk_type": "preamble", "article_count": 0, "article_numbers": []},
                        "char_count": len(preamble),
                        "chunk_index": chunk_index,
                    }
                )
                chunk_index += 1

        # If no articles found, fall back to character-based chunking
        if not articles:
            logger.warning("No articles found in document, using fallback chunking")
            fallback_chunks = self._chunk_text_fallback(text)
            for fc in fallback_chunks:
                fc["chunk_index"] = chunk_index
                chunks.append(fc)
                chunk_index += 1
            return chunks

        # Create chunks from articles
        article_chunks = self.create_chunks_from_articles(articles)

        # Add chunk indices and positions
        for chunk in article_chunks:
            chunk["chunk_index"] = chunk_index
            chunk_index += 1
            chunks.append(chunk)

        logger.info(f"Created {len(chunks)} chunks from {len(articles)} articles")

        return chunks

    def _chunk_text_fallback(self, text: str, is_preamble: bool = False) -> List[Dict[str, Any]]:
        """Fallback to character-based chunking when article structure isn't found."""
        chunks = []

        # Simple character-based chunking
        for i in range(0, len(text), self.max_chunk_size):
            chunk_text = text[i : i + self.max_chunk_size]

            # Try to break at sentence boundary
            if i + self.max_chunk_size < len(text):
                last_period = chunk_text.rfind(".")
                last_newline = chunk_text.rfind("\n")
                split_point = max(last_period, last_newline)

                if split_point > self.max_chunk_size * 0.7:  # Only split if we keep >70%
                    chunk_text = chunk_text[: split_point + 1]

            chunks.append(
                {
                    "text": chunk_text.strip(),
                    "metadata": {
                        "chunk_type": "preamble" if is_preamble else "fallback",
                        "article_count": 0,
                        "article_numbers": [],
                    },
                    "char_count": len(chunk_text.strip()),
                }
            )

        return chunks


# Integration with existing EmbeddingsClient
def chunk_legal_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> List[Dict[str, Any]]:
    """
    Enhanced chunking function that uses article-based chunking for legal documents.

    This can be integrated into the existing EmbeddingsClient.
    """
    chunker = LegalDocumentChunker(max_chunk_size=chunk_size)

    # Get article-based chunks
    chunks = chunker.chunk_legal_document(text)

    # Convert to format expected by existing code
    formatted_chunks = []
    start_char = 0

    for chunk in chunks:
        chunk_text = chunk["text"]
        end_char = start_char + len(chunk_text)

        formatted_chunk = {
            "text": chunk_text,
            "start_char": start_char,
            "end_char": end_char,
            "chunk_index": chunk["chunk_index"],
            "metadata": chunk["metadata"],
        }

        formatted_chunks.append(formatted_chunk)
        start_char = end_char + 2  # Account for \n\n between chunks

    return formatted_chunks


# Example usage
if __name__ == "__main__":
    # Example legal document text
    sample_text = """
    ASSEMBLEIA DA REPÚBLICA
    
    Lei n.º 23/2023
    de 15 de maio
    
    Regime Jurídico das Sociedades Comerciais
    
    A Assembleia da República decreta, nos termos da alínea c) do artigo 161.º da Constituição, o seguinte:
    
    CAPÍTULO I
    Disposições gerais
    
    Artigo 1.º
    Objeto
    
    A presente lei estabelece o regime jurídico aplicável às sociedades comerciais, regulando a sua constituição, funcionamento, modificação e extinção.
    
    Artigo 2.º
    Tipos de sociedades
    
    1 - As sociedades comerciais devem adotar um dos seguintes tipos:
    a) Sociedade em nome coletivo;
    b) Sociedade por quotas;
    c) Sociedade anónima;
    d) Sociedade em comandita simples;
    e) Sociedade em comandita por ações.
    
    2 - As sociedades que não adotem um dos tipos referidos no número anterior são nulas.
    
    Artigo 3.º
    Capacidade
    
    As sociedades comerciais gozam de personalidade jurídica e têm capacidade de direitos e obrigações necessária ou conveniente à prossecução do seu objeto, excetuadas aquelas que lhes sejam vedadas por lei ou sejam inseparáveis da personalidade singular.
    
    Artigo 4.º
    Denominação social
    
    1 - A denominação das sociedades comerciais deve conter:
    a) O tipo de sociedade;
    b) O objeto social, quando exigido por lei.
    
    2 - A denominação não pode conter expressões que possam induzir em erro sobre o tipo, objeto ou atividade da sociedade.
    """

    # Test the chunker
    chunker = LegalDocumentChunker(max_chunk_size=500)
    chunks = chunker.chunk_legal_document(sample_text)

    print(f"Total chunks created: {len(chunks)}")
    for i, chunk in enumerate(chunks):
        print(f"\n--- Chunk {i + 1} ---")
        print(f"Type: {chunk['metadata']['chunk_type']}")
        print(f"Articles: {chunk['metadata']['article_numbers']}")
        print(f"Size: {chunk['char_count']} chars")
        print(f"Preview: {chunk['text'][:100]}...")
