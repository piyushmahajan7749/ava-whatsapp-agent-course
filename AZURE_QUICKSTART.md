# Azure Deployment - Quick Start Guide

Deploy your WhatsApp agent to Azure in **5 simple steps**. No more ngrok!

## Prerequisites (5 minutes)

1. **Azure Account**: [Sign up for free](https://azure.microsoft.com/free/) - Get $200 credits
2. **Azure CLI**: Install via `brew install azure-cli` (macOS) or [other platforms](https://aka.ms/install-azure-cli)
3. **Login**: Run `az login`

## Deployment (10 minutes)

### Step 1: Verify Environment Variables

Ensure your `.env` file has all required keys:

```bash
# Check your .env file
cat .env | grep -E "GROQ|ELEVENLABS|TOGETHER|QDRANT|WHATSAPP|AZURE_OPENAI"
```

Required variables:

- `GROQ_API_KEY`
- `ELEVENLABS_API_KEY`
- `ELEVENLABS_VOICE_ID`
- `TOGETHER_API_KEY`
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_API_ENDPOINT`
- `AZURE_OPENAI_API_VERSION`
- `AZURE_OPENAI_VISION_DEPLOYMENT`
- `QDRANT_URL` (your Qdrant Cloud URL)
- `QDRANT_API_KEY` (your Qdrant Cloud API key)
- `WHATSAPP_PHONE_NUMBER_ID`
- `WHATSAPP_TOKEN`
- `WHATSAPP_VERIFY_TOKEN`

### Step 2: Deploy to Azure

```bash
# Simple one-command deployment
make azure-deploy
```

Or directly:

```bash
chmod +x deploy-azure-simple.sh
./deploy-azure-simple.sh
```

**What happens:**

- ✅ Creates Azure resources (Container Registry, Container Apps, Storage)
- ✅ Builds and pushes your Docker image
- ✅ Deploys with auto-scaling (2-5 replicas)
- ✅ Configures for 1000+ users
- ✅ Takes ~5-10 minutes

**Output:**

```
============================================
  🎉 Deployment Successful!
============================================

Application URL:
  https://ava-whatsapp.XXX.azurecontainerapps.io

WhatsApp Webhook URL:
  https://ava-whatsapp.XXX.azurecontainerapps.io/webhook
```

### Step 3: Test Deployment

```bash
# Your app URL will be displayed after deployment
# Test the API documentation
curl https://YOUR-APP-URL/docs

# Or use make command to check status
make azure-status
```

### Step 4: Update WhatsApp Webhook

1. Go to [Meta Developer Portal](https://developers.facebook.com/)
2. Select your WhatsApp Business App
3. Navigate to **Configuration** → **Webhooks**
4. Click **Edit** on Callback URL
5. Enter: `https://YOUR-APP-URL.azurecontainerapps.io/webhook`
6. Enter your `WHATSAPP_VERIFY_TOKEN` from `.env`
7. Click **Verify and Save**
8. Subscribe to: `messages` and `messaging_postbacks`

### Step 5: Test with WhatsApp

Send a message to your WhatsApp Business number. It should respond!

## Monitoring

### View Live Logs

```bash
make azure-logs
```

### Check Status

```bash
make azure-status
```

## Updating Your Code

After making changes:

```bash
# Quick update
make azure-update
```

This rebuilds and redeploys in ~3 minutes.

## Architecture

### What's Deployed

- ✅ **WhatsApp webhook** (FastAPI) on Azure Container Apps
- ✅ **Auto-scaling**: 2-5 replicas
- ✅ **Resources**: 2 vCPU, 4Gi RAM per replica
- ✅ **Storage**: Azure Files for SQLite persistence
- ✅ **Capacity**: 125 concurrent users, 1000+ total users

### What's NOT Deployed (Already Using Cloud)

- ❌ Qdrant (using your Qdrant Cloud instance)
- ❌ Chainlit (not needed for WhatsApp)

### External Services (Already Configured)

- Qdrant Cloud (vector database)
- Groq (LLM inference)
- ElevenLabs (text-to-speech)
- Together AI (image generation)
- Azure OpenAI (vision model)

## Costs

With **$200 Azure free credits**:

- First 2-3 months: **FREE**
- After credits: **~$70-105/month** for 1000 users

**Cost breakdown:**

- Container Apps (2 replicas): ~$70/month
- Storage (10GB): ~$2/month
- Container Registry: ~$5/month
- Bandwidth: ~$5-10/month
- **Total**: ~$82-87/month base, scales up during high traffic

## Common Tasks

### View Logs

```bash
make azure-logs
```

### Update Code

```bash
# After making changes
git commit -m "Updated code"
make azure-update
```

### Scale Up

```bash
az containerapp update \
    --name ava-whatsapp \
    --resource-group ava-whatsapp-rg \
    --min-replicas 3 \
    --max-replicas 10
```

### Check Cost

```bash
# View cost analysis
az consumption usage list \
    --resource-group ava-whatsapp-rg
```

## Troubleshooting

### Deployment fails with "registry not found"

```bash
# Ensure unique ACR name
export AZURE_ACR_NAME="avawhatsappacr$(date +%s | tail -c 6)"
./deploy-azure-simple.sh
```

### Container won't start

```bash
# Check logs
make azure-logs

# Common issues:
# - Missing environment variables
# - Invalid API keys
# - Qdrant connection issues
```

### WhatsApp webhook verification fails

```bash
# Verify token matches
grep WHATSAPP_VERIFY_TOKEN .env

# Test webhook manually
curl "https://YOUR-APP-URL/webhook?hub.mode=subscribe&hub.challenge=test&hub.verify_token=YOUR_TOKEN"
```

### High memory usage

```bash
# Scale up memory
az containerapp update \
    --name ava-whatsapp \
    --resource-group ava-whatsapp-rg \
    --memory 6Gi
```

## Cleanup

### Delete Everything (to save costs)

```bash
make azure-delete
```

This deletes all Azure resources and stops billing.

## Comparison: Azure vs ngrok

| Feature         | ngrok (current)                  | Azure (new)                    |
| --------------- | -------------------------------- | ------------------------------ |
| **Uptime**      | Manual (requires running laptop) | 99.9% SLA                      |
| **URL**         | Changes on restart               | Permanent                      |
| **SSL**         | Provided by ngrok                | Automatic Azure SSL            |
| **Scaling**     | Single instance                  | Auto-scale 2-5 replicas        |
| **Cost**        | Free (or $8/month)               | ~$82/month (free for 2 months) |
| **Capacity**    | ~10-20 users                     | 1000+ users                    |
| **Reliability** | Depends on laptop                | Production-grade               |
| **Monitoring**  | None                             | Azure Monitor, logs            |

## Next Steps

1. ✅ Deploy with `make azure-deploy`
2. ✅ Update WhatsApp webhook
3. ✅ Test with users
4. ✅ Monitor with `make azure-logs`
5. ✅ Scale as needed

## Support

- **Full Documentation**: [AZURE_DEPLOYMENT.md](AZURE_DEPLOYMENT.md)
- **Azure Container Apps**: https://learn.microsoft.com/en-us/azure/container-apps/
- **WhatsApp Business API**: https://developers.facebook.com/docs/whatsapp/

---

**Ready to go production? Run `make azure-deploy` now! 🚀**
