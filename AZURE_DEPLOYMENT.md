# Azure Production Deployment Guide

## Overview

This guide deploys **only the WhatsApp webhook** to Azure Container Apps. Your existing **Qdrant Cloud** instance is used for vector storage.

### Architecture

```
Azure Cloud
│
├── Container Apps Environment
│   └── WhatsApp Webhook (2-5 replicas, auto-scaling)
│       ├── FastAPI on port 8080
│       ├── 2 vCPU, 4Gi RAM per replica
│       └── Persistent storage via Azure Files
│
├── Azure Files
│   └── SQLite database (short_term_memory)
│
└── Azure Container Registry
    └── Docker images

External Services (Already Configured)
├── Qdrant Cloud (vector database)
├── Groq (LLM inference)
├── ElevenLabs (TTS)
├── Together AI (image generation)
└── WhatsApp Business API
```

### Scale Capacity

- **Configuration**: 2 vCPU, 4Gi RAM per replica
- **Auto-scaling**: 2-5 replicas
- **Concurrent users per replica**: ~25
- **Total capacity**: 125 concurrent conversations
- **Total users supported**: 1000+ (assuming 5% concurrency)

## Prerequisites

### 1. Azure Account

- Sign up at [azure.microsoft.com](https://azure.microsoft.com/free/)
- New accounts get $200 free credits

### 2. Install Azure CLI

**macOS:**

```bash
brew install azure-cli
```

**Linux:**

```bash
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
```

**Windows:**

```powershell
winget install -e --id Microsoft.AzureCLI
```

### 3. Login to Azure

```bash
az login
```

### 4. Verify .env file

Ensure your `.env` file contains all required variables:

```bash
# Required API keys
GROQ_API_KEY=your_groq_key
ELEVENLABS_API_KEY=your_elevenlabs_key
ELEVENLABS_VOICE_ID=your_voice_id
TOGETHER_API_KEY=your_together_key

# Azure OpenAI (for vision model)
AZURE_OPENAI_API_KEY=your_azure_openai_key
AZURE_OPENAI_API_ENDPOINT=your_endpoint
AZURE_OPENAI_API_VERSION=2024-02-15-preview
AZURE_OPENAI_VISION_DEPLOYMENT=your_deployment_name

# Qdrant Cloud (already configured)
QDRANT_URL=https://your-cluster.qdrant.io
QDRANT_API_KEY=your_qdrant_key

# WhatsApp Business API
WHATSAPP_PHONE_NUMBER_ID=your_phone_id
WHATSAPP_TOKEN=your_access_token
WHATSAPP_VERIFY_TOKEN=your_verify_token

# Optional: Google Sheets
GOOGLE_SHEETS_BOOKING_ID=your_sheet_id
```

## Deployment Steps

### Step 1: Make Script Executable

```bash
chmod +x deploy-azure-simple.sh
```

### Step 2: Run Deployment Script

```bash
./deploy-azure-simple.sh
```

The script will:

1. ✅ Validate prerequisites and environment variables
2. ✅ Create Azure resource group
3. ✅ Create Azure Container Registry
4. ✅ Build and push Docker image (~3-5 minutes)
5. ✅ Create Container Apps environment
6. ✅ Create Azure Files for persistent storage
7. ✅ Deploy container with auto-scaling
8. ✅ Configure all environment variables
9. ✅ Display your application URL

**Expected output:**

```
============================================
  🎉 Deployment Successful!
============================================

Application URL:
  https://ava-whatsapp.XXX.azurecontainerapps.io

WhatsApp Webhook URL:
  https://ava-whatsapp.XXX.azurecontainerapps.io/webhook
```

### Step 3: Verify Deployment

```bash
# Get your app URL
APP_URL=$(az containerapp show \
    --name ava-whatsapp \
    --resource-group ava-whatsapp-rg \
    --query properties.configuration.ingress.fqdn \
    -o tsv)

# Test the API
curl https://$APP_URL/docs

# Check health
curl https://$APP_URL/
```

### Step 4: Configure WhatsApp Webhook

1. Go to [Meta Developer Portal](https://developers.facebook.com/)
2. Select your WhatsApp app
3. Navigate to **Configuration** → **Webhooks**
4. Click **Edit** on Callback URL
5. Enter: `https://your-app-url.azurecontainerapps.io/webhook`
6. Enter your `WHATSAPP_VERIFY_TOKEN`
7. Click **Verify and Save**
8. Subscribe to webhook fields:
   - `messages`
   - `messaging_postbacks`

### Step 5: Test WhatsApp Integration

Send a message to your WhatsApp Business number and verify it responds.

## Monitoring & Management

### View Real-time Logs

```bash
az containerapp logs show \
    --name ava-whatsapp \
    --resource-group ava-whatsapp-rg \
    --follow
```

### Check Application Metrics

```bash
az containerapp show \
    --name ava-whatsapp \
    --resource-group ava-whatsapp-rg \
    --query properties.configuration
```

### View in Azure Portal

```bash
# Get direct link to your app in portal
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
echo "https://portal.azure.com/#@/resource/subscriptions/$SUBSCRIPTION_ID/resourceGroups/ava-whatsapp-rg/providers/Microsoft.App/containerApps/ava-whatsapp"
```

## Updating Your Deployment

### Method 1: Rebuild and Auto-update

```bash
# Build new image
az acr build \
    --registry avawhatsappacr \
    --image ava-whatsapp:latest \
    --file Dockerfile \
    .

# Container App will automatically pull and deploy the latest image
```

### Method 2: Update with specific image tag

```bash
# Build with specific tag
az acr build \
    --registry avawhatsappacr \
    --image ava-whatsapp:v1.2.3 \
    --file Dockerfile \
    .

# Update container app
az containerapp update \
    --name ava-whatsapp \
    --resource-group ava-whatsapp-rg \
    --image avawhatsappacr.azurecr.io/ava-whatsapp:v1.2.3
```

### Update Environment Variables

```bash
az containerapp update \
    --name ava-whatsapp \
    --resource-group ava-whatsapp-rg \
    --set-env-vars GROQ_API_KEY="new_key"
```

## Scaling

### Manual Scaling

```bash
# Scale up for higher traffic
az containerapp update \
    --name ava-whatsapp \
    --resource-group ava-whatsapp-rg \
    --min-replicas 3 \
    --max-replicas 10

# Scale down for cost savings
az containerapp update \
    --name ava-whatsapp \
    --resource-group ava-whatsapp-rg \
    --min-replicas 1 \
    --max-replicas 3
```

### Adjust Scaling Rules

```bash
# Change concurrent requests per replica
az containerapp update \
    --name ava-whatsapp \
    --resource-group ava-whatsapp-rg \
    --scale-rule-name http-scaling \
    --scale-rule-type http \
    --scale-rule-http-concurrency 50
```

## Cost Optimization

### Current Configuration Cost Estimate

- **Base (2 replicas always on)**: ~$70/month
- **Peak (5 replicas during high traffic)**: ~$175/month
- **Average (3 replicas)**: ~$105/month

With Azure free credits ($200):

- **First ~2 months**: FREE
- After credits: ~$70-105/month for 1000 users

### Cost Reduction Tips

1. **Scale to zero during off-hours** (not recommended for production):

```bash
az containerapp update \
    --name ava-whatsapp \
    --resource-group ava-whatsapp-rg \
    --min-replicas 0 \
    --max-replicas 5
```

2. **Use smaller instances for testing**:

```bash
az containerapp update \
    --name ava-whatsapp \
    --resource-group ava-whatsapp-rg \
    --cpu 1.0 \
    --memory 2Gi
```

3. **Use consumption-only pricing** (pay only when running)

## Troubleshooting

### Issue: Container fails to start

**Check logs:**

```bash
az containerapp logs show \
    --name ava-whatsapp \
    --resource-group ava-whatsapp-rg \
    --tail 100
```

**Common causes:**

- Missing environment variables
- Invalid API keys
- Qdrant connection issues

### Issue: High memory usage

**Check metrics:**

```bash
az monitor metrics list \
    --resource /subscriptions/{subscription}/resourceGroups/ava-whatsapp-rg/providers/Microsoft.App/containerApps/ava-whatsapp \
    --metric MemoryWorkingSetBytes
```

**Solution:** Increase memory or add more replicas:

```bash
az containerapp update \
    --name ava-whatsapp \
    --resource-group ava-whatsapp-rg \
    --memory 6Gi
```

### Issue: Qdrant connection fails

**Verify Qdrant Cloud:**

1. Check QDRANT_URL in your .env
2. Verify QDRANT_API_KEY is correct
3. Ensure Qdrant Cloud allows connections from Azure IPs

**Test connection:**

```bash
az containerapp exec \
    --name ava-whatsapp \
    --resource-group ava-whatsapp-rg \
    --command "curl -H 'api-key: YOUR_KEY' https://your-cluster.qdrant.io/collections"
```

### Issue: WhatsApp webhook verification fails

**Check verify token:**

```bash
az containerapp show \
    --name ava-whatsapp \
    --resource-group ava-whatsapp-rg \
    --query "properties.template.containers[0].env[?name=='WHATSAPP_VERIFY_TOKEN'].value"
```

**Update if needed:**

```bash
az containerapp update \
    --name ava-whatsapp \
    --resource-group ava-whatsapp-rg \
    --set-env-vars WHATSAPP_VERIFY_TOKEN="your_token"
```

### Issue: SQLite database locked

This can happen with multiple replicas writing to the same database.

**Solution:** This is already handled by using Azure Files with proper locking, but if issues persist:

```bash
# Reduce to single replica temporarily
az containerapp update \
    --name ava-whatsapp \
    --resource-group ava-whatsapp-rg \
    --min-replicas 1 \
    --max-replicas 1
```

Consider migrating to Azure SQL or PostgreSQL for better multi-replica support.

## Backup & Recovery

### Backup SQLite Database

```bash
# Download database from Azure Files
az storage file download \
    --account-name avawhatsappstorage \
    --share-name ava-data \
    --path memory.db \
    --dest ./backup-memory.db
```

### Restore Database

```bash
# Upload backup to Azure Files
az storage file upload \
    --account-name avawhatsappstorage \
    --share-name ava-data \
    --source ./backup-memory.db \
    --path memory.db
```

## Security Best Practices

### 1. Use Azure Key Vault (Recommended for Production)

```bash
# Create Key Vault
az keyvault create \
    --name ava-keyvault \
    --resource-group ava-whatsapp-rg \
    --location eastus

# Store secrets
az keyvault secret set --vault-name ava-keyvault --name GROQ-API-KEY --value "your_key"
az keyvault secret set --vault-name ava-keyvault --name WHATSAPP-TOKEN --value "your_token"

# Update container app to use Key Vault
# (requires additional configuration)
```

### 2. Enable Managed Identity

```bash
az containerapp identity assign \
    --name ava-whatsapp \
    --resource-group ava-whatsapp-rg \
    --system-assigned
```

### 3. Restrict Ingress

```bash
# Limit to specific IPs (e.g., Meta's webhook IPs)
az containerapp ingress access-restriction set \
    --name ava-whatsapp \
    --resource-group ava-whatsapp-rg \
    --rule-name meta-webhooks \
    --ip-address 31.13.64.0/19 \
    --action Allow
```

## Advanced Configuration

### Custom Domain

```bash
# Add custom domain
az containerapp hostname add \
    --name ava-whatsapp \
    --resource-group ava-whatsapp-rg \
    --hostname chat.yourdomain.com

# Bind certificate (requires SSL cert)
az containerapp hostname bind \
    --name ava-whatsapp \
    --resource-group ava-whatsapp-rg \
    --hostname chat.yourdomain.com \
    --certificate-name your-cert
```

### Enable Application Insights

```bash
# Create App Insights
az monitor app-insights component create \
    --app ava-insights \
    --resource-group ava-whatsapp-rg \
    --location eastus

# Get instrumentation key
INSTRUMENTATION_KEY=$(az monitor app-insights component show \
    --app ava-insights \
    --resource-group ava-whatsapp-rg \
    --query instrumentationKey -o tsv)

# Update container app
az containerapp update \
    --name ava-whatsapp \
    --resource-group ava-whatsapp-rg \
    --set-env-vars APPLICATIONINSIGHTS_CONNECTION_STRING="InstrumentationKey=$INSTRUMENTATION_KEY"
```

## Cleanup

### Delete Everything

```bash
# WARNING: This deletes all resources and data
az group delete --name ava-whatsapp-rg --yes --no-wait
```

### Delete Only Container App (keep data)

```bash
az containerapp delete \
    --name ava-whatsapp \
    --resource-group ava-whatsapp-rg \
    --yes
```

## Migration from ngrok

### Before Deployment

1. ✅ Test locally with `make ava-run`
2. ✅ Verify all API keys in `.env`
3. ✅ Note your current ngrok URL

### During Deployment

1. ✅ Run `./deploy-azure-simple.sh`
2. ✅ Wait for completion (~5-10 minutes)
3. ✅ Test new Azure URL

### After Deployment

1. ✅ Update WhatsApp webhook URL
2. ✅ Test with WhatsApp messages
3. ✅ Monitor logs for 24 hours
4. ✅ Stop ngrok (no longer needed!)

## Support & Resources

- **Azure Container Apps Docs**: https://learn.microsoft.com/en-us/azure/container-apps/
- **Azure CLI Reference**: https://learn.microsoft.com/en-us/cli/azure/containerapp
- **Qdrant Cloud Docs**: https://qdrant.tech/documentation/cloud/
- **WhatsApp Business API**: https://developers.facebook.com/docs/whatsapp/

## Next Steps

1. ✅ Deploy using `./deploy-azure-simple.sh`
2. ✅ Update WhatsApp webhook
3. ✅ Test with real users
4. ✅ Monitor performance and costs
5. ✅ Scale as needed
6. ✅ Consider migrating SQLite to Azure SQL for better scaling

---

**Congratulations! Your WhatsApp agent is now running on Azure with support for 1000+ users! 🚀**
