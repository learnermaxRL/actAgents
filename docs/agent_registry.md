# Agent Registry & Factory System

This document explains how the Agent Registry and Factory system works, and how to register new agents in the Shopping AI System.

---

## Table of Contents

1. [Overview](#overview)
2. [Agent Registry](#agent-registry)
3. [Agent Factory](#agent-factory)
4. [Agent Type Enums](#agent-type-enums)
5. [Registering a New Agent](#registering-a-new-agent)
6. [Agent Lifecycle Management](#agent-lifecycle-management)
7. [Best Practices](#best-practices)

---

## Overview

The Agent Registry and Factory system provides a centralized way to manage different types of agents in the application. It handles:

- **Agent Registration**: Mapping agent types to their implementations
- **Agent Creation**: Instantiating agents with proper configuration
- **Agent Caching**: Reusing agent instances for efficiency
- **Lifecycle Management**: Proper initialization and cleanup

---

## Agent Registry

The `AgentRegistry` class maintains a mapping between agent types and their corresponding classes.

### Structure

```python
class AgentRegistry:
    _agents: Dict[AgentTypeEnums, Type[BaseAgent]] = {
        AgentTypeEnums.CUSTOMER_SERVICE: CustomerServiceAgent,
        # Add more agents here
    }
```

### Key Methods

```python
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
```

---

## Agent Factory

The `AgentFactory` class handles the creation, caching, and lifecycle management of agent instances.

### Key Features

- **Instance Caching**: Reuses agent instances for efficiency
- **Configuration Management**: Applies settings and overrides
- **State Management**: Handles initialization and cleanup
- **Error Handling**: Graceful handling of creation failures

### Core Methods

```python
async def create_agent(
    self, 
    agent_type: str, 
    agent_id: Optional[str] = None,
    **kwargs
) -> BaseAgent:
    """Create a new agent instance."""

async def get_or_create_agent(
    self, 
    agent_type: str, 
    agent_id: Optional[str] = None,
    **kwargs
) -> BaseAgent:
    """Get an existing agent from cache or create a new one."""

async def cleanup_agent(self, agent_type: str, agent_id: Optional[str] = None):
    """Clean up and remove an agent from cache."""

async def cleanup_all_agents(self):
    """Clean up all cached agents."""
```

---

## Agent Type Enums

Agent types are defined in the `AgentTypeEnums` class:

```python
class AgentTypeEnums(Enum):
    """Enumeration of available agent types."""
    CUSTOMER_SERVICE = "customer_service"
    # Add more agent types as they are developed
```

### Adding New Agent Types

1. **Add to the enum**:
   ```python
   class AgentTypeEnums(Enum):
       CUSTOMER_SERVICE = "customer_service"
       YOUR_AGENT = "your_agent"  # Add your new type
   ```

2. **Register in the registry**:
   ```python
   AgentRegistry._agents[AgentTypeEnums.YOUR_AGENT] = YourAgentClass
   ```

---

## Registering a New Agent

### Step 1: Create Your Agent Class

```python
from core.agents.common.base_agent import BaseAgent

class YourAgent(BaseAgent):
    def __init__(self, **kwargs):
        super().__init__(
            agent_name="your_agent",
            **kwargs
        )
        self._register_tools()
    
    def _register_tools(self):
        # Register your tools here
        pass
```

### Step 2: Add to AgentTypeEnums

```python
# In core/agents/common/agent_factory.py
class AgentTypeEnums(Enum):
    CUSTOMER_SERVICE = "customer_service"
    YOUR_AGENT = "your_agent"  # Add your agent type
```

### Step 3: Register in AgentRegistry

```python
# In core/agents/common/agent_factory.py
from examples.your_agent.agent import YourAgent

class AgentRegistry:
    _agents: Dict[AgentTypeEnums, Type[BaseAgent]] = {
        AgentTypeEnums.CUSTOMER_SERVICE: CustomerServiceAgent,
        AgentTypeEnums.YOUR_AGENT: YourAgent,  # Add your agent
    }
```

### Step 4: Update API Models (Optional)

If you want your agent to be available through the API:

```python
# In api/models.py
class AgentTypeEnums(Enum):
    CUSTOMER_SERVICE = "customer_service"
    YOUR_AGENT = "your_agent"  # Add your agent type
```

---

## Agent Lifecycle Management

### Creation and Initialization

```python
# Create agent through factory
agent = await agent_factory.create_agent("your_agent", agent_id="user123")

# The factory automatically:
# 1. Gets the agent class from registry
# 2. Applies configuration from settings
# 3. Initializes state management
# 4. Caches the instance
```

### Caching Strategy

- **Cache Key**: `{agent_type}_{agent_id}` or just `{agent_type}`
- **Reuse**: Same agent instance for same user/chat
- **Isolation**: Different instances for different users

### Cleanup

```python
# Clean up specific agent
await agent_factory.cleanup_agent("your_agent", "user123")

# Clean up all agents (called on application shutdown)
await agent_factory.cleanup_all_agents()
```

---

## Configuration Management

### Default Configuration

The factory applies configuration from settings:

```python
def _get_agent_config(self, agent_type: AgentTypeEnums, **overrides) -> Dict[str, Any]:
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
        })
    
    # Apply overrides
    base_config.update(overrides)
    return base_config
```

### Configuration Overrides

You can override configuration when creating agents:

```python
agent = await agent_factory.create_agent(
    "your_agent",
    agent_id="user123",
    enable_state_management=False,  # Override default
    custom_setting="value"          # Add custom settings
)
```

---

## Best Practices

### 1. **Agent Registration**

- Register agents in the factory file for consistency
- Use descriptive enum values
- Keep agent types lowercase and hyphenated

### 2. **Configuration**

- Use settings for common configuration
- Allow overrides for specific use cases
- Document configuration options

### 3. **Lifecycle Management**

- Always clean up agents when done
- Use context managers for automatic cleanup
- Handle initialization failures gracefully

### 4. **Error Handling**

```python
try:
    agent = await agent_factory.create_agent("your_agent")
except ValueError as e:
    # Handle unsupported agent type
    logger.error(f"Agent type not supported: {e}")
except Exception as e:
    # Handle other creation errors
    logger.error(f"Failed to create agent: {e}")
```

### 5. **Testing**

```python
# Test agent registration
assert AgentTypeEnums.YOUR_AGENT in AgentRegistry.get_available_agents()

# Test agent creation
agent = await agent_factory.create_agent("your_agent")
assert isinstance(agent, YourAgent)

# Test cleanup
await agent_factory.cleanup_agent("your_agent")
```

---

## Example: Complete Agent Registration

Here's a complete example of registering a new agent:

### 1. Agent Implementation

```python
# examples/your_agent/agent.py
from core.agents.common.base_agent import BaseAgent

class YourAgent(BaseAgent):
    def __init__(self, **kwargs):
        super().__init__(agent_name="your_agent", **kwargs)
        self._register_tools()
    
    def _register_tools(self):
        # Register your tools
        pass
```

### 2. Update Factory

```python
# core/agents/common/agent_factory.py
from examples.your_agent.agent import YourAgent

class AgentTypeEnums(Enum):
    CUSTOMER_SERVICE = "customer_service"
    YOUR_AGENT = "your_agent"

class AgentRegistry:
    _agents: Dict[AgentTypeEnums, Type[BaseAgent]] = {
        AgentTypeEnums.CUSTOMER_SERVICE: CustomerServiceAgent,
        AgentTypeEnums.YOUR_AGENT: YourAgent,
    }
```

### 3. Usage

```python
# Create and use your agent
agent = await agent_factory.create_agent("your_agent", agent_id="user123")
async for chunk in agent.process_message("Hello", "chat123"):
    print(chunk, end="")
```

---

This registry system provides a clean, extensible way to manage multiple agent types in your application while maintaining proper lifecycle management and configuration. 