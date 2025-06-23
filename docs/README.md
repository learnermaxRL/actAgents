# AI Agents Framework Documentation

Welcome to the documentation for the Shopping AI System! This guide will help you understand the architecture, core concepts, and how to create your own custom agents using this framework.

---

## Table of Contents

1. [Overview](#overview)
2. [Directory Structure](#directory-structure)
3. [Core Concepts](#core-concepts)
4. [How to Create a New Agent (Step-by-Step)](#how-to-create-a-new-agent-step-by-step)
5. [Agent Registry & Factory](#agent-registry--factory)
6. [Working Example: Customer Service Agent](#working-example-customer-service-agent)
7. [Server & Frontend Testing](#server--frontend-testing)
8. [Best Practices](#best-practices)
9. [Extending and Integrating Agents](#extending-and-integrating-agents)
10. [References & Further Reading](#references--further-reading)

---

## Overview

The Shopping AI System is a modular, extensible framework for building AI-powered agents that can handle complex tasks, such as customer service, product recommendations, web search, and more. Agents are built on top of a robust `BaseAgent` class, and can be easily extended with new tools, prompts, and behaviors.

---

## Directory Structure

A typical agent implementation follows this structure:

```
examples/
  your_agent/
    agent.py
    tools/
      your_tool.py
    tools_schemas/
      your_tool_schema.py
    prompts/
      your_agent_prompt.py
```

- **agent.py**: Main agent class (inherits from `BaseAgent`)
- **tools/**: Python modules implementing tool functions
- **tools_schemas/**: JSON schemas describing tool interfaces
- **prompts/**: System prompts and persona definitions

---

## Core Concepts

### 1. **BaseAgent**
The abstract base class for all agents. Handles conversation management, tool calls, state management, and logging.

### 2. **Tools & Tool Schemas**
- **Tool Schema**: Defines the interface (name, parameters, description) for a tool.
- **Tool Function**: Implements the actual logic (e.g., product search, web scraping).

### 3. **Prompts**
System prompts define the agent's persona, behavior, and response style.

### 4. **State Management**
Agents can maintain conversation state, chat history, and tool call history using Redis or other backends.

### 5. **Agent Registry & Factory**
Centralized system for managing different agent types, their creation, and lifecycle management.

---

## How to Create a New Agent (Step-by-Step)

### 1. **Create the Agent Class**

Create a new directory for your agent (e.g., `examples/my_agent/`).

**agent.py**
```python
from core.agents.common.base_agent import BaseAgent
from utils.logger import get_logger
from .prompts.my_agent_prompt import MY_AGENT_PROMPT
from .tools_schemas.my_tool_schema import my_tool_schema
from .tools.my_tool import my_tool_function

class MyAgent(BaseAgent):
    def __init__(self, **kwargs):
        super().__init__(
            agent_name="my_agent",
            **kwargs
        )
        self.logger = get_logger("my_agent")
        self.my_prompt = MY_AGENT_PROMPT
        self._register_tools()

    def _register_tools(self):
        self.register_tool(my_tool_schema, my_tool_function)
```

### 2. **Define Tool Schemas**

**tools_schemas/my_tool_schema.py**
```python
my_tool_schema = {
    "type": "function",
    "function": {
        "name": "my_tool_function",
        "description": "Describe what this tool does.",
        "parameters": {
            "type": "object",
            "properties": {
                "param1": {"type": "string", "description": "Description of param1"},
                # ...
            },
            "required": ["param1"]
        }
    }
}
```

### 3. **Implement Tool Functions**

**tools/my_tool.py**
```python
async def my_tool_function(**kwargs):
    # Implement your tool logic here
    return {"result": "success"}
```

### 4. **Create Prompts**

**prompts/my_agent_prompt.py**
```python
MY_AGENT_PROMPT = """
You are MyAgent, an expert in your domain. Respond helpfully and concisely.
"""
```

### 5. **Register Tools in the Agent**

Call `self.register_tool(schema, function)` for each tool in your agent's `_register_tools` method.

### 6. **Process Messages**

Override `process_message` if you need custom logic, or use the base implementation:

```python
async def process_message(self, message: str, chat_id: str, stream: bool = True, **kwargs):
    async for chunk in super().process_message(
        message=message,
        chat_id=chat_id,
        system_prompt=self.my_prompt,
        stream=stream,
        save_to_history=True,
        use_stored_history=True,
        **kwargs
    ):
        yield chunk
```

---

## Agent Registry & Factory

The system includes a centralized Agent Registry and Factory for managing different agent types. This allows you to:

- **Register new agent types** with the system
- **Create agents dynamically** based on type
- **Cache agent instances** for efficiency
- **Manage agent lifecycles** properly

### Quick Registration

To register your new agent:

1. **Add to AgentTypeEnums**:
   ```python
   class AgentTypeEnums(Enum):
       CUSTOMER_SERVICE = "customer_service"
       YOUR_AGENT = "your_agent"  # Add your type
   ```

2. **Register in AgentRegistry**:
   ```python
   AgentRegistry._agents[AgentTypeEnums.YOUR_AGENT] = YourAgentClass
   ```

3. **Use through Factory**:
   ```python
   agent = await agent_factory.create_agent("your_agent", agent_id="user123")
   ```

For detailed information about the Agent Registry system, see [Agent Registry Documentation](agent_registry.md).

---

## Working Example: Customer Service Agent

A complete working example is available in `examples/customer_service_agent/` that demonstrates:

### Features
- **Ticket Management**: Create and update support tickets
- **FAQ Search**: Search knowledge base for common questions
- **Professional Persona**: Empathetic customer service representative
- **Interactive Demo**: Command-line interface for testing

### Tools Included
- `create_ticket`: Create new support tickets
- `update_ticket`: Update existing ticket status
- `search_faq`: Search FAQ database for answers

### Usage
```bash
# Run the interactive demo
cd examples/customer_service_agent
python agent.py
```

### Example Interactions
```
You: I need help with my order
Agent: I understand you need help with your order. Let me search our FAQ for order-related information...

You: Create a ticket for billing issue
Agent: I'll help you create a support ticket for your billing issue. I'll need some information to set this up properly...
```

This example shows how to build a practical, production-ready agent with real-world functionality.

---

## Server & Frontend Testing

The system includes a complete FastAPI server and a sample frontend UI for testing and demonstration purposes.

### FastAPI Server

The server is built with FastAPI and provides a robust API for agent interactions.

#### **Server Features**
- **FastAPI Framework**: Modern, fast web framework with automatic API documentation
- **Streaming Responses**: Real-time streaming of agent responses
- **Agent Management**: Dynamic agent creation and lifecycle management
- **State Management**: Redis-backed conversation state and history
- **Health Monitoring**: Built-in health checks and monitoring endpoints
- **CORS Support**: Cross-origin resource sharing for web frontend integration

#### **Server Endpoints**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Service information and status |
| `/health` | GET | Health check endpoint |
| `/docs` | GET | Interactive API documentation (Swagger UI) |
| `/redoc` | GET | Alternative API documentation |
| `/agents/chat` | POST | Chat with agents (streaming response) |

#### **Starting the Server**

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp setup_env.sh .env
# Edit .env with your API keys

# Start the server
python main.py
```

The server will start on `http://localhost:8000` by default.

#### **Server Configuration**

Key environment variables for the server:

```bash
# Model API Configuration
MODEL_API_KEY=your_api_key
MODEL_DEPLOYMENT_NAME=gpt-4o
MODEL_API_BASE_URL=https://api.openai.com/v1

# Server Configuration
AGENTS_SERVER_PORT=8000
LOG_LEVEL=info

# Storage Configuration
STORAGE_TYPE=redis
REDIS_URL=redis://localhost:6379

# Agent Configuration
ENABLE_STATE_MANAGEMENT=true
STORE_TOOL_HISTORY=true
MAX_TOOL_ITERATIONS=4
```

#### **API Usage Example**

```bash
# Chat with the customer service agent
curl -X POST "http://localhost:8000/agents/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I need help with my order",
    "chat_id": "chat123",
    "user_id": "user123",
    "agent_type": "customer_service"
  }'
```

### Sample Frontend UI

A complete web-based chat interface is provided in `frontend/testui.html` for easy testing and demonstration.

#### **Frontend Features**
- **Modern UI Design**: Clean, responsive interface with gradient backgrounds
- **Real-time Chat**: Live streaming of agent responses
- **Example Queries**: Pre-built example questions for quick testing
- **Connection Status**: Visual indicators for server connectivity
- **Mobile Responsive**: Works on desktop and mobile devices
- **Local Storage**: Persists user ID and chat sessions

#### **Frontend Capabilities**
- **Streaming Responses**: Real-time display of agent responses as they're generated
- **Error Handling**: Graceful handling of connection issues and errors
- **Typing Indicators**: Visual feedback when the agent is processing
- **Message History**: Scrollable chat history with user and agent messages
- **Quick Actions**: Clickable example queries for common use cases

#### **Using the Frontend**

1. **Start the server** (see above)
2. **Open the frontend**:
   ```bash
   # Open in browser
   open frontend/testui.html
   # Or navigate to the file in your browser
   ```

3. **Test the interface**:
   - The interface will automatically connect to the server
   - Use the example queries or type your own messages
   - Watch real-time responses from the customer service agent

#### **Frontend Configuration**

The frontend is configured to connect to `http://localhost:8000` by default. To change the server URL, edit the `apiUrl` variable in the JavaScript code:

```javascript
class CustomerServiceAIChat {
    constructor() {
        this.apiUrl = 'http://localhost:8000'; // Change this for different server
        // ...
    }
}
```

#### **Example Frontend Interactions**

The frontend includes several example queries you can click to test:

- "I need help with my order"
- "Create a support ticket for billing issue"
- "What is your return policy?"
- "How do I reset my password?"

#### **Frontend Customization**

The frontend can be easily customized:

- **Styling**: Modify the CSS in the `<style>` section
- **Agent Type**: Change the `agent_type` in the request payload
- **Examples**: Add or modify the example queries
- **Branding**: Update colors, logos, and text to match your brand

### Testing Workflow

1. **Start the server**: `python main.py`
2. **Open the frontend**: `frontend/testui.html`
3. **Test basic functionality**: Try the example queries
4. **Test custom queries**: Type your own questions
5. **Monitor the server**: Check logs and API documentation at `/docs`

### Docker Deployment

For production deployment, use Docker:

```bash
# Build and run with Docker Compose
docker-compose up --build

# The frontend will be available at the same URL
# (you may need to copy the HTML file to a web server)
```

The server and frontend provide a complete testing and demonstration environment for the AI agent system.

---

## Best Practices

- **Keep tools modular**: One schema and function per tool.
- **Use clear, descriptive prompts**: Guide the agent's behavior and persona.
- **Leverage state management**: For context-aware, multi-turn conversations.
- **Log important actions**: For debugging and monitoring.
- **Document your agent**: Add docstrings and comments.
- **Register with the factory**: Use the agent registry for proper lifecycle management.

---

## Extending and Integrating Agents

- **Add new tools**: Create new schemas and functions, then register them.
- **Update prompts**: Refine the agent's persona and instructions.
- **Use state management**: For advanced conversation and tool call tracking.
- **Integrate with APIs**: Tools can call external APIs, databases, or services.
- **Register new agent types**: Use the agent registry for system-wide availability.

---

## References & Further Reading

- [Code Organization & Architecture](code_organization.md) - Detailed architecture documentation
- [Agent Registry & Factory](agent_registry.md) - Complete guide to the agent registry system
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [OpenAI Function Calling](https://platform.openai.com/docs/guides/function-calling)
- [Redis Documentation](https://redis.io/docs/)

---

For more advanced usage, see the full CustomerServiceAgent implementation and explore the `core/` and `api/` directories for backend integration. 