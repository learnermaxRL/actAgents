"""Configuration settings for the AI agent system."""

import os
from typing import Optional, List
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    """Application settings."""
    
    # LLM Configuration - Generic Model API
    model_api_key: str = os.getenv("MODEL_API_KEY", "")
    model_deployment_name: str = os.getenv("MODEL_DEPLOYMENT_NAME", "gpt-4o-mini")
    model_api_base_url: str = os.getenv("MODEL_API_BASE_URL", "")
    model_name: str = os.getenv("MODEL_DEPLOYMENT_NAME", "gpt-4o")
    
    # Backend Storage Configuration
    storage_type: str = os.getenv("STORAGE_TYPE", "redis")  # redis, memory, postgresql
    
    # Redis Configuration
    redis_host: str = os.getenv("REDIS_HOST", "localhost")
    redis_port: int = int(os.getenv("REDIS_PORT", "6379"))
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    redis_db: int = int(os.getenv("REDIS_DB", "0"))
    redis_password: Optional[str] = os.getenv("REDIS_PASSWORD","")
    
    
    # Agent System Configuration
    enable_state_management: bool = os.getenv("ENABLE_STATE_MANAGEMENT", "true").lower() == "true"
    store_tool_history: bool = os.getenv("STORE_TOOL_HISTORY", "true").lower() == "true"
    max_tool_iterations: int = int(os.getenv("MAX_TOOL_ITERATIONS", "4"))
    chat_history_limit: int = int(os.getenv("CHAT_HISTORY_LIMIT", "5"))
   

    agent_server_port: int = int(os.getenv("AGENTS_SERVER_PORT", "8000"))
    log_level: str = os.getenv("LOG_LEVEL", "info")
    
    # Performance Configuration
    
    class Config:
        case_sensitive = False


settings:Settings = Settings()