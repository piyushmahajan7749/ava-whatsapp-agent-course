#!/bin/bash
# Start local API server with proper environment loading

cd /Users/piyush/Projects/cx-agent

echo "=================================================="
echo "  Starting Local API Server"
echo "=================================================="
echo ""
echo "API URL: http://localhost:8081"
echo ""
echo "Available endpoints:"
echo "  - http://localhost:8081/test"
echo "  - http://localhost:8081/conversations_list"
echo "  - http://localhost:8081/conversation/{user_id}"
echo "  - http://localhost:8081/conversations_stats"
echo "  - http://localhost:8081/debug_memory"
echo ""
echo "Your Next.js frontend (localhost:3000) can now connect!"
echo ""
echo "Press Ctrl+C to stop the server"
echo "=================================================="
echo ""

# Start the FastAPI server using uvicorn directly (better environment handling)
PYTHONPATH=src uv run uvicorn ai_companion.interfaces.whatsapp.webhook_endpoint:app --host 0.0.0.0 --port 8082 --reload

