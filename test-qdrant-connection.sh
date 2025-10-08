#!/bin/bash
# Test Qdrant connection with provided credentials

QDRANT_URL="$1"
QDRANT_API_KEY="$2"

if [ -z "$QDRANT_URL" ] || [ -z "$QDRANT_API_KEY" ]; then
    echo "Usage: ./test-qdrant-connection.sh <QDRANT_URL> <QDRANT_API_KEY>"
    echo ""
    echo "Or test with .env file:"
    echo "  QDRANT_URL=\$(grep QDRANT_URL .env | cut -d'=' -f2- | tr -d '\"')"
    echo "  QDRANT_API_KEY=\$(grep QDRANT_API_KEY .env | cut -d'=' -f2- | tr -d '\"')"
    echo "  ./test-qdrant-connection.sh \"\$QDRANT_URL\" \"\$QDRANT_API_KEY\""
    exit 1
fi

echo "========================================"
echo "  Qdrant Connection Test"
echo "========================================"
echo "URL: $QDRANT_URL"
echo "API Key: ${QDRANT_API_KEY:0:20}..."
echo "========================================"
echo ""

uv run python << EOF
from qdrant_client import QdrantClient
import sys

url = "$QDRANT_URL"
api_key = "$QDRANT_API_KEY"

print(f"Testing connection to: {url}")
print("")

try:
    client = QdrantClient(url=url, api_key=api_key, timeout=10)
    print("✓ Client initialized")
    
    collections = client.get_collections()
    print(f"✓ Connection successful!")
    print(f"✓ Found {len(collections.collections)} collections")
    print("")
    
    if collections.collections:
        print("Existing collections:")
        for col in collections.collections:
            print(f"  - {col.name}")
    else:
        print("No collections found (this is normal for a new cluster)")
    
    print("")
    print("✓ Qdrant connection is working!")
    sys.exit(0)
    
except Exception as e:
    print(f"✗ Connection failed!")
    print(f"✗ Error: {type(e).__name__}: {e}")
    print("")
    print("Troubleshooting:")
    print("1. Check if cluster exists at https://cloud.qdrant.io/")
    print("2. Verify URL format: https://xxxxx.qdrant.io")
    print("3. Verify API key is correct")
    print("4. Check if cluster is in 'Running' state")
    sys.exit(1)
EOF

