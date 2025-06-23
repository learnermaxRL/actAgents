"""Agent Factory for managing and creating different types of agents."""

import asyncio
from typing import Dict, Type, Optional, Any, List
from abc import ABC, abstractmethod
from enum import Enum

from config.settings import settings
from core.agents.common.base_agent import BaseAgent
from examples.customer_service_agent.agent import CustomerServiceAgent
from utils.logger import get_logger


class AgentTypeEnums(Enum):
    """Enumeration of available agent types."""
    CUSTOMER_SERVICE = "customer_service"
    # GENERAL = "general"
    # Add more agent types as they are developed

# Context manager for agent lifecycle
class AgentContext:
    """Context manager for proper agent lifecycle management."""
    
    def __init__(self, agent_type: str, agent_id: Optional[str] = None, **kwargs):
        self.agent_type = agent_type
        self.agent_id = agent_id
        self.kwargs = kwargs
        self.agent: Optional[BaseAgent] = None
    
    async def __aenter__(self) -> BaseAgent:
        self.agent = await agent_factory.create_agent(
            self.agent_type, self.agent_id, **self.kwargs
        )
        return self.agent
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.agent:
            await agent_factory.cleanup_agent(self.agent_type, self.agent_id)

class AgentRegistry:
    """Registry for mapping agent types to their implementations."""
    
    _agents: Dict[AgentTypeEnums, Type[BaseAgent]] = {
        AgentTypeEnums.CUSTOMER_SERVICE: CustomerServiceAgent,
        # Register other agents here as they are implemented
    }
    
    @classmethod
    def register_agent(cls, agent_type: AgentTypeEnums, agent_class: Type[BaseAgent]):
        """Register a new agent type."""
        cls._agents[agent_type] = agent_class
    
    @classmethod
    def get_agent_class(cls, agent_type: AgentTypeEnums) -> Optional[Type[BaseAgent]]:
        """Get the agent class for a given type."""
        return cls._agents.get(agent_type)
    
    @classmethod
    def get_available_agents(cls) -> List[AgentTypeEnums]:
        """Get list of available agent types."""
        return list(cls._agents.keys())


class AgentFactory:
    """Factory for creating and managing agent instances."""
    
    def __init__(self):
        self.logger = get_logger("agent_factory")
        self._agent_cache: Dict[str, BaseAgent] = {}
        self._initialized_agents: Dict[str, bool] = {}
    
    def _get_agent_config(self, agent_type: AgentTypeEnums, **overrides) -> Dict[str, Any]:
        """Get configuration for agent based on settings and overrides."""
        base_config = {

            "enable_state_management": settings.enable_state_management,
            "store_tool_history": settings.store_tool_history,
            "storage_type": settings.storage_type,
            "model_name": settings.model_name,
            "model_api_base_url": settings.model_api_base_url,
            "model_api_key": settings.model_api_key
        }
        
        # Add storage-specific configuration
        if settings.storage_type == "redis":
            base_config.update({
                "redis_url": settings.redis_url,
                "redis_db": settings.redis_db,
                "redis_password": settings.redis_password,
            })
        elif settings.storage_type == "postgresql":
            base_config.update({
                "postgres_url": settings.postgres_url,
            })
        
        
        # Apply overrides
        base_config.update(overrides)
        
        return base_config
    
    async def create_agent(
        self, 
        agent_type: str, 
        agent_id: Optional[str] = None,
        **kwargs
    ) -> BaseAgent:
        """
        Create a new agent instance.
        
        Args:
            agent_type: Type of agent to create (string)
            agent_id: Optional unique identifier for caching
            **kwargs: Additional configuration overrides
        
        Returns:
            Initialized agent instance
        
        Raises:
            ValueError: If agent type is not supported
        """
        try:
            # Convert string to enum
            if isinstance(agent_type, str):
                try:
                    agent_enum = AgentTypeEnums(agent_type.lower())
                except ValueError:
                    raise ValueError(f"Unsupported agent type: {agent_type}. Available: {[t.value for t in AgentTypeEnums]}")
            else:
                agent_enum = agent_type
            
            # Check if agent is cached
            cache_key = f"{agent_enum.value}_{agent_id}" if agent_id else agent_enum.value
            if cache_key in self._agent_cache:
                return self._agent_cache[cache_key]
            
            # Get agent class
            agent_class = AgentRegistry.get_agent_class(agent_enum)
            if not agent_class:
                raise ValueError(f"No implementation found for agent type: {agent_enum.value}")
            
            # Get configuration
            config = self._get_agent_config(agent_enum, **kwargs)
            
            # Create agent instance
            agent = agent_class(**config)
            
            # Initialize agent if state management is enabled
            if config.get("enable_state_management", True):
                await agent.initialize()
                self._initialized_agents[cache_key] = True
            
            # Cache the agent
            self._agent_cache[cache_key] = agent
            
            self.logger.info(f"Created and initialized {agent_enum.value} agent with ID: {agent_id or 'default'}")
            
            return agent
            
        except Exception as e:
            self.logger.error(f"Failed to create agent {agent_type}: {e}")
            raise
    
    async def get_or_create_agent(
        self, 
        agent_type: str, 
        agent_id: Optional[str] = None,
        **kwargs
    ) -> BaseAgent:
        """
        Get an existing agent from cache or create a new one.
        
        Args:
            agent_type: Type of agent to get/create
            agent_id: Optional unique identifier
            **kwargs: Additional configuration overrides
        
        Returns:
            Agent instance
        """
        cache_key = f"{agent_type}_{agent_id}" if agent_id else agent_type
        
        if cache_key in self._agent_cache:
            return self._agent_cache[cache_key]
        
        return await self.create_agent(agent_type, agent_id, **kwargs)
    
    def get_available_agent_types(self) -> List[str]:
        """Get list of available agent types as strings."""
        return [agent_type.value for agent_type in AgentRegistry.get_available_agents()]
    
    def is_agent_type_supported(self, agent_type: str) -> bool:
        """Check if an agent type is supported."""
        try:
            AgentTypeEnums(agent_type.lower())
            return True
        except ValueError:
            return False
    
    async def cleanup_agent(self, agent_type: str, agent_id: Optional[str] = None):
        """Clean up and remove an agent from cache."""
        cache_key = f"{agent_type}_{agent_id}" if agent_id else agent_type
        
        if cache_key in self._agent_cache:
            agent = self._agent_cache[cache_key]
            try:
                await agent.close()
            except Exception as e:
                self.logger.warning(f"Error closing agent {cache_key}: {e}")
            
            del self._agent_cache[cache_key]
            self._initialized_agents.pop(cache_key, None)
            
            self.logger.info(f"Cleaned up agent: {cache_key}")
    
    async def cleanup_all_agents(self):
        """Clean up all cached agents."""
        for cache_key in list(self._agent_cache.keys()):
            await self.cleanup_agent(*cache_key.split("_", 1))
        
        self.logger.info("Cleaned up all agents")
    
    def get_agent_info(self) -> Dict[str, Any]:
        """Get information about the factory and cached agents."""
        return {
            "available_agent_types": self.get_available_agent_types(),
            "cached_agents": list(self._agent_cache.keys()),
            "initialized_agents": list(self._initialized_agents.keys()),
            "storage_type": settings.storage_type,
            "state_management_enabled": settings.enable_state_management,
        }


# Global factory instance
agent_factory = AgentFactory()





