from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ai_companion.interfaces.whatsapp.whatsapp_response import whatsapp_router
from ai_companion.interfaces.api_endpoints import conversations_router

app = FastAPI(title="Upaai AI Companion API", version="1.0.0")

# CORS middleware for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://upaai.in",
        "https://www.upaai.in",
        "http://localhost:3000",  # For local development
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Include routers
app.include_router(whatsapp_router)
app.include_router(conversations_router)
