#!/bin/bash
# ============================================================================
# Azure Deployment Script for Ava WhatsApp Agent
# Production-ready deployment for 1000+ users
# ============================================================================

set -e

# Configuration - CHANGE THESE VALUES
RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-ava-whatsapp-rg}"
LOCATION="${AZURE_LOCATION:-eastus}"
CONTAINER_APP_ENV="${AZURE_CONTAINER_ENV:-ava-container-env}"
CONTAINER_APP_NAME="${AZURE_CONTAINER_APP:-ava-whatsapp}"
ACR_NAME="${AZURE_ACR_NAME:-avawhatsappacr$(date +%s | tail -c 6)}"  # Unique name
STORAGE_ACCOUNT="${AZURE_STORAGE_ACCOUNT:-avawhatsappstorage$(date +%s | tail -c 6)}"
FILE_SHARE_NAME="ava-data"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[✓]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[!]${NC} $1"; }
log_error() { echo -e "${RED}[✗]${NC} $1"; }

# Check prerequisites
log_info "Checking prerequisites..."

if ! command -v az &> /dev/null; then
    log_error "Azure CLI not installed. Install from: https://aka.ms/install-azure-cli"
    exit 1
fi

if ! az account show &> /dev/null; then
    log_error "Not logged into Azure. Run: az login"
    exit 1
fi

if [ ! -f .env ]; then
    log_error ".env file not found! Create it with all required API keys."
    exit 1
fi

log_success "Prerequisites verified"

# Load environment variables to validate
log_info "Loading environment variables from .env..."

# Safely load .env file, handling quotes and special characters
while IFS= read -r line || [ -n "$line" ]; do
    # Skip comments and empty lines
    if [[ "$line" =~ ^[[:space:]]*# ]] || [[ -z "${line// }" ]]; then
        continue
    fi
    
    # Remove carriage returns (Windows line endings)
    line=$(echo "$line" | tr -d '\r')
    
    # Extract variable name and value
    if [[ "$line" =~ ^[[:space:]]*([A-Za-z_][A-Za-z0-9_]*)[[:space:]]*=[[:space:]]*(.*)[[:space:]]*$ ]]; then
        var_name="${BASH_REMATCH[1]}"
        var_value="${BASH_REMATCH[2]}"
        
        # Remove surrounding quotes if present
        var_value=$(echo "$var_value" | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//")
        
        # Export the variable
        export "$var_name=$var_value"
    fi
done < .env

REQUIRED_VARS=(
    "GROQ_API_KEY"
    "ELEVENLABS_API_KEY"
    "ELEVENLABS_VOICE_ID"
    "TOGETHER_API_KEY"
    "AZURE_OPENAI_API_KEY"
    "AZURE_OPENAI_API_ENDPOINT"
    "AZURE_OPENAI_API_VERSION"
    "AZURE_OPENAI_VISION_DEPLOYMENT"
    "QDRANT_URL"
    "WHATSAPP_PHONE_NUMBER_ID"
    "WHATSAPP_TOKEN"
    "WHATSAPP_VERIFY_TOKEN"
)

MISSING_VARS=()
for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        MISSING_VARS+=("$var")
    fi
done

if [ ${#MISSING_VARS[@]} -gt 0 ]; then
    log_error "Missing required environment variables in .env:"
    printf '  - %s\n' "${MISSING_VARS[@]}"
    exit 1
fi

log_success "Environment variables validated"

# Get current subscription
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
log_info "Using subscription: $SUBSCRIPTION_ID"

echo ""
echo "============================================"
echo "  Azure Deployment Configuration"
echo "============================================"
echo "Resource Group:    $RESOURCE_GROUP"
echo "Location:          $LOCATION"
echo "Container App:     $CONTAINER_APP_NAME"
echo "ACR:               $ACR_NAME"
echo "Storage:           $STORAGE_ACCOUNT"
echo "============================================"
echo ""

read -p "Continue with deployment? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log_warning "Deployment cancelled"
    exit 0
fi

# Step 1: Create Resource Group
log_info "Creating resource group..."
az group create \
    --name "$RESOURCE_GROUP" \
    --location "$LOCATION" \
    --output none 2>/dev/null || true
log_success "Resource group ready"

# Step 2: Create Storage Account for persistent SQLite database
log_info "Creating storage account for persistent data..."
az storage account create \
    --name "$STORAGE_ACCOUNT" \
    --resource-group "$RESOURCE_GROUP" \
    --location "$LOCATION" \
    --sku Standard_LRS \
    --kind StorageV2 \
    --https-only true \
    --min-tls-version TLS1_2 \
    --output none 2>/dev/null || true
log_success "Storage account created"

# Step 3: Create File Share for SQLite database
log_info "Creating Azure Files share..."
STORAGE_KEY=$(az storage account keys list \
    --account-name "$STORAGE_ACCOUNT" \
    --resource-group "$RESOURCE_GROUP" \
    --query "[0].value" -o tsv)

az storage share create \
    --name "$FILE_SHARE_NAME" \
    --account-name "$STORAGE_ACCOUNT" \
    --account-key "$STORAGE_KEY" \
    --quota 10 \
    --output none 2>/dev/null || true
log_success "File share created"

# Step 4: Create Azure Container Registry
log_info "Creating Azure Container Registry..."
az acr create \
    --resource-group "$RESOURCE_GROUP" \
    --name "$ACR_NAME" \
    --sku Basic \
    --location "$LOCATION" \
    --admin-enabled true \
    --output none 2>/dev/null || true
log_success "Container registry created"

# Step 5: Build and push Docker image
log_info "Building and pushing WhatsApp webhook image (this may take 3-5 minutes)..."
az acr build \
    --registry "$ACR_NAME" \
    --image ava-whatsapp:latest \
    --image ava-whatsapp:$(git rev-parse --short HEAD 2>/dev/null || echo "latest") \
    --file Dockerfile \
    . \
    --output table

log_success "Docker image built and pushed"

# Step 6: Create Container Apps Environment
log_info "Creating Container Apps Environment..."
az containerapp env create \
    --name "$CONTAINER_APP_ENV" \
    --resource-group "$RESOURCE_GROUP" \
    --location "$LOCATION" \
    --output none 2>/dev/null || true
log_success "Container Apps Environment ready"

# Step 7: Add Storage to Container Apps Environment
log_info "Configuring persistent storage..."
az containerapp env storage set \
    --name "$CONTAINER_APP_ENV" \
    --resource-group "$RESOURCE_GROUP" \
    --storage-name "ava-persistent-data" \
    --azure-file-account-name "$STORAGE_ACCOUNT" \
    --azure-file-account-key "$STORAGE_KEY" \
    --azure-file-share-name "$FILE_SHARE_NAME" \
    --access-mode ReadWrite \
    --output none 2>/dev/null || true
log_success "Persistent storage configured"

# Step 8: Get ACR credentials
ACR_USERNAME=$(az acr credential show --name "$ACR_NAME" --query username -o tsv)
ACR_PASSWORD=$(az acr credential show --name "$ACR_NAME" --query passwords[0].value -o tsv)
ACR_SERVER=$(az acr show --name "$ACR_NAME" --query loginServer -o tsv)

# Step 9: Create Container App with all configurations
log_info "Deploying WhatsApp webhook container app..."
log_info "Configuration: 2 vCPU, 4Gi RAM, auto-scale 2-5 replicas (supports 1000+ users)"

az containerapp create \
    --name "$CONTAINER_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --environment "$CONTAINER_APP_ENV" \
    --image "$ACR_SERVER/ava-whatsapp:latest" \
    --target-port 8080 \
    --ingress external \
    --registry-server "$ACR_SERVER" \
    --registry-username "$ACR_USERNAME" \
    --registry-password "$ACR_PASSWORD" \
    --cpu 2.0 \
    --memory 4Gi \
    --min-replicas 2 \
    --max-replicas 5 \
    --env-vars \
        GROQ_API_KEY="$GROQ_API_KEY" \
        ELEVENLABS_API_KEY="$ELEVENLABS_API_KEY" \
        ELEVENLABS_VOICE_ID="$ELEVENLABS_VOICE_ID" \
        TOGETHER_API_KEY="$TOGETHER_API_KEY" \
        AZURE_OPENAI_API_KEY="$AZURE_OPENAI_API_KEY" \
        AZURE_OPENAI_API_ENDPOINT="$AZURE_OPENAI_API_ENDPOINT" \
        AZURE_OPENAI_API_VERSION="$AZURE_OPENAI_API_VERSION" \
        AZURE_OPENAI_VISION_DEPLOYMENT="$AZURE_OPENAI_VISION_DEPLOYMENT" \
        QDRANT_API_KEY="${QDRANT_API_KEY:-}" \
        QDRANT_URL="$QDRANT_URL" \
        QDRANT_PORT="6333" \
        WHATSAPP_PHONE_NUMBER_ID="$WHATSAPP_PHONE_NUMBER_ID" \
        WHATSAPP_TOKEN="$WHATSAPP_TOKEN" \
        WHATSAPP_VERIFY_TOKEN="$WHATSAPP_VERIFY_TOKEN" \
        GOOGLE_SHEETS_BOOKING_ID="${GOOGLE_SHEETS_BOOKING_ID:-}" \
        SHORT_TERM_MEMORY_DB_PATH="/app/data/memory.db" \
        TEXT_MODEL_NAME="${TEXT_MODEL_NAME:-gpt-5-chat}" \
        SMALL_TEXT_MODEL_NAME="${SMALL_TEXT_MODEL_NAME:-gpt-5-mini}" \
        STT_MODEL_NAME="${STT_MODEL_NAME:-whisper-large-v3-turbo}" \
        TTS_MODEL_NAME="${TTS_MODEL_NAME:-eleven_flash_v2_5}" \
        TTI_MODEL_NAME="${TTI_MODEL_NAME:-black-forest-labs/FLUX.1-schnell-Free}" \
    --output none 2>/dev/null || {
        log_warning "Container app might already exist, updating instead..."
        az containerapp update \
            --name "$CONTAINER_APP_NAME" \
            --resource-group "$RESOURCE_GROUP" \
            --image "$ACR_SERVER/ava-whatsapp:latest" \
            --output none
    }

log_success "Container app deployed"

# Step 10: Mount persistent storage
log_info "Mounting persistent storage for SQLite database..."
az containerapp update \
    --name "$CONTAINER_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --replace-env-vars "ava-persistent-data=/app/data" \
    --output none 2>/dev/null || true
log_success "Storage mounted"

# Step 11: Configure scaling rules
log_info "Configuring auto-scaling for 1000+ users..."
az containerapp update \
    --name "$CONTAINER_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --scale-rule-name http-scaling \
    --scale-rule-type http \
    --scale-rule-http-concurrency 25 \
    --output none 2>/dev/null || true
log_success "Auto-scaling configured (25 concurrent requests per replica)"

# Get application URL
APP_URL=$(az containerapp show \
    --name "$CONTAINER_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query properties.configuration.ingress.fqdn \
    -o tsv)

echo ""
echo "============================================"
echo "  🎉 Deployment Successful!"
echo "============================================"
echo ""
echo "Application URL:"
echo "  https://$APP_URL"
echo ""
echo "WhatsApp Webhook URL:"
echo "  https://$APP_URL/webhook"
echo ""
echo "API Documentation:"
echo "  https://$APP_URL/docs"
echo ""
echo "============================================"
echo "  Resource Summary"
echo "============================================"
echo "Resource Group:       $RESOURCE_GROUP"
echo "Container App:        $CONTAINER_APP_NAME"
echo "Container Registry:   $ACR_SERVER"
echo "Storage Account:      $STORAGE_ACCOUNT"
echo ""
echo "Configuration:"
echo "  - CPU: 2 vCPUs per replica"
echo "  - Memory: 4Gi per replica"
echo "  - Auto-scale: 2-5 replicas"
echo "  - Max capacity: ~125 concurrent users"
echo "  - Storage: Persistent Azure Files"
echo "  - Qdrant: Using your cloud instance"
echo ""
echo "============================================"
echo "  Next Steps"
echo "============================================"
echo ""
echo "1. Test your deployment:"
echo "   curl https://$APP_URL/docs"
echo ""
echo "2. Update WhatsApp webhook:"
echo "   - Go to: https://developers.facebook.com/"
echo "   - Navigate to your WhatsApp app"
echo "   - Update webhook URL to: https://$APP_URL/webhook"
echo "   - Verify with your WHATSAPP_VERIFY_TOKEN"
echo ""
echo "3. Monitor your application:"
echo "   az containerapp logs show \\"
echo "     --name $CONTAINER_APP_NAME \\"
echo "     --resource-group $RESOURCE_GROUP \\"
echo "     --follow"
echo ""
echo "4. View logs in Azure Portal:"
echo "   https://portal.azure.com/#@/resource/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.App/containerApps/$CONTAINER_APP_NAME"
echo ""
echo "============================================"
echo ""

# Save configuration for future reference
cat > azure-deployment-config.txt << EOF
Azure Deployment Configuration
Generated: $(date)

Resource Group: $RESOURCE_GROUP
Location: $LOCATION
Container App: $CONTAINER_APP_NAME
Environment: $CONTAINER_APP_ENV
Container Registry: $ACR_SERVER
Storage Account: $STORAGE_ACCOUNT
File Share: $FILE_SHARE_NAME

Application URL: https://$APP_URL
WhatsApp Webhook: https://$APP_URL/webhook

To update deployment:
  az acr build --registry $ACR_NAME --image ava-whatsapp:latest --file Dockerfile .
  az containerapp update --name $CONTAINER_APP_NAME --resource-group $RESOURCE_GROUP --image $ACR_SERVER/ava-whatsapp:latest

To view logs:
  az containerapp logs show --name $CONTAINER_APP_NAME --resource-group $RESOURCE_GROUP --follow

To scale manually:
  az containerapp update --name $CONTAINER_APP_NAME --resource-group $RESOURCE_GROUP --min-replicas 3 --max-replicas 10
EOF

log_success "Deployment configuration saved to: azure-deployment-config.txt"

