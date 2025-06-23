"""Main FastAPI server for AI Agent Service."""

from dotenv import load_dotenv
load_dotenv()  
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from config.settings import settings
from api.agent_routes.routes import agents_router
from core.agents.common.agent_factory import agent_factory



@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    # Startup
    yield
    # Shutdown
    await agent_factory.cleanup_all_agents()


app = FastAPI(
    title="AI Agent Service",
    description="AI-powered agent service with customer service and other specialized agents",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development; restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include agents router
app.include_router(agents_router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {"service": "AI Agent Service", "status": "running"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.agent_server_port , log_level=settings.log_level)