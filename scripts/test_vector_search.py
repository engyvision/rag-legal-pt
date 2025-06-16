"""Test vector search functionality after index creation."""
import os
import sys
import asyncio
import numpy as np

from pymongo import MongoClient
from dotenv import load_dotenv

# Add src to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.retrieval_service.core.mongodb import MongoDBClient
from src.retrieval_service.core.embeddings import EmbeddingsClient
from src.retrieval_service.core.config import settings

# Now import from src

# Load environment variables
load_dotenv()


async def test_vector_search():
    """Test vector search with a sample query."""
    print("🔍 Testing Vector Search Functionality\n")

    # Initialize clients
    mongodb_client = MongoDBClient()
    embeddings_client = EmbeddingsClient()

    try:
        # Connect to MongoDB
        mongodb_client.connect()
        print("✅ Connected to MongoDB Atlas")

        # Check if we have vectors
        vector_count = await mongodb_client.async_db[
            settings.mongodb_collection_vectors
        ].count_documents({})

        if vector_count == 0:
            print("❌ No vectors found in database")
            print("   Run: python scripts/init_data.py")
            return

        print(f"✅ Found {vector_count} vectors in database")

        # Test query
        test_query = "sociedades comerciais"
        print(f"\n📝 Test query: '{test_query}'")

        # Generate embedding for query
        print("🔄 Generating query embedding...")
        query_embedding = await embeddings_client.agenerate_embedding(test_query)
        print(f"✅ Generated embedding (dimension: {len(query_embedding)})")

        # Perform vector search
        print("\n🔍 Performing vector search...")
        try:
            results = await mongodb_client.vector_search(
                query_embedding=query_embedding,
                limit=3
            )

            if results:
                print(
                    f"✅ Vector search successful! Found {len(results)} results:")
                print("\nTop Results:")
                for i, result in enumerate(results, 1):
                    print(f"\n{i}. Score: {result.get('score', 0):.4f}")
                    print(f"   Text: {result.get('text', '')[:100]}...")
                    if 'metadata' in result:
                        print(f"   Metadata: {result['metadata']}")
            else:
                print("⚠️  Vector search returned no results")
                print("   This might mean:")
                print("   - The vector index is still being built (wait 2-3 minutes)")
                print("   - The index name doesn't match 'vector_index'")
                print("   - There's an issue with the index configuration")

        except Exception as e:
            print(f"❌ Vector search failed: {e}")
            print("\nPossible issues:")
            print("1. Vector search index not created yet")
            print("2. Index name doesn't match 'vector_index'")
            print("3. Index is still building (wait 2-3 minutes)")
            print("\nPlease check MongoDB Atlas Search tab")

        # Test with a random vector (should work even without matching content)
        print("\n🔍 Testing with random vector...")
        random_embedding = np.random.rand(settings.embedding_dimensions).tolist()

        try:
            results = await mongodb_client.vector_search(
                query_embedding=random_embedding,
                limit=1
            )
            print("✅ Random vector search worked (index is functional)")
        except Exception as e:
            print(f"❌ Random vector search failed: {e}")
            print("   The vector search index is not properly configured")

    except Exception as e:
        print(f"❌ Error during testing: {e}")

    finally:
        mongodb_client.close()
        print("\n✅ Test complete")


async def check_index_status():
    """Check the status of vector search indexes."""
    print("\n📊 Checking Vector Search Index Status\n")

    try:
        client = MongoClient(os.getenv("MONGODB_URI"))
        db = client[os.getenv("MONGODB_DATABASE", "legal_assistant")]

        # Note: This might not work with all pymongo versions
        # It's mainly for informational purposes
        print("Regular indexes on 'vectors' collection:")
        for index in db.vectors.list_indexes():
            print(f"  - {index['name']}: {index.get('key', {})}")

        print("\n⚠️  Note: Vector search indexes are managed separately")
        print("   Check the MongoDB Atlas UI Search tab for:")
        print("   - Index name: vector_index")
        print("   - Status: Active")
        print("   - Type: vectorSearch")

        client.close()

    except Exception as e:
        print(f"Error checking indexes: {e}")


if __name__ == "__main__":
    print("=" * 50)
    print("MongoDB Atlas Vector Search Test")
    print("=" * 50)

    # Run the async test
    asyncio.run(test_vector_search())

    # Check index status
    asyncio.run(check_index_status())

    print("\n" + "=" * 50)
    print("If vector search failed:")
    print("1. Go to MongoDB Atlas > Search tab")
    print("2. Verify 'vector_index' exists and is Active")
    print("3. Wait 2-3 minutes if just created")
    print("4. Check the index configuration matches the documentation")
    print("=" * 50)
