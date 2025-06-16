"""Verify that all components are properly set up."""

import os
import sys
from pymongo import MongoClient
from google.cloud import aiplatform
from google.cloud import storage
from dotenv import load_dotenv
import logging

# Add src to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


def check_env_variables():
    """Check if all required environment variables are set."""
    print("\n=== Checking Environment Variables ===")

    required_vars = [
        "GOOGLE_CLOUD_PROJECT",
        "MONGODB_URI",
        "MONGODB_DATABASE",
        "GCS_BUCKET_NAME",
        "VERTEX_AI_LOCATION"
    ]

    missing = []
    for var in required_vars:
        value = os.getenv(var)
        if value:
            print(f"✅ {var}: {'*' * 10} (set)")
        else:
            print(f"❌ {var}: NOT SET")
            missing.append(var)

    return len(missing) == 0


def check_google_cloud():
    """Check Google Cloud connection and services."""
    print("\n=== Checking Google Cloud ===")

    try:
        # Check credentials
        creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if creds_path and os.path.exists(creds_path):
            print(f"✅ Service account credentials found: {creds_path}")
        else:
            print("⚠️  No service account credentials file found")
            print("   Using application default credentials")

        # Initialize Vertex AI
        project = os.getenv("GOOGLE_CLOUD_PROJECT")
        location = os.getenv("VERTEX_AI_LOCATION", "us-central1")

        aiplatform.init(project=project, location=location)
        print(f"✅ Vertex AI initialized for project: {project}")

        # Check Cloud Storage
        storage_client = storage.Client(project=project)
        bucket_name = os.getenv("GCS_BUCKET_NAME")

        try:
            bucket = storage_client.bucket(bucket_name)
            bucket.reload()  # This will fail if bucket doesn't exist
            print(f"✅ Cloud Storage bucket exists: {bucket_name}")
        except Exception as e:
            print(f"❌ Cloud Storage bucket not found: {bucket_name}")
            print(
                f"   Create it with: gsutil mb -p {project} gs://{bucket_name}")

        return True

    except Exception as e:
        print(f"❌ Google Cloud error: {e}")
        return False


def check_mongodb():
    """Check MongoDB connection and setup."""
    print("\n=== Checking MongoDB Atlas ===")

    try:
        # Connect to MongoDB
        client = MongoClient(os.getenv("MONGODB_URI"))
        db = client[os.getenv("MONGODB_DATABASE", "legal_assistant")]

        # Test connection
        client.admin.command('ping')
        print("✅ Connected to MongoDB Atlas")

        # Check collections
        collections = db.list_collection_names()
        required_collections = ["documents", "vectors", "queries"]

        for coll in required_collections:
            if coll in collections:
                count = db[coll].count_documents({})
                print(f"✅ Collection '{coll}' exists ({count} documents)")
            else:
                print(f"❌ Collection '{coll}' not found")
                print("   Run: python scripts/setup_mongodb.py")

        # Check for vector search index
        print("\n=== Checking Vector Search Index ===")
        try:
            # Note: list_search_indexes might not be available in all pymongo versions
            # This is a basic check
            indexes = list(db.vectors.list_indexes())
            print(f"ℹ️  Regular indexes found: {len(indexes)}")
            print("⚠️  Vector search index must be created manually in Atlas UI")
            print("   See instructions in MongoDB Atlas Setup Guide")
        except Exception as e:
            print("ℹ️  Cannot programmatically verify vector search index")
            print("   Please check manually in MongoDB Atlas UI")

        client.close()
        return True

    except Exception as e:
        print(f"❌ MongoDB connection error: {e}")
        print("\nPossible issues:")
        print("- Check your MONGODB_URI in .env")
        print("- Ensure IP whitelist includes your IP")
        print("- Verify username and password")
        return False


def check_sample_data():
    """Check if sample data exists."""
    print("\n=== Checking Sample Data ===")

    try:
        client = MongoClient(os.getenv("MONGODB_URI"))
        db = client[os.getenv("MONGODB_DATABASE", "legal_assistant")]

        doc_count = db.documents.count_documents({})
        vector_count = db.vectors.count_documents({})

        if doc_count > 0:
            print(f"✅ Found {doc_count} documents")
        else:
            print("ℹ️  No documents found")
            print("   Run: python scripts/init_data.py")

        if vector_count > 0:
            print(f"✅ Found {vector_count} vectors")
        else:
            print("ℹ️  No vectors found")
            print("   Run: python scripts/init_data.py")

        # Show sample document
        if doc_count > 0:
            sample = db.documents.find_one()
            print(f"\nSample document: {sample.get('title', 'No title')}")

        client.close()
        return True

    except Exception as e:
        print(f"❌ Error checking sample data: {e}")
        return False


def main():
    """Run all checks."""
    print("🔍 Portuguese Legal Assistant - Setup Verification\n")

    all_good = True

    # Check environment variables
    if not check_env_variables():
        all_good = False
        print("\n⚠️  Please set all required environment variables in .env")

    # Check Google Cloud
    if not check_google_cloud():
        all_good = False
        print("\n⚠️  Google Cloud setup incomplete")

    # Check MongoDB
    if not check_mongodb():
        all_good = False
        print("\n⚠️  MongoDB setup incomplete")

    # Check sample data
    check_sample_data()

    # Summary
    print("\n" + "="*50)
    if all_good:
        print("✅ Setup verification complete!")
        print("\nNext steps:")
        print("1. Create vector search index in MongoDB Atlas UI")
        print("2. Run: python scripts/init_data.py (if not done)")
        print("3. Test vector search: python scripts/test_vector_search.py")
        print("4. Start the application:")
        print("   - python -m src.retrieval_service.main")
        print("   - streamlit run src/frontend_service/app.py")
    else:
        print("❌ Setup incomplete. Please fix the issues above.")
        print("\nRefer to:")
        print("- QUICKSTART.md for setup instructions")
        print("- MongoDB Atlas Setup Guide for detailed MongoDB steps")

    print("="*50)


if __name__ == "__main__":
    main()
