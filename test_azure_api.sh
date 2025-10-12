#!/bin/bash
# Test Azure API to verify if chat messages fix is working

AZURE_URL="https://ava-whatsapp.calmcoast-908a8490.eastus.azurecontainerapps.io"

echo "=========================================="
echo "Testing Azure API - Chat Messages Fix"
echo "=========================================="
echo ""

echo "1️⃣  Testing /test endpoint:"
echo "----------------------------------------"
TEST_RESULT=$(curl -s "$AZURE_URL/test" 2>/dev/null)
if [ $? -eq 0 ]; then
    echo "$TEST_RESULT" | jq 2>/dev/null || echo "$TEST_RESULT"
    echo "✓ API is responding"
else
    echo "✗ API is not responding"
    exit 1
fi
echo ""

echo "2️⃣  Testing /debug_memory endpoint:"
echo "----------------------------------------"
DEBUG_RESULT=$(curl -s "$AZURE_URL/debug_memory" 2>/dev/null)
if [ $? -eq 0 ]; then
    echo "$DEBUG_RESULT" | jq 2>/dev/null || echo "$DEBUG_RESULT"
    
    STATUS=$(echo "$DEBUG_RESULT" | jq -r '.status' 2>/dev/null)
    if [ "$STATUS" = "success" ]; then
        echo "✓ Memory reader is initialized"
    else
        echo "✗ Memory reader failed to initialize"
    fi
else
    echo "✗ Debug endpoint not responding"
fi
echo ""

echo "3️⃣  Testing /conversations_list:"
echo "----------------------------------------"
CONV_RESULT=$(curl -s "$AZURE_URL/conversations_list" 2>/dev/null)
if [ $? -eq 0 ]; then
    LAST_MSG=$(echo "$CONV_RESULT" | jq -r '.[0].last_message' 2>/dev/null)
    
    if [ "$LAST_MSG" = "null" ] || [ -z "$LAST_MSG" ]; then
        echo "✗ No conversations found or error"
        echo "Response: $CONV_RESULT" | jq 2>/dev/null || echo "$CONV_RESULT"
    else
        echo "Last message preview:"
        echo "  \"${LAST_MSG:0:100}...\""
        echo ""
        
        # Check if it's semantic memory or actual chat
        if echo "$LAST_MSG" | grep -qi "user is interested\\|user prefers\\|user mentioned\\|user's name is"; then
            echo "❌ FAIL: Still returning SEMANTIC MEMORY statements"
            echo ""
            echo "Example semantic statement detected:"
            echo "  - \"User is interested in...\""
            echo "  - \"User prefers...\""
            echo ""
            echo "This means the fix hasn't been deployed to Azure yet."
        else
            echo "✅ PASS: Returning ACTUAL CHAT MESSAGES"
            echo ""
            echo "The fix is working correctly in Azure!"
        fi
    fi
else
    echo "✗ Conversations endpoint not responding"
fi
echo ""

echo "4️⃣  Testing /conversations_stats:"
echo "----------------------------------------"
STATS_RESULT=$(curl -s "$AZURE_URL/conversations_stats" 2>/dev/null)
if [ $? -eq 0 ]; then
    echo "$STATS_RESULT" | jq 2>/dev/null || echo "$STATS_RESULT"
else
    echo "✗ Stats endpoint not responding"
fi
echo ""

echo "=========================================="
echo "Test Complete"
echo "=========================================="

