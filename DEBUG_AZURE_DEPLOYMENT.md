# 🔍 Debug Azure Deployment - Chat Messages Issue

## ✅ Local Status: WORKING

The code is confirmed working locally - returns actual chat messages ✓

## ❌ Azure Status: NOT WORKING

Still returning semantic memory statements instead of chat messages

---

## Possible Causes

### 1. **Old Code Still Running in Azure**

The most likely issue - Azure might be using cached/old code.

### 2. **Import Path Issue**

The new module might not be imported correctly in Azure.

### 3. **Database Path Issue**

Azure uses `/app/data/memory.db` but might not have data there.

---

## 🔍 Step-by-Step Debug Process

### Step 1: Verify Azure Is Using Latest Image

```bash
# Check current image in Azure
az containerapp show \
  --name ava-whatsapp \
  --resource-group ava-whatsapp-rg \
  --query "properties.template.containers[0].image" \
  -o tsv
```

Expected: Should show `avawhatsappacr20487.azurecr.io/ava-whatsapp:latest`

---

### Step 2: Force Complete Rebuild

The issue might be Docker layer caching. Let's force a complete rebuild:

```bash
# Clean build with no cache
az acr build \
  --registry avawhatsappacr20487 \
  --image ava-whatsapp:latest \
  --no-cache \
  --file Dockerfile \
  . \
  --output table
```

Then update the container app:

```bash
az containerapp update \
  --name ava-whatsapp \
  --resource-group ava-whatsapp-rg \
  --image avawhatsappacr20487.azurecr.io/ava-whatsapp:latest
```

---

### Step 3: Check Azure Logs

```bash
# Follow logs to see if there are import errors
az containerapp logs show \
  --name ava-whatsapp \
  --resource-group ava-whatsapp-rg \
  --follow
```

Look for:

- ❌ `ModuleNotFoundError: No module named 'ai_companion.modules.memory.short_term_reader'`
- ❌ `Failed to initialize memory reader`
- ✅ `Short-term memory reader initialized successfully`

---

### Step 4: Test Azure API Endpoint

```bash
# Get your Azure URL
AZURE_URL="https://ava-whatsapp.calmcoast-908a8490.eastus.azurecontainerapps.io"

# Test the conversations list
curl -s "$AZURE_URL/conversations_list" | jq '.[0]'

# Test debug endpoint
curl -s "$AZURE_URL/debug_memory" | jq
```

**What to check:**

- If `last_message` contains phrases like "User is interested" → ❌ Still using old code
- If `last_message` contains actual chat like "Hello, I want..." → ✅ Fix is working!

---

### Step 5: Verify Files Are in Docker Image

Check if the new file exists in the built image:

```bash
# List recent builds
az acr repository show-tags \
  --name avawhatsappacr20487 \
  --repository ava-whatsapp \
  --orderby time_desc \
  --output table
```

---

## 🛠️ Recommended Fix Steps

### Option A: Complete Clean Rebuild (RECOMMENDED)

```bash
cd /Users/piyush/Projects/cx-agent

# 1. Verify files are committed
git status

# 2. Clean rebuild with no cache
az acr build \
  --registry avawhatsappacr20487 \
  --image ava-whatsapp:$(date +%s) \
  --image ava-whatsapp:latest \
  --no-cache \
  --file Dockerfile \
  . \
  --output table

# 3. Force container app restart
az containerapp revision restart \
  --name ava-whatsapp \
  --resource-group ava-whatsapp-rg

# 4. Wait 30 seconds for startup
sleep 30

# 5. Test the API
curl -s "https://ava-whatsapp.calmcoast-908a8490.eastus.azurecontainerapps.io/conversations_list" \
  | jq '.[0].last_message'
```

---

### Option B: Check if Module Is Present

Add a temporary debug endpoint to verify the module exists:

```python
# Add to conversations_api.py temporarily
@conversations_router.get("/debug_imports")
async def debug_imports():
    """Debug endpoint to verify imports."""
    import sys
    import os

    return {
        "short_term_reader_imported": "ShortTermMemoryReader" in str(sys.modules),
        "memory_reader_initialized": memory_reader is not None,
        "db_path": settings.SHORT_TERM_MEMORY_DB_PATH if memory_reader else "N/A",
        "db_exists": os.path.exists(settings.SHORT_TERM_MEMORY_DB_PATH) if memory_reader else False,
        "python_path": sys.path[:3],
    }
```

Then rebuild and test:

```bash
make azure-update
curl https://ava-whatsapp.calmcoast-908a8490.eastus.azurecontainerapps.io/debug_imports | jq
```

---

## 📋 Verification Checklist

- [ ] Local test passes (shows actual chat messages)
- [ ] Git status shows all files committed
- [ ] Docker rebuild completed without errors
- [ ] Azure container app updated successfully
- [ ] Azure logs show no import errors
- [ ] Azure `/debug_memory` endpoint works
- [ ] Azure `/conversations_list` returns actual chat (not semantic memory)
- [ ] Test message shows real chat content

---

## 🔧 Common Issues & Solutions

### Issue 1: "module not found"

**Solution**: The `short_term_reader.py` file might not be in the Docker image.

```bash
# Verify Dockerfile copies correctly
cat Dockerfile | grep "COPY src/"
# Should see: COPY src/ /app/

# The file should be at: /app/ai_companion/modules/memory/short_term_reader.py
```

### Issue 2: Database path doesn't exist

**Solution**: Azure might not have the database file.

```bash
# Check if Azure File Share has the database
az storage file list \
  --account-name avawhatsappstorage20487 \
  --share-name ava-data \
  --output table
```

### Issue 3: Import works but still returns semantic memory

**Solution**: The API might be importing the old `vector_store` due to import caching.

**Fix**: Add this to conversations_api.py at the top:

```python
import importlib
import sys

# Force reload of memory modules
if 'ai_companion.modules.memory.short_term_reader' in sys.modules:
    importlib.reload(sys.modules['ai_companion.modules.memory.short_term_reader'])
```

---

## 🎯 Quick Test Script

Save this as `test_azure_api.sh`:

```bash
#!/bin/bash
AZURE_URL="https://ava-whatsapp.calmcoast-908a8490.eastus.azurecontainerapps.io"

echo "Testing Azure API..."
echo ""

echo "1. Testing /test endpoint:"
curl -s "$AZURE_URL/test" | jq
echo ""

echo "2. Testing /debug_memory endpoint:"
curl -s "$AZURE_URL/debug_memory" | jq
echo ""

echo "3. Testing /conversations_list:"
RESULT=$(curl -s "$AZURE_URL/conversations_list" | jq '.[0].last_message' -r)
echo "Last message: $RESULT"
echo ""

if echo "$RESULT" | grep -qi "user is interested\\|user prefers\\|user mentioned"; then
    echo "❌ FAIL: Still returning semantic memory statements"
else
    echo "✅ PASS: Returning actual chat messages"
fi
```

Run it:

```bash
chmod +x test_azure_api.sh
./test_azure_api.sh
```

---

## 📊 Expected vs Actual

### ❌ WRONG (Semantic Memory):

```json
{
  "user_id": "919303402193",
  "last_message": "User is interested in booking poojas",
  "message_count": 5
}
```

### ✅ CORRECT (Actual Chat):

```json
{
  "user_id": "919303402193",
  "last_message": "Namaste Piyush ji 😊 Kaise hain aap?",
  "message_count": 16
}
```

---

## 🚨 If Nothing Works

As a last resort, verify the deployment is using the correct endpoints:

1. Check the Dockerfile CMD line (line 39):

   ```dockerfile
   CMD ["/app/.venv/bin/fastapi", "run", "ai_companion/interfaces/whatsapp/webhook_endpoint.py", "--port", "8080", "--host", "0.0.0.0"]
   ```

2. Check that `webhook_endpoint.py` imports `conversations_router`:

   ```python
   from ai_companion.interfaces.api_endpoints import conversations_router
   ```

3. Check that `conversations_api.py` uses `ShortTermMemoryReader`:
   ```python
   from ai_companion.modules.memory.short_term_reader import ShortTermMemoryReader
   ```

---

## 🎉 Success Criteria

You'll know it's working when:

1. ✅ Azure logs show: "✓ Short-term memory reader initialized successfully"
2. ✅ `/debug_memory` returns success status
3. ✅ `/conversations_list` shows real chat messages
4. ✅ No "User is interested" or similar semantic statements

**Status**: Ready to debug Azure deployment
