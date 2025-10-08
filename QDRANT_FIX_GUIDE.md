# Qdrant Connection Fix Guide

## Problem

Your Azure deployment is getting a **404 error** when connecting to Qdrant Cloud:

```
Error: UnexpectedResponse: Unexpected Response: 404 (Not Found)
URL: https://a860d76f-e993-492b-96dd-6bd38039f54d.us-east4-0.gcp.cloud.qdrant.io
```

This means the Qdrant cluster doesn't exist or was deleted.

## Quick Fix (5 minutes)

### Option 1: Get New Qdrant Cloud Credentials (Recommended)

1. **Go to Qdrant Cloud Dashboard**

   ```
   https://cloud.qdrant.io/
   ```

2. **Login or Create Account**

   - Free tier available (1GB storage, sufficient for testing)
   - No credit card required for free tier

3. **Create a New Cluster**

   - Click "Create Cluster"
   - Select **FREE** tier
   - Choose region: **us-east** (closest to your Azure East US deployment)
   - Wait 1-2 minutes for cluster status to be "Running"

4. **Get Your Credentials**

   **Cluster URL:**

   - Find your cluster in the dashboard
   - Copy the URL (format: `https://xxxxx-xxxxx-xxxxx.qdrant.io`)

   **API Key:**

   - Click on your cluster
   - Go to "API Keys" tab
   - Create new key or copy existing one

5. **Update Your Configuration**

   ```bash
   ./setup-qdrant.sh
   ```

   The script will:

   - Test your new credentials
   - Update `.env` file
   - Update Azure Container App
   - Verify everything works

### Option 2: Manual Update

If you prefer to update manually:

1. **Test new credentials:**

   ```bash
   ./test-qdrant-connection.sh "https://YOUR-NEW-URL.qdrant.io" "YOUR-NEW-API-KEY"
   ```

2. **Update .env file:**

   ```bash
   # Edit .env and replace:
   QDRANT_URL="https://YOUR-NEW-URL.qdrant.io"
   QDRANT_API_KEY="YOUR-NEW-API-KEY"
   ```

3. **Update Azure:**

   ```bash
   ./fix-env-vars.sh
   ```

4. **Monitor logs:**
   ```bash
   make azure-logs
   ```

## Verification Steps

### 1. Test Connection Locally

```bash
QDRANT_URL=$(grep QDRANT_URL .env | cut -d'=' -f2- | tr -d '"')
QDRANT_API_KEY=$(grep QDRANT_API_KEY .env | cut -d'=' -f2- | tr -d '"')
./test-qdrant-connection.sh "$QDRANT_URL" "$QDRANT_API_KEY"
```

**Expected output:**

```
✓ Client initialized
✓ Connection successful!
✓ Found 0 collections
✓ Qdrant connection is working!
```

### 2. Verify Azure Deployment

```bash
# Check environment variables are set
az containerapp show \
    --name ava-whatsapp \
    --resource-group ava-whatsapp-rg \
    --query "properties.template.containers[0].env[?name=='QDRANT_URL'].{name:name, value:value}" \
    -o table
```

### 3. Monitor Logs for Qdrant Errors

```bash
make azure-logs
```

Look for:

- ✅ No "404" errors
- ✅ No "UnexpectedResponse" errors
- ✅ Memory operations succeeding

### 4. Test with WhatsApp

Send a message to your WhatsApp Business number and check:

- ✅ Message is received
- ✅ Response is sent
- ✅ No errors in logs

## Troubleshooting

### Issue: Still getting 404 after updating

**Check:**

1. Cluster status in Qdrant Cloud dashboard is "Running"
2. URL doesn't have extra spaces or quotes
3. API key is correct and not expired
4. Region is accessible from Azure East US

**Verify:**

```bash
# Test credentials
./test-qdrant-connection.sh "$QDRANT_URL" "$QDRANT_API_KEY"
```

### Issue: Connection timeout

**Possible causes:**

- Cluster is starting up (wait 2-3 minutes)
- Network/firewall issue
- Wrong region (use us-east for best Azure connectivity)

**Solution:**

```bash
# Test with longer timeout
uv run python << 'EOF'
from qdrant_client import QdrantClient
client = QdrantClient(url="YOUR_URL", api_key="YOUR_KEY", timeout=30)
print(client.get_collections())
EOF
```

### Issue: Authentication failed

**Check:**

- API key is copied correctly (no extra spaces)
- API key hasn't been revoked
- Using the correct cluster's API key

**Solution:**

- Generate a new API key in Qdrant Cloud dashboard
- Update with `./setup-qdrant.sh`

## Why Did This Happen?

Common reasons for Qdrant cluster deletion/unavailability:

1. **Free tier expiration** - Free clusters may be deleted after inactivity
2. **Account issue** - Qdrant Cloud account suspended or deleted
3. **Manual deletion** - Cluster was deleted from dashboard
4. **Wrong credentials** - Using credentials from a different/old cluster

## Qdrant Cloud Free Tier Details

**What you get:**

- 1GB storage (sufficient for ~10,000-50,000 memories)
- Unlimited requests
- No time limit
- All features included

**Limitations:**

- Single cluster only
- No SLA guarantees
- May be throttled under heavy load

**For production:**

- Consider paid tier for SLA and support
- Or migrate to Azure AI Search (requires code changes)

## Alternative: Local Qdrant (Not Recommended)

For testing only, you can use local Qdrant:

**Pros:**

- No external dependency
- No cost

**Cons:**

- Data lost on container restart
- Not production-ready
- Only works with Docker Compose locally

**Setup:**

```bash
# Use local Qdrant from docker-compose
QDRANT_URL=http://qdrant:6333
QDRANT_API_KEY=None
```

## Need More Help?

1. **Qdrant Cloud Documentation:**
   https://qdrant.tech/documentation/cloud/

2. **Create Cluster Guide:**
   https://qdrant.tech/documentation/cloud/create-cluster/

3. **Check cluster status:**
   https://cloud.qdrant.io/

## Next Steps After Fix

Once Qdrant is working:

1. ✅ Test WhatsApp conversation
2. ✅ Verify memories are stored
3. ✅ Check memory retrieval works
4. ✅ Monitor for any other issues

**All commands:**

```bash
# Setup new credentials
./setup-qdrant.sh

# Test connection
./test-qdrant-connection.sh "$QDRANT_URL" "$QDRANT_API_KEY"

# Update Azure
./fix-env-vars.sh

# Monitor logs
make azure-logs

# Check status
make azure-status
```

---

**Summary:** Your Qdrant cluster needs to be recreated. Use the free tier at https://cloud.qdrant.io/ and run `./setup-qdrant.sh` to fix it in 5 minutes.
