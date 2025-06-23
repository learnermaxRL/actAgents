# Code Organization & Architecture

This document provides a comprehensive overview of the Shopping AI System's code organization, architecture patterns, and how different components interact with each other.

---

## Table of Contents

1. [Project Structure](#project-structure)
2. [Core Architecture](#core-architecture)
3. [Agent System](#agent-system)
4. [State Management](#state-management)
5. [API Layer](#api-layer)
6. [Configuration Management](#configuration-management)
7. [Tool System](#tool-system)
8. [Agent Registry & Factory](#agent-registry--factory)
9. [Development Patterns](#development-patterns)

---

## Project Structure

```
shopping_ai_system/
├── api/                          # API layer
│   ├── agent_routes/            # FastAPI routes for agents
│   └── models.py                # Pydantic models for API
├── config/                      # Configuration management
│   └── settings.py              # Application settings
├── core/                        # Core business logic
│   ├── agents/                  # Agent implementations
│   │   └── common/              # Shared agent components
│   │       ├── base_agent.py    # Abstract base agent class
│   │       └── agent_factory.py # Agent factory and registry
│   ├── services/                # Business services
│   │   ├── search/              # Search functionality
│   │   └── state_management/    # State management services
│   └── exceptions.py            # Custom exceptions
├── examples/                    # Example agents and implementations
│   └── customer_service_agent/  # Complete customer service agent example
├── utils/                       # Utility functions and helpers
│   ├── logger.py                # Logging utilities
│   └── chat_logger.py           # Chat-specific logging
├── main.py                      # FastAPI application entry point
└── requirements.txt             # Python dependencies
```

---

## Core Architecture

### 1. **Layered Architecture**

The system follows a clean layered architecture:

```
┌─────────────────────────────────────┐
│           API Layer                 │  ← FastAPI routes, request/response models
├─────────────────────────────────────┤
│         Business Logic              │  ← Agents, services, core functionality
├─────────────────────────────────────┤
│         Data Access Layer           │  ← State management, storage services
├─────────────────────────────────────┤
│         Infrastructure              │  ← Configuration, logging, utilities
└─────────────────────────────────────┘
```

### 2. **Dependency Injection**

The system uses dependency injection through the agent factory pattern:

```python
# Agent creation through factory
agent = await agent_factory.create_agent("customer_service", agent_id="user123")

# Configuration injection
config = {
    "enable_state_management": True,
    "storage_type": "redis",
    "model_name": "gpt-4o"
}
```

---

## Agent System

### 1. **BaseAgent Class**

The `BaseAgent` class provides the foundation for all agents:

```python
class BaseAgent(ABC):
    def __init__(self, agent_name: str, **kwargs):
        # Core agent setup
        self.agent_name = agent_name
        self.tools: List[Dict] = []
        self.available_functions: Dict[str, Callable] = {}
        
        # State management
        self.state_service = ChatStateManagerService(...)
        
        # Model configuration
        self.model_name = model_name
        self.model_api_key = model_api_key
```

**Key Responsibilities:**
- Tool registration and management
- Conversation handling with LLM
- State management integration
- Error handling and logging
- Streaming response generation

### 2. **Agent Lifecycle**

```python
# 1. Agent Creation
agent = await agent_factory.create_agent("customer_service")

# 2. Agent Initialization
await agent.initialize()

# 3. Message Processing
async for chunk in agent.process_message(message, chat_id):
    yield chunk

# 4. Agent Cleanup
await agent.close()
```

---

## State Management

### 1. **ChatStateManagerService**

Manages conversation state, history, and tool calls:

```python
class ChatStateManagerService:
    async def add_message(self, chat_id: str, message: Dict):
        # Store user/assistant messages
    
    async def add_tool_call(self, chat_id: str, tool_call: Dict):
        # Store tool execution details
    
    async def get_full_context(self, chat_id: str, k_turns: int = 4):
        # Retrieve conversation context
```

### 2. **Storage Backends**

Supports multiple storage backends:

- **Redis**: Fast, in-memory storage (default)
- **Memory**: In-process storage for testing
- **PostgreSQL**: Persistent storage for production

### 3. **State Structure**

```json
{
  "chat_history": [
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi there!"}
  ],
  "tool_history": [
    {
      "tool_name": "create_ticket",
      "arguments": {"customer_name": "John Doe"},
      "result": {...},
      "duration_ms": 150
    }
  ],
  "chat_state": {
    "user_preferences": {...},
    "current_context": {...}
  }
}
```

---

## API Layer

### 1. **FastAPI Integration**

```python
# Router setup
agents_router = APIRouter(prefix="/agents", tags=["agents"])

# Streaming chat endpoint
@agents_router.post("/chat")
async def chat_streaming(request: ChatRequest):
    agent = await agent_factory.get_or_create_agent(
        agent_type=request.agent_type.value,
        agent_id=f"{request.user_id}_{request.chat_id}"
    )
    
    return StreamingResponse(
        generate_response(agent, request),
        media_type="text/plain"
    )
```

### 2. **Request/Response Models**

```python
class ChatRequest(BaseModel):
    message: str
    chat_id: str
    user_id: str
    agent_type: AgentTypeEnums
    extra_metadata: Optional[Dict[str, Any]]

class ChatResponse(BaseModel):
    content: str
    chat_id: str
    agent_type: str
```

---

## Configuration Management

### 1. **Settings Class**

```python
class Settings(BaseSettings):
    # Model Configuration
    model_api_key: str = os.getenv("MODEL_API_KEY", "")
    model_deployment_name: str = os.getenv("MODEL_DEPLOYMENT_NAME", "gpt-4o")
    model_api_base_url: str = os.getenv("MODEL_API_BASE_URL", "")
    
    # Storage Configuration
    storage_type: str = os.getenv("STORAGE_TYPE", "redis")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    # Agent Configuration
    enable_state_management: bool = os.getenv("ENABLE_STATE_MANAGEMENT", "true").lower() == "true"
    max_tool_iterations: int = int(os.getenv("MAX_TOOL_ITERATIONS", "4"))
```

### 2. **Environment Variables**

The system uses environment variables for configuration:

```bash
# Model API
MODEL_API_KEY=your_api_key
MODEL_DEPLOYMENT_NAME=gpt-4o
MODEL_API_BASE_URL=https://api.openai.com/v1

# Storage
STORAGE_TYPE=redis
REDIS_URL=redis://localhost:6379

# Agent Settings
ENABLE_STATE_MANAGEMENT=true
MAX_TOOL_ITERATIONS=4
```

---

## Tool System

### 1. **Tool Schema Definition**

```python
create_ticket_tool_schema = {
    "type": "function",
    "function": {
        "name": "create_ticket",
        "description": "Create a new support ticket for customer issues",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_name": {"type": "string"},
                "issue_type": {"type": "string"},
                "priority": {"type": "string"}
            },
            "required": ["customer_name", "issue_type"]
        }
    }
}
```

### 2. **Tool Implementation**

```python
async def create_ticket(**kwargs) -> Dict[str, Any]:
    """Create a new support ticket."""
    try:
        # Implementation logic here
        ticket_id = generate_ticket_id()
        # Store ticket in database
        return {
            "success": True,
            "ticket_id": ticket_id,
            "message": f"Ticket {ticket_id} created successfully"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
```

### 3. **Tool Registration**

```python
def _register_tools(self):
    """Register available tools for the agent."""
    self.register_tool(create_ticket_tool_schema, create_ticket)
    self.register_tool(search_faq_tool_schema, search_faq)
```

---

## Agent Registry & Factory

### 1. **AgentRegistry**

Manages agent type to class mappings:

```python
class AgentRegistry:
    _agents: Dict[AgentTypeEnums, Type[BaseAgent]] = {
        AgentTypeEnums.CUSTOMER_SERVICE: CustomerServiceAgent,
        # Add more agents here
    }
    
    @classmethod
    def register_agent(cls, agent_type: AgentTypeEnums, agent_class: Type[BaseAgent]):
        """Register a new agent type."""
        cls._agents[agent_type] = agent_class
```

### 2. **AgentFactory**

Handles agent creation, caching, and lifecycle management:

```python
class AgentFactory:
    def __init__(self):
        self._agent_cache: Dict[str, BaseAgent] = {}
        self._initialized_agents: Dict[str, bool] = {}
    
    async def create_agent(self, agent_type: str, agent_id: Optional[str] = None, **kwargs) -> BaseAgent:
        # Create and initialize agent
        agent_class = AgentRegistry.get_agent_class(agent_type)
        agent = agent_class(**config)
        await agent.initialize()
        return agent
    
    async def get_or_create_agent(self, agent_type: str, agent_id: Optional[str] = None, **kwargs) -> BaseAgent:
        # Get from cache or create new
        cache_key = f"{agent_type}_{agent_id}"
        if cache_key in self._agent_cache:
            return self._agent_cache[cache_key]
        return await self.create_agent(agent_type, agent_id, **kwargs)
```

### 3. **Agent Registration Process**

To add a new agent:

1. **Create the agent class** (inherit from BaseAgent)
2. **Add to AgentTypeEnums**:
   ```python
   class AgentTypeEnums(Enum):
       CUSTOMER_SERVICE = "customer_service"
       YOUR_AGENT = "your_agent"  # Add here
   ```
3. **Register in AgentRegistry**:
   ```python
   AgentRegistry._agents[AgentTypeEnums.YOUR_AGENT] = YourAgentClass
   ```

---

## Development Patterns

### 1. **Async/Await Pattern**

The system extensively uses async/await for non-blocking operations:

```python
async def process_message(self, message: str, chat_id: str) -> AsyncIterator[str]:
    # Async message processing
    async for chunk in self._stream_response(message, chat_id):
        yield chunk
```

### 2. **Dependency Injection**

Configuration and services are injected through constructors:

```python
def __init__(self, state_service: ChatStateManagerService = None, **kwargs):
    self.state_service = state_service or ChatStateManagerService(**kwargs)
```

### 3. **Error Handling**

Comprehensive error handling with custom exceptions:

```python
try:
    result = await self.available_functions[function_name](**function_args)
except Exception as e:
    self.chat_logger.log(LogLevel.ERROR, f"Tool call failed: {e}")
    raise ToolCallException(f"Function {function_name} failed: {e}")
```

### 4. **Logging Strategy**

Structured logging with different levels:

```python
self.chat_logger.log(
    LogLevel.INFO,
    agent=self.agent_name,
    chat_id=chat_id,
    message="Tool registered successfully"
)
```

---

## Best Practices

### 1. **Code Organization**
- Keep agents modular and focused
- Separate concerns (tools, schemas, prompts)
- Use clear naming conventions

### 2. **Error Handling**
- Always handle exceptions gracefully
- Log errors with context
- Provide meaningful error messages

### 3. **Performance**
- Use async/await for I/O operations
- Implement proper caching strategies
- Monitor and optimize tool execution times

### 4. **Testing**
- Write unit tests for tools
- Test agent interactions
- Mock external dependencies

### 5. **Documentation**
- Document all public APIs
- Include usage examples
- Keep documentation up to date

---

This architecture provides a solid foundation for building scalable, maintainable AI agent systems with clear separation of concerns and extensible design patterns. 