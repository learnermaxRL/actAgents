"""FastAPI router for agents with streaming chat support."""

import asyncio
import json
from typing import Dict, Any, Optional
from enum import Enum

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from core.agents.common.agent_factory import AgentTypeEnums, agent_factory
from utils.logger import get_logger
from api.models import ChatRequest, ChatResponse

# Create router with prefix
agents_router = APIRouter(prefix="/agents", tags=["agents"])
logger = get_logger("agents_router")


@agents_router.post("/chat")
async def chat_streaming(
    request: ChatRequest,
):
    """
    Streaming chat endpoint for agent communication.
    
    Args:
        request: Chat request containing message and metadata
        background_tasks: Background tasks for cleanup
    
    Returns:
        StreamingResponse with agent response chunks
    """
    try:
        logger.info(
            f"Chat request received - User: {request.user_id}, "
            f"Chat: {request.chat_id}, Agent: {request.agent_type.value}"
        )
        
        # Validate agent type
        if not agent_factory.is_agent_type_supported(request.agent_type.value):
            raise HTTPException(
                status_code=400,
                detail=f"Agent type '{request.agent_type.value}' is not supported. "
                       f"Available types: {agent_factory.get_available_agent_types()}"
            )
        
        # Create unique agent ID combining user and chat
        agent_id = f"{request.user_id}_{request.chat_id}"
        
        # Get or create agent
        agent = await agent_factory.get_or_create_agent(
            agent_type=request.agent_type.value,
            agent_id=agent_id
        )
        
        # Create streaming generator
        async def generate_response():
            """Generate streaming response chunks."""
            try:
                
                # Stream response from agent
                async for chunk in agent.process_message(
                    message=request.message,
                    chat_id=request.chat_id,
                    stream=True
                ):
                    # Format as Server-Sent Event
                    yield f"data: {json.dumps({'chunk': chunk, 'type': 'content'})}\n\n"
                
                # Send completion signal
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                
            except Exception as e:
                logger.error(f"Error in streaming response: {e}")
                # Send error to client
                error_data = {
                    'type': 'error',
                    'error': str(e),
                    'message': 'An error occurred while processing your request.'
                }
                yield f"data: {json.dumps(error_data)}\n\n"
        
        # Return streaming response
        return StreamingResponse(
            generate_response(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/plain; charset=utf-8"
            }
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error in chat endpoint: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@agents_router.post("/chat/non-streaming", response_model=ChatResponse)
async def chat_non_streaming(
    request: ChatRequest,
    background_tasks: BackgroundTasks
):
    """
    Non-streaming chat endpoint for agent communication.
    
    Args:
        request: Chat request containing message and metadata
        background_tasks: Background tasks for cleanup
    
    Returns:
        Complete agent response
    """
    try:
        logger.info(
            f"Non-streaming chat request - User: {request.user_id}, "
            f"Chat: {request.chat_id}, Agent: {request.agent_type.value}"
        )
        
        # Validate agent type
        if not agent_factory.is_agent_type_supported(request.agent_type.value):
            raise HTTPException(
                status_code=400,
                detail=f"Agent type '{request.agent_type.value}' is not supported. "
                       f"Available types: {agent_factory.get_available_agent_types()}"
            )
        
        # Create unique agent ID
        agent_id = f"{request.user_id}_{request.chat_id}"
        
        # Get or create agent
        agent = await agent_factory.get_or_create_agent(
            agent_type=request.agent_type.value,
            agent_id=agent_id
        )
        
        # Add metadata to chat context if provided
        if request.extra_metadata:
            await agent.update_chat_state(
                chat_id=request.chat_id,
                state_update={
                    "user_id": request.user_id,
                    "extra_metadata": request.extra_metadata
                }
            )
        
        # Get complete response (non-streaming mode)
        complete_response = ""
        async for chunk in agent.process_message(
            message=request.message,
            chat_id=request.chat_id,
            stream=False
        ):
            complete_response += chunk
        
        return ChatResponse(
            response=complete_response,
            chat_id=request.chat_id,
            user_id=request.user_id,
            agent_type=request.agent_type.value
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error in non-streaming chat endpoint: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@agents_router.get("/info")
async def get_agents_info():
    """
    Get information about available agents and factory status.
    
    Returns:
        Information about agents and factory
    """
    try:
        factory_info = agent_factory.get_agent_info()
        
        return {
            "available_agent_types": factory_info["available_agent_types"],
            "storage_type": factory_info["storage_type"],
            "state_management_enabled": factory_info["state_management_enabled"],
            "cached_agents_count": len(factory_info["cached_agents"]),
            "supported_endpoints": [
                "/agents/chat (streaming)",
                "/agents/chat/non-streaming",
                "/agents/info"
            ]
        }
        
    except Exception as e:
        logger.error(f"Error getting agents info: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get agents info: {str(e)}"
        )


@agents_router.get("/health")
async def health_check():
    """
    Health check endpoint for agents router.
    
    Returns:
        Health status
    """
    try:
        # Basic health check - verify factory is working
        available_types = agent_factory.get_available_agent_types()
        
        return {
            "status": "healthy",
            "available_agents": len(available_types),
            "agent_types": available_types
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Service unhealthy: {str(e)}"
        )