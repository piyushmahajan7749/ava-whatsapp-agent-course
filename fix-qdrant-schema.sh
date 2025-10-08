#!/bin/bash
# Recreate Qdrant collection with user_id index

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[✓]${NC} $1"; }
log_error() { echo -e "${RED}[✗]${NC} $1"; }

echo ""
echo "========================================"
echo "  Fix Qdrant Schema (user_id index)"
echo "========================================"
echo ""

# Check environment variables
if [ -z "$QDRANT_URL" ] || [ -z "$QDRANT_API_KEY" ]; then
    log_info "Loading credentials from .env file..."
    export QDRANT_URL=$(grep QDRANT_URL .env | cut -d'=' -f2- | tr -d '"')
    export QDRANT_API_KEY=$(grep QDRANT_API_KEY .env | cut -d'=' -f2- | tr -d '"')
fi

log_info "Qdrant URL: $QDRANT_URL"
log_info "Recreating collection with user_id index..."
echo ""

uv run python << 'EOF'
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PayloadSchemaType
from sentence_transformers import SentenceTransformer
import os
import sys

# Load credentials
url = os.getenv("QDRANT_URL")
api_key = os.getenv("QDRANT_API_KEY")

if not url or not api_key:
    print("✗ Error: QDRANT_URL and QDRANT_API_KEY must be set")
    sys.exit(1)

print(f"Connecting to: {url}")

try:
    client = QdrantClient(url=url, api_key=api_key)
    model = SentenceTransformer("all-MiniLM-L6-v2")
    
    collection_name = "long_term_memory"
    
    # Check if collection exists
    try:
        existing = client.get_collection(collection_name)
        print(f"✓ Collection '{collection_name}' exists")
        print(f"  Points: {existing.points_count}")
        
        # Delete old collection
        client.delete_collection(collection_name)
        print(f"✓ Deleted old collection")
    except Exception as e:
        print(f"Collection '{collection_name}' does not exist (will create new)")
    
    # Create new collection with proper configuration
    print(f"Creating collection with user_id index...")
    sample_embedding = model.encode("sample text")
    
    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(
            size=len(sample_embedding),
            distance=Distance.COSINE,
        ),
    )
    print(f"✓ Collection created")
    
    # Create payload index for user_id
    client.create_payload_index(
        collection_name=collection_name,
        field_name="user_id",
        field_schema=PayloadSchemaType.KEYWORD,
    )
    print(f"✓ user_id keyword index created")
    
    # Verify the index
    info = client.get_collection(collection_name)
    print(f"\nCollection info:")
    print(f"  Name: {info.config.params.vectors.size} dimensions")
    print(f"  Points: {info.points_count}")
    
    if hasattr(info, 'payload_schema') and info.payload_schema:
        print(f"\nPayload indexes:")
        for field, schema in info.payload_schema.items():
            print(f"  - {field}: {schema.data_type if hasattr(schema, 'data_type') else schema}")
    
    print(f"\n✓ Collection ready for user-specific memories!")
    sys.exit(0)
    
except Exception as e:
    print(f"✗ Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
EOF

if [ $? -eq 0 ]; then
    log_success "Qdrant schema fixed successfully!"
    echo ""
    log_info "Next steps:"
    echo "  1. Update Azure deployment: make azure-update"
    echo "  2. Test with WhatsApp message"
    echo "  3. Check logs: make azure-logs"
else
    log_error "Failed to fix Qdrant schema"
    exit 1
fi

