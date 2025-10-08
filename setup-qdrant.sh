#!/bin/bash
# Setup or update Qdrant Cloud credentials

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

echo ""
echo "========================================"
echo "  Qdrant Cloud Setup Helper"
echo "========================================"
echo ""

log_error "Current Qdrant credentials are invalid (404 error)"
echo ""
log_info "The Qdrant cluster either:"
echo "  1. Was deleted or deactivated"
echo "  2. Never existed at this URL"
echo "  3. Has incorrect credentials"
echo ""

echo "========================================"
echo "  Option 1: Get New Qdrant Cloud Credentials (Recommended)"
echo "========================================"
echo ""
echo "Steps:"
echo "1. Go to: https://cloud.qdrant.io/"
echo "2. Login or create account (free tier available)"
echo "3. Create a new cluster:"
echo "   - Click 'Create Cluster'"
echo "   - Select FREE tier (1GB storage)"
echo "   - Choose region: us-east (closest to Azure East US)"
echo "   - Wait for cluster to be 'Running'"
echo ""
echo "4. Get your credentials:"
echo "   - Copy Cluster URL (format: https://xxxxx.qdrant.io)"
echo "   - Go to 'API Keys' tab"
echo "   - Create or copy existing API key"
echo ""

read -p "Do you have new Qdrant credentials? (y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    log_info "Please enter your new Qdrant credentials:"
    echo ""
    
    read -p "Qdrant URL (e.g., https://xxxxx.qdrant.io): " NEW_QDRANT_URL
    read -p "Qdrant API Key: " NEW_QDRANT_API_KEY
    
    echo ""
    log_info "Testing new credentials..."
    
    if ./test-qdrant-connection.sh "$NEW_QDRANT_URL" "$NEW_QDRANT_API_KEY"; then
        log_success "Credentials verified!"
        echo ""
        
        log_info "Updating .env file..."
        
        # Backup existing .env
        cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
        log_info "Backed up .env to .env.backup.$(date +%Y%m%d_%H%M%S)"
        
        # Update .env file
        sed -i.tmp "s|QDRANT_URL=.*|QDRANT_URL=\"$NEW_QDRANT_URL\"|g" .env
        sed -i.tmp "s|QDRANT_API_KEY=.*|QDRANT_API_KEY=\"$NEW_QDRANT_API_KEY\"|g" .env
        rm .env.tmp
        
        log_success ".env file updated!"
        echo ""
        
        log_info "Next steps:"
        echo "1. Update Azure Container App:"
        echo "   ./fix-env-vars.sh"
        echo ""
        echo "2. Monitor logs:"
        echo "   make azure-logs"
        echo ""
        echo "3. Test WhatsApp message to verify it works"
        echo ""
        
        read -p "Update Azure Container App now? (y/n) " -n 1 -r
        echo ""
        
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log_info "Updating Azure Container App..."
            ./fix-env-vars.sh
            
            log_success "Azure Container App updated!"
            echo ""
            log_info "Monitor logs with: make azure-logs"
            echo ""
            log_info "Send a WhatsApp message to test!"
        else
            log_warning "Remember to run: ./fix-env-vars.sh"
        fi
    else
        log_error "Credentials test failed. Please verify and try again."
        exit 1
    fi
else
    echo ""
    log_warning "No credentials provided."
    echo ""
    echo "========================================"
    echo "  Option 2: Use Local Qdrant (Not Recommended)"
    echo "========================================"
    echo ""
    echo "For temporary testing only:"
    echo "1. Modify docker-compose.yml to expose Qdrant"
    echo "2. Use QDRANT_URL=http://localhost:6333"
    echo "3. Data will be lost on container restart"
    echo ""
    echo "This is NOT recommended for production!"
    echo ""
    
    log_info "Please get Qdrant Cloud credentials and run this script again:"
    echo "  ./setup-qdrant.sh"
fi

