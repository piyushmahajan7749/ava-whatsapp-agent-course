#!/bin/bash
# ============================================================================
# Azure Update Script - Quick redeploy after code changes
# ============================================================================

set -e

# Load saved configuration
if [ ! -f azure-deployment-config.txt ]; then
    echo "Error: azure-deployment-config.txt not found!"
    echo "Run ./deploy-azure-simple.sh first to do initial deployment"
    exit 1
fi

# Extract configuration
RESOURCE_GROUP=$(grep "Resource Group:" azure-deployment-config.txt | cut -d' ' -f3)
CONTAINER_APP=$(grep "Container App:" azure-deployment-config.txt | cut -d' ' -f3)
ACR_NAME=$(grep "Container Registry:" azure-deployment-config.txt | cut -d' ' -f3 | cut -d'.' -f1)

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[✓]${NC} $1"; }

echo "============================================"
echo "  Azure Quick Update"
echo "============================================"
echo "Resource Group: $RESOURCE_GROUP"
echo "Container App:  $CONTAINER_APP"
echo "Registry:       $ACR_NAME"
echo "============================================"
echo ""

# Build and push new image
log_info "Building new Docker image..."
az acr build \
    --registry "$ACR_NAME" \
    --image ava-whatsapp:latest \
    --image ava-whatsapp:$(git rev-parse --short HEAD 2>/dev/null || date +%s) \
    --file Dockerfile \
    . \
    --output table

log_success "Image built and pushed"

# Container App will auto-update, but we can force it
log_info "Triggering container app update..."
ACR_SERVER=$(az acr show --name "$ACR_NAME" --query loginServer -o tsv)

az containerapp update \
    --name "$CONTAINER_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --image "$ACR_SERVER/ava-whatsapp:latest" \
    --output none

log_success "Container app updated"

# Get URL
APP_URL=$(az containerapp show \
    --name "$CONTAINER_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --query properties.configuration.ingress.fqdn \
    -o tsv)

echo ""
log_success "Update complete! Application URL: https://$APP_URL"
echo ""
log_info "To view logs:"
echo "  az containerapp logs show --name $CONTAINER_APP --resource-group $RESOURCE_GROUP --follow"

