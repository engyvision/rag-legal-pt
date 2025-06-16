"""Setup MongoDB Atlas for the Portuguese Legal Assistant."""

import os
import sys
from pymongo import MongoClient, ASCENDING, TEXT
from dotenv import load_dotenv
import logging

# Add src to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


def setup_mongodb():
    """Setup MongoDB Atlas collections and indexes."""

    # Get MongoDB URI
    mongodb_uri = os.getenv("MONGODB_URI")
    if not mongodb_uri:
        logger.error("MONGODB_URI not set in environment variables")
        return False

    try:
        # Connect to MongoDB
        client = MongoClient(mongodb_uri)
        db = client[os.getenv("MONGODB_DATABASE", "legal_assistant")]

        # Test connection
        client.admin.command('ping')
        logger.info("Connected to MongoDB Atlas")

        # Create collections
        collections = {
            "documents": {
                "validator": {
                    "$jsonSchema": {
                        "bsonType": "object",
                        "required": ["title", "text", "source", "created_at"],
                        "properties": {
                            "title": {"bsonType": "string"},
                            "text": {"bsonType": "string"},
                            "source": {"bsonType": "string"},
                            "document_type": {"bsonType": "string"},
                            "document_number": {"bsonType": "string"},
                            "publication_date": {"bsonType": "string"},
                            "url": {"bsonType": "string"},
                            "metadata": {"bsonType": "object"},
                            "created_at": {"bsonType": "date"},
                            "updated_at": {"bsonType": "date"}
                        }
                    }
                }
            },
            "vectors": {
                "validator": {
                    "$jsonSchema": {
                        "bsonType": "object",
                        "required": ["document_id", "text", "embedding", "created_at"],
                        "properties": {
                            "document_id": {"bsonType": "objectId"},
                            "text": {"bsonType": "string"},
                            "embedding": {
                                "bsonType": "array",
                                "items": {"bsonType": "double"}
                            },
                            "chunk_index": {"bsonType": "int"},
                            "metadata": {"bsonType": "object"},
                            "created_at": {"bsonType": "date"}
                        }
                    }
                }
            },
            "queries": {
                "validator": {
                    "$jsonSchema": {
                        "bsonType": "object",
                        "required": ["query", "timestamp"],
                        "properties": {
                            "query": {"bsonType": "string"},
                            "response": {"bsonType": "string"},
                            "sources": {"bsonType": "array"},
                            "timestamp": {"bsonType": "date"},
                            "user_feedback": {"bsonType": "object"}
                        }
                    }
                }
            }
        }

        # Create collections with validators
        for collection_name, options in collections.items():
            try:
                db.create_collection(collection_name, **options)
                logger.info(f"Created collection: {collection_name}")
            except Exception as e:
                if "already exists" in str(e):
                    logger.info(f"Collection {collection_name} already exists")
                else:
                    logger.error(
                        f"Error creating collection {collection_name}: {e}")

        # Create indexes
        logger.info("Creating indexes...")

        # Documents collection indexes
        documents_col = db["documents"]
        documents_col.create_index([("title", TEXT), ("text", TEXT)])
        documents_col.create_index("document_type")
        documents_col.create_index("publication_date")
        documents_col.create_index("created_at")

        # Vectors collection indexes (regular indexes, Atlas Search index created separately)
        vectors_col = db["vectors"]
        vectors_col.create_index("document_id")
        vectors_col.create_index("chunk_index")
        vectors_col.create_index("created_at")

        # Queries collection indexes
        queries_col = db["queries"]
        queries_col.create_index("timestamp")
        queries_col.create_index([("query", TEXT)])

        logger.info("Indexes created successfully")

        # Note about Atlas Vector Search
        logger.info("\n" + "="*50)
        logger.info("IMPORTANT: Vector Search Index Setup")
        logger.info("="*50)
        logger.info(
            "You need to create a Vector Search index manually in MongoDB Atlas:")
        logger.info("1. Go to your MongoDB Atlas cluster")
        logger.info("2. Navigate to the 'Search' tab")
        logger.info("3. Click 'Create Search Index'")
        logger.info("4. Choose 'JSON Editor' configuration method")
        logger.info("5. Select:")
        logger.info("   - Database: legal_assistant")
        logger.info("   - Collection: vectors")
        logger.info("   - Index Name: vector_index")
        logger.info("6. Use this JSON configuration:")
        logger.info("""
{
  "mappings": {
    "dynamic": true,
    "fields": {
      "embedding": {
        "dimensions": 768,
        "similarity": "cosine",
        "type": "knnVector"
      }
    }
  }
}
        """)
        logger.info("7. Click 'Create Search Index' and wait 1-2 minutes")
        logger.info("="*50)

        # Insert sample data (optional)
        if os.getenv("INSERT_SAMPLE_DATA", "false").lower() == "true":
            logger.info("Inserting sample data...")
            sample_doc = {
                "title": "Lei de Teste",
                "text": "Este é um documento de teste para o assistente jurídico.",
                "source": "sample",
                "document_type": "lei",
                "document_number": "TEST-001",
                "publication_date": "2024-01-01",
                "url": "https://example.com",
                "metadata": {"category": "test"},
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
            documents_col.insert_one(sample_doc)
            logger.info("Sample data inserted")

        logger.info("MongoDB setup completed successfully!")
        return True

    except Exception as e:
        logger.error(f"MongoDB setup failed: {e}")
        return False

    finally:
        if 'client' in locals():
            client.close()


if __name__ == "__main__":
    from datetime import datetime
    success = setup_mongodb()
    sys.exit(0 if success else 1)
