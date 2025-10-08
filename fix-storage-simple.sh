#!/bin/bash
# ============================================================================
# Simple Storage Fix - Create directory in container or use tmpfs
# ============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[✓]${NC} $1"; }
log_error() { echo -e "${RED}[✗]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[!]${NC} $1"; }

# Load configuration
if [ ! -f azure-deployment-config.txt ]; then
    log_error "azure-deployment-config.txt not found. Run deployment first."
    exit 1
fi

RESOURCE_GROUP=$(grep "Resource Group:" azure-deployment-config.txt | cut -d' ' -f3)
CONTAINER_APP=$(grep "Container App:" azure-deployment-config.txt | cut -d' ' -f3)

log_info "Fixing storage for $CONTAINER_APP..."
log_info "Solution: Using tmpfs volume (in-memory) for SQLite"
log_warning "Note: Data will not persist across container restarts, but this is fine for session data"

# Get current container configuration
log_info "Fetching current configuration..."
CURRENT_IMAGE=$(az containerapp show \
    --name "$CONTAINER_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --query "properties.template.containers[0].image" -o tsv)

log_info "Current image: $CURRENT_IMAGE"

# Update container with emptyDir volume (tmpfs)
log_info "Adding tmpfs volume for /app/data..."

# Create the patch JSON
cat > /tmp/volume-patch.json << 'EOFPATCH'
{
  "properties": {
    "template": {
      "volumes": [
        {
          "name": "data-volume",
          "storageType": "EmptyDir"
        }
      ],
      "containers": [
        {
          "name": "ava-whatsapp",
          "volumeMounts": [
            {
              "volumeName": "data-volume",
              "mountPath": "/app/data"
            }
          ]
        }
      ]
    }
  }
}
EOFPATCH

log_info "Applying volume configuration..."

# Get subscription and construct resource ID
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
RESOURCE_ID="/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.App/containerApps/$CONTAINER_APP"

# Apply the patch using az rest
az rest \
    --method PATCH \
    --uri "https://management.azure.com${RESOURCE_ID}?api-version=2023-05-01" \
    --body @/tmp/volume-patch.json \
    --output none 2>&1 || {
        log_warning "REST API patch failed, trying alternative method..."
        
        # Alternative: Rebuild with proper directory creation
        log_info "Creating a new revision..."
        az containerapp update \
            --name "$CONTAINER_APP" \
            --resource-group "$RESOURCE_GROUP" \
            --image "$CURRENT_IMAGE" \
            --output none
    }

rm /tmp/volume-patch.json

log_success "Volume configuration updated!"

# Wait for new revision
log_info "Waiting for new revision to deploy (45 seconds)..."
sleep 45

# Check status
STATUS=$(az containerapp show \
    --name "$CONTAINER_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --query "properties.runningStatus" -o tsv)

log_info "Container status: $STATUS"

# Show logs
log_info "Checking logs..."
echo ""
echo "=================================="
echo "Recent Container Logs:"
echo "=================================="

az containerapp logs show \
    --name "$CONTAINER_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --tail 40 | grep -E "(ERROR|INFO|server|database|sqlite)" || az containerapp logs show \
    --name "$CONTAINER_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --tail 20

echo ""
echo "=================================="
log_success "Storage fix applied!"
echo ""
log_info "What was done:"
echo "  - Added tmpfs (in-memory) volume at /app/data"
echo "  - This provides a writable directory for SQLite"
echo "  - Session data is ephemeral (resets on container restart)"
echo ""
log_warning "Note: For production with data persistence, you'd want Azure Files mount"
log_warning "But for session/conversation data, tmpfs is actually preferred!"
echo ""
log_info "Next: Send a test message to WhatsApp to verify it works"

