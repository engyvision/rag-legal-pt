"""Initialize sample data for development and testing."""

import os
import sys
import asyncio
from datetime import datetime
import logging

# Add src to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.common.models import DocumentType, DocumentSource
from src.retrieval_service.core.embeddings import EmbeddingsClient
from src.retrieval_service.core.mongodb import MongoDBClient
from src.retrieval_service.core.config import settings


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Sample Portuguese legal documents
SAMPLE_DOCUMENTS = [
    {
        "title": "Lei n.º 23/2023 - Regime Jurídico das Sociedades Comerciais",
        "text": """
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
        """,
        "document_type": DocumentType.LEI,
        "document_number": "23/2023",
        "publication_date": "2023-05-15",
        "issuing_body": "Assembleia da República",
        "description": "Estabelece o regime jurídico aplicável às sociedades comerciais",
        "category": "legislação_geral",
        "keywords": ["lei", "legislação", "sociedade", "comercial", "empresa", "direito_comercial", "empresarial"],
        "source": DocumentSource.MANUAL,
        "url": "https://dre.pt/exemplo/lei-23-2023",
        "metadata": {
            "scraping_method": "manual",
            "processing_version": "1.0"
        }
    },
    {
        "title": "Decreto-Lei n.º 45/2023 - Código do Trabalho",
        "text": """
PRESIDÊNCIA DO CONSELHO DE MINISTROS

Decreto-Lei n.º 45/2023
de 20 de junho

Procede à alteração do Código do Trabalho

O presente decreto-lei procede à décima alteração ao Código do Trabalho, aprovado pela Lei n.º 7/2009, de 12 de fevereiro.

Artigo 1.º
Objeto

O presente decreto-lei procede à décima alteração ao Código do Trabalho, aprovado pela Lei n.º 7/2009, de 12 de fevereiro.

Artigo 2.º
Alteração ao Código do Trabalho

Os artigos 126.º, 127.º e 238.º do Código do Trabalho passam a ter a seguinte redação:

«Artigo 126.º
Período normal de trabalho

1 - O período normal de trabalho não pode exceder oito horas por dia e quarenta horas por semana.
2 - O período normal de trabalho diário pode ser aumentado até duas horas, sem que a duração do trabalho semanal exceda as quarenta horas.
3 - Nas empresas com regime de laboração contínua ou de turnos, o período normal de trabalho pode ser definido em termos médios.»
        """,
        "document_type": DocumentType.DECRETO_LEI,
        "document_number": "45/2023",
        "publication_date": "2023-06-20",
        "issuing_body": "Presidência do Conselho de Ministros",
        "description": "Procede à alteração do Código do Trabalho",
        "category": "legislação_geral",
        "keywords": ["decreto-lei", "decreto", "legislação", "trabalho", "direito_trabalho", "laboral"],
        "source": DocumentSource.MANUAL,
        "url": "https://dre.pt/exemplo/decreto-lei-45-2023",
        "metadata": {
            "scraping_method": "manual",
            "processing_version": "1.0"
        }
    },
    {
        "title": "Portaria n.º 123/2023 - Regulamentação do Teletrabalho",
        "text": """
MINISTÉRIO DO TRABALHO, SOLIDARIEDADE E SEGURANÇA SOCIAL

Portaria n.º 123/2023
de 10 de julho

Regulamenta o regime de prestação subordinada de teletrabalho

Ao abrigo do disposto no n.º 1 do artigo 166.º do Código do Trabalho, aprovado pela Lei n.º 7/2009, de 12 de fevereiro, manda o Governo, pelo Ministro do Trabalho, Solidariedade e Segurança Social, o seguinte:

Artigo 1.º
Objeto

A presente portaria regulamenta o regime de prestação subordinada de teletrabalho previsto nos artigos 165.º a 171.º do Código do Trabalho.

Artigo 2.º
Acordo de teletrabalho

1 - O acordo de teletrabalho deve conter:
a) Identificação das partes;
b) Indicação da atividade a prestar pelo trabalhador;
c) Indicação do local onde o trabalhador prestará a sua atividade;
d) Período normal de trabalho;
e) Horário de trabalho;
f) Instrumentos de trabalho a utilizar;
g) Forma de controlo da prestação de trabalho.

2 - O acordo deve ainda estabelecer:
a) A propriedade dos instrumentos de trabalho;
b) O responsável pela instalação e manutenção dos mesmos;
c) O pagamento das despesas de consumo e de utilização dos instrumentos de trabalho.
        """,
        "document_type": DocumentType.PORTARIA,
        "document_number": "123/2023",
        "publication_date": "2023-07-10",
        "issuing_body": "Ministério do Trabalho, Solidariedade e Segurança Social",
        "description": "Regulamenta o regime de prestação subordinada de teletrabalho",
        "category": "regulamentação_setorial",
        "keywords": ["portaria", "regulamento", "trabalho", "direito_trabalho", "laboral"],
        "source": DocumentSource.MANUAL,
        "url": "https://dre.pt/exemplo/portaria-123-2023",
        "metadata": {
            "scraping_method": "manual",
            "processing_version": "1.0"
        }
    }
]


async def init_sample_data():
    """Initialize sample data in MongoDB."""
    logger.info("Initializing sample data...")

    # Initialize clients
    mongodb_client = MongoDBClient()
    embeddings_client = EmbeddingsClient()

    try:
        # Connect to MongoDB
        mongodb_client.connect()

        # Clear existing sample data
        if os.getenv("CLEAR_EXISTING_DATA", "false").lower() == "true":
            logger.info("Clearing existing data...")
            await mongodb_client.async_db[
                settings.mongodb_collection_documents
            ].delete_many({"source": DocumentSource.MANUAL})

            await mongodb_client.async_db[
                settings.mongodb_collection_vectors
            ].delete_many({})

        # Insert sample documents
        for doc_data in SAMPLE_DOCUMENTS:
            logger.info(f"Processing document: {doc_data['title']}")

            # Create document
            document = {
                **doc_data,
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }

            # Insert document
            doc_id = await mongodb_client.insert_document(document)
            logger.info(f"Inserted document with ID: {doc_id}")

            # Create chunks and embeddings
            text = doc_data["text"]
            chunks = embeddings_client.chunk_text(text)

            logger.info(f"Created {len(chunks)} chunks")

            # Generate embeddings
            chunk_texts = [chunk["text"] for chunk in chunks]
            embeddings = await embeddings_client.agenerate_embeddings_batch(
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
                        "issuing_body": doc_data["issuing_body"]
                    },
                    "created_at": datetime.now()
                }

                await mongodb_client.insert_vector(vector_doc)

            logger.info(f"Created {len(chunks)} vectors for document")

        # Create text indexes
        logger.info("Creating text indexes...")
        docs_collection = mongodb_client.db[
            settings.mongodb_collection_documents
        ]
        docs_collection.create_index([("title", "text"), ("text", "text")])

        logger.info("Sample data initialization completed!")

        # Display statistics
        doc_count = await mongodb_client.async_db[
            settings.mongodb_collection_documents
        ].count_documents({})

        vector_count = await mongodb_client.async_db[
            settings.mongodb_collection_vectors
        ].count_documents({})

        logger.info(f"Total documents: {doc_count}")
        logger.info(f"Total vectors: {vector_count}")

    except Exception as e:
        logger.error(f"Error initializing sample data: {e}")
        raise

    finally:
        mongodb_client.close()


if __name__ == "__main__":
    asyncio.run(init_sample_data())
