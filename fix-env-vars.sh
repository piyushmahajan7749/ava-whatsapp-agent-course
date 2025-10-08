#!/bin/bash
# ============================================================================
# Fix Environment Variables in Azure Container App
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

log_info "Updating environment variables for $CONTAINER_APP..."

# Load environment variables from .env file
if [ ! -f .env ]; then
    log_error ".env file not found!"
    exit 1
fi

# Function to get env var value from .env file
get_env_var() {
    local var_name="$1"
    local value=$(grep "^${var_name}=" .env | cut -d'=' -f2- | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//")
    echo "$value"
}

# Get all required variables
GROQ_API_KEY=$(get_env_var "GROQ_API_KEY")
ELEVENLABS_API_KEY=$(get_env_var "ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID=$(get_env_var "ELEVENLABS_VOICE_ID")
TOGETHER_API_KEY=$(get_env_var "TOGETHER_API_KEY")
AZURE_OPENAI_API_KEY=$(get_env_var "AZURE_OPENAI_API_KEY")
AZURE_OPENAI_API_ENDPOINT=$(get_env_var "AZURE_OPENAI_API_ENDPOINT")
AZURE_OPENAI_API_VERSION=$(get_env_var "AZURE_OPENAI_API_VERSION")
AZURE_OPENAI_VISION_DEPLOYMENT=$(get_env_var "AZURE_OPENAI_VISION_DEPLOYMENT")
QDRANT_API_KEY=$(get_env_var "QDRANT_API_KEY")
QDRANT_URL=$(get_env_var "QDRANT_URL")
WHATSAPP_PHONE_NUMBER_ID=$(get_env_var "WHATSAPP_PHONE_NUMBER_ID")
WHATSAPP_TOKEN=$(get_env_var "WHATSAPP_TOKEN")
WHATSAPP_VERIFY_TOKEN=$(get_env_var "WHATSAPP_VERIFY_TOKEN")
GOOGLE_SHEETS_BOOKING_ID=$(get_env_var "GOOGLE_SHEETS_BOOKING_ID")
TEXT_MODEL_NAME=$(get_env_var "TEXT_MODEL_NAME")
SMALL_TEXT_MODEL_NAME=$(get_env_var "SMALL_TEXT_MODEL_NAME")
STT_MODEL_NAME=$(get_env_var "STT_MODEL_NAME")
TTS_MODEL_NAME=$(get_env_var "TTS_MODEL_NAME")
TTI_MODEL_NAME=$(get_env_var "TTI_MODEL_NAME")

# Validate required variables
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

log_success "All required variables found in .env"

# Update container app with all environment variables
log_info "Updating Azure Container App environment variables..."

az containerapp update \
    --name "$CONTAINER_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --set-env-vars \
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
        SHORT_TERM_MEMORY_DB_PATH="/tmp/memory.db" \
        TEXT_MODEL_NAME="${TEXT_MODEL_NAME:-gpt-5-chat}" \
        SMALL_TEXT_MODEL_NAME="${SMALL_TEXT_MODEL_NAME:-gpt-5-mini}" \
        STT_MODEL_NAME="${STT_MODEL_NAME:-whisper-large-v3-turbo}" \
        TTS_MODEL_NAME="${TTS_MODEL_NAME:-eleven_flash_v2_5}" \
        TTI_MODEL_NAME="${TTI_MODEL_NAME:-black-forest-labs/FLUX.1-schnell-Free}" \
    --output none

log_success "Environment variables updated!"

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

# Show the logs
log_info "Fetching recent logs to verify..."
echo ""
echo "=================================="
echo "Recent Container Logs:"
echo "=================================="

az containerapp logs show \
    --name "$CONTAINER_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --tail 20

echo ""
log_success "Environment variables have been updated!"
log_info "Monitor logs with: make azure-logs"

