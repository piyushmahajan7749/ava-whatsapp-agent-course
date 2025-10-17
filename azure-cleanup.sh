#!/bin/bash

# Azure Cleanup Script
# This script cleans up Azure resources and stored memory data

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  Azure Cleanup Script${NC}"
echo -e "${BLUE}============================================${NC}"

# Check if deployment config exists
if [ ! -f "azure-deployment-config.txt" ]; then
    echo -e "${RED}Error: No deployment found${NC}"
    echo "Run 'make azure-deploy' first to create a deployment"
    exit 1
fi

# Read configuration
RESOURCE_GROUP=$(grep "Resource Group:" azure-deployment-config.txt | cut -d' ' -f3)
STORAGE_ACCOUNT=$(grep "Storage Account:" azure-deployment-config.txt | cut -d' ' -f3)
FILE_SHARE=$(grep "File Share:" azure-deployment-config.txt | cut -d' ' -f3)

echo -e "${YELLOW}Found deployment:${NC}"
echo "  Resource Group: $RESOURCE_GROUP"
echo "  Storage Account: $STORAGE_ACCOUNT"
echo "  File Share: $FILE_SHARE"
echo ""

# Function to clean up memory data
cleanup_memory_data() {
    echo -e "${BLUE}[INFO]${NC} Cleaning up stored memory data..."
    
    # Check if storage account exists
    if az storage account show --name "$STORAGE_ACCOUNT" --resource-group "$RESOURCE_GROUP" >/dev/null 2>&1; then
        # Get storage account key
        STORAGE_KEY=$(az storage account keys list --resource-group "$RESOURCE_GROUP" --account-name "$STORAGE_ACCOUNT" --query "[0].value" -o tsv)
        
        # Delete memory directories from file share
        echo -e "${BLUE}[INFO]${NC} Deleting memory data from Azure File Share..."
        
        # Delete long_term_memory directory if it exists
        if az storage file list --account-name "$STORAGE_ACCOUNT" --account-key "$STORAGE_KEY" --share-name "$FILE_SHARE" --path "long_term_memory" >/dev/null 2>&1; then
            echo "  Deleting long_term_memory directory..."
            az storage file delete-batch --account-name "$STORAGE_ACCOUNT" --account-key "$STORAGE_KEY" --source "$FILE_SHARE/long_term_memory" --delete-snapshots include
        fi
        
        # Delete short_term_memory directory if it exists
        if az storage file list --account-name "$STORAGE_ACCOUNT" --account-key "$STORAGE_KEY" --share-name "$FILE_SHARE" --path "short_term_memory" >/dev/null 2>&1; then
            echo "  Deleting short_term_memory directory..."
            az storage file delete-batch --account-name "$STORAGE_ACCOUNT" --account-key "$STORAGE_KEY" --source "$FILE_SHARE/short_term_memory" --delete-snapshots include
        fi
        
        # Delete generated_images directory if it exists
        if az storage file list --account-name "$STORAGE_ACCOUNT" --account-key "$STORAGE_KEY" --share-name "$FILE_SHARE" --path "generated_images" >/dev/null 2>&1; then
            echo "  Deleting generated_images directory..."
            az storage file delete-batch --account-name "$STORAGE_ACCOUNT" --account-key "$STORAGE_KEY" --source "$FILE_SHARE/generated_images" --delete-snapshots include
        fi
        
        echo -e "${GREEN}[✓]${NC} Memory data cleanup completed"
    else
        echo -e "${YELLOW}[WARNING]${NC} Storage account not found, skipping memory cleanup"
    fi
}

# Function to delete all Azure resources
delete_azure_resources() {
    echo -e "${BLUE}[INFO]${NC} Deleting Azure resources..."
    echo -e "${RED}WARNING: This will delete ALL resources in resource group: $RESOURCE_GROUP${NC}"
    echo ""
    
    read -p "Are you sure you want to delete all Azure resources? (y/N) " -n 1 -r
    echo ""
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${BLUE}[INFO]${NC} Initiating resource group deletion..."
        az group delete --name "$RESOURCE_GROUP" --yes --no-wait
        echo -e "${GREEN}[✓]${NC} Azure resources deletion initiated"
        
        # Clean up local config file
        rm -f azure-deployment-config.txt
        echo -e "${GREEN}[✓]${NC} Local configuration file removed"
    else
        echo -e "${YELLOW}[INFO]${NC} Resource deletion cancelled"
    fi
}

# Main menu
echo "What would you like to do?"
echo "1. Clean up memory data only (keep Azure resources)"
echo "2. Delete all Azure resources (complete cleanup)"
echo "3. Cancel"
echo ""

read -p "Choose an option (1-3): " -n 1 -r
echo ""

case $REPLY in
    1)
        cleanup_memory_data
        echo ""
        echo -e "${GREEN}[✓]${NC} Memory cleanup completed. Azure resources are still running."
        ;;
    2)
        cleanup_memory_data
        echo ""
        delete_azure_resources
        ;;
    3)
        echo -e "${YELLOW}[INFO]${NC} Cleanup cancelled"
        exit 0
        ;;
    *)
        echo -e "${RED}Error: Invalid option${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  Cleanup Complete${NC}"
echo -e "${GREEN}============================================${NC}"
