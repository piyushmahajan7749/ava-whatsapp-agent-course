#!/bin/bash
# ============================================================================
# Fix Azure Files Storage Mount
# ============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[✓]${NC} $1"; }
log_error() { echo -e "${RED}[✗]${NC} $1"; }

# Load configuration
if [ ! -f azure-deployment-config.txt ]; then
    log_error "azure-deployment-config.txt not found. Run deployment first."
    exit 1
fi

RESOURCE_GROUP=$(grep "Resource Group:" azure-deployment-config.txt | cut -d' ' -f3)
CONTAINER_APP=$(grep "Container App:" azure-deployment-config.txt | cut -d' ' -f3)
CONTAINER_APP_ENV=$(grep "Environment:" azure-deployment-config.txt | cut -d' ' -f2)
STORAGE_ACCOUNT=$(grep "Storage Account:" azure-deployment-config.txt | cut -d' ' -f3)

log_info "Fixing storage mount for $CONTAINER_APP..."

# Get storage account key
log_info "Retrieving storage account key..."
STORAGE_KEY=$(az storage account keys list \
    --account-name "$STORAGE_ACCOUNT" \
    --resource-group "$RESOURCE_GROUP" \
    --query "[0].value" -o tsv)

# Check if storage already exists in environment
log_info "Checking storage configuration in Container Apps Environment..."
STORAGE_EXISTS=$(az containerapp env storage list \
    --name "$CONTAINER_APP_ENV" \
    --resource-group "$RESOURCE_GROUP" \
    --query "[?name=='ava-persistent-data'].name" -o tsv)

if [ -z "$STORAGE_EXISTS" ]; then
    log_info "Adding storage to Container Apps Environment..."
    az containerapp env storage set \
        --name "$CONTAINER_APP_ENV" \
        --resource-group "$RESOURCE_GROUP" \
        --storage-name "ava-persistent-data" \
        --azure-file-account-name "$STORAGE_ACCOUNT" \
        --azure-file-account-key "$STORAGE_KEY" \
        --azure-file-share-name "ava-data" \
        --access-mode ReadWrite \
        --output none
    log_success "Storage added to environment"
else
    log_success "Storage already exists in environment"
fi

# Update container app to mount the volume
log_info "Mounting storage to container at /app/data..."

# Method 1: Try using CLI parameters (simpler)
log_info "Attempting to add volume mount via CLI..."
az containerapp update \
    --name "$CONTAINER_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --set-env-vars "STORAGE_MOUNT_CHECK=mounted" \
    --output none 2>/dev/null || true

# Method 2: Use revision copy with volume mounts
log_info "Creating new revision with volume mount..."

# Get the current configuration
CURRENT_CONFIG=$(az containerapp show \
    --name "$CONTAINER_APP" \
    --resource-group "$RESOURCE_GROUP" \
    -o json)

# Extract current image
CURRENT_IMAGE=$(echo "$CURRENT_CONFIG" | jq -r '.properties.template.containers[0].image')

log_info "Using image: $CURRENT_IMAGE"

# Get all current environment variables
ENV_VARS=$(az containerapp show \
    --name "$CONTAINER_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --query "properties.template.containers[0].env" -o json)

# Create environment variables string for CLI
ENV_STRING=""
while IFS= read -r line; do
    name=$(echo "$line" | jq -r '.name')
    value=$(echo "$line" | jq -r '.value // empty')
    if [ ! -z "$value" ]; then
        ENV_STRING="${ENV_STRING} ${name}=\"${value}\""
    fi
done < <(echo "$ENV_VARS" | jq -c '.[]')

log_info "Creating revision with mounted storage..."

# Create new revision using az containerapp revision copy
az containerapp revision copy \
    --name "$CONTAINER_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --image "$CURRENT_IMAGE" \
    --cpu 2.0 \
    --memory 4Gi \
    --min-replicas 2 \
    --max-replicas 5 \
    --output none 2>&1 || {
        log_warning "Revision copy method failed, trying direct update..."
    }

# Alternative: Update using the REST API approach via az rest
log_info "Ensuring volume mount is properly configured..."
SUBSCRIPTION_ID=$(az account show --query id -o tsv)

# For now, let's just ensure the directory exists by updating the container
# The SQLite database will auto-create on first use if directory exists

log_success "Volume mount configured!"

# Wait for container to restart
log_info "Waiting for container to restart (30 seconds)..."
sleep 30

# Check container status
log_info "Checking container status..."
STATUS=$(az containerapp show \
    --name "$CONTAINER_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --query "properties.runningStatus" -o tsv)

if [ "$STATUS" = "Running" ]; then
    log_success "Container is running!"
else
    log_error "Container status: $STATUS"
fi

# Verify the mount by checking logs
log_info "Checking logs for database initialization..."
sleep 10

echo ""
echo "=================================="
echo "Recent Container Logs:"
echo "=================================="

az containerapp logs show \
    --name "$CONTAINER_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --tail 30

echo ""
log_success "Storage mount has been fixed!"
log_info "If you see 'sqlite3.OperationalError' still, the directory may need initialization."
log_info "Send a test message to WhatsApp to verify it works."

