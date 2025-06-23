# AI Agent System

An AI-powered agent service built with FastAPI and modern AI models, featuring a customer service agent as the primary example.

## Features

- AI-powered customer service assistance
- Modular agent architecture
- Tool-based functionality
- State management with Redis
- Streaming responses
- Docker support
- **FastAPI server** with automatic API documentation
- **Sample frontend UI** for testing and demonstration

## Quick Start

### Prerequisites

- Python 3.8+
- Docker (optional)
- Redis (for state management)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd shopping_ai_system
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   cp setup_env.sh .env
   # Edit .env with your configuration
   ```

4. **Run the service**
   ```bash
   python main.py
   ```

### Using Docker

```bash
# Build and run with Docker Compose
docker-compose up --build

# Or build manually
docker build -t ai-agent-system .
docker run -p 8000:8000 ai-agent-system
```

## Usage

### API Endpoints

- `POST /agents/chat` - Chat with an agent
- `GET /health` - Health check
- `GET /` - Service info
- `GET /docs` - Interactive API documentation

### Example Request

```bash
curl -X POST "http://localhost:8000/agents/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I need help with my order",
    "chat_id": "chat123",
    "user_id": "user123",
    "agent_type": "customer_service"
  }'
```

### Web Interface

Open `frontend/testui.html` in your browser for an interactive chat interface.

**Features:**
- Real-time streaming responses
- Example queries for quick testing
- Mobile-responsive design
- Connection status indicators

## Server & Frontend

### FastAPI Server

The system includes a complete FastAPI server with:

- **Streaming responses** for real-time chat
- **Agent management** with dynamic creation
- **State management** using Redis
- **Health monitoring** and API documentation
- **CORS support** for web frontend integration

**Server endpoints:**
- `/` - Service information
- `/health` - Health check
- `/docs` - Interactive API docs (Swagger UI)
- `/agents/chat` - Chat endpoint with streaming

### Sample Frontend UI

A complete web-based chat interface (`frontend/testui.html`) provides:

- **Modern UI** with gradient backgrounds
- **Real-time chat** with streaming responses
- **Example queries** for quick testing
- **Error handling** and connection status
- **Mobile responsive** design

**Quick testing:**
1. Start server: `python main.py`
2. Open: `frontend/testui.html`
3. Try example queries or type your own messages

## Agent Examples

### Customer Service Agent

The system includes a complete customer service agent example in `examples/customer_service_agent/` that demonstrates:

- Ticket management
- FAQ search
- Professional customer service persona
- Interactive CLI demo

Run the example:
```bash
cd examples/customer_service_agent
python agent.py
```

## Documentation

- [System Documentation](docs/README.md) - Complete guide to the system
- [Code Organization](docs/code_organization.md) - Architecture and patterns
- [Agent Registry](docs/agent_registry.md) - Agent management system

## Configuration

Key environment variables:

```bash
MODEL_API_KEY=your_api_key
MODEL_DEPLOYMENT_NAME=gpt-4o
MODEL_API_BASE_URL=https://api.openai.com/v1
STORAGE_TYPE=redis
REDIS_URL=redis://localhost:6379
AGENTS_SERVER_PORT=8000
```

## Development

### Project Structure

```
shopping_ai_system/
├── api/                    # API layer
├── config/                 # Configuration
├── core/                   # Core business logic
├── examples/               # Example agents
├── docs/                   # Documentation
├── frontend/               # Web interface
└── utils/                  # Utilities
```

### Adding New Agents

1. Create agent class inheriting from `BaseAgent`
2. Define tool schemas and functions
3. Create system prompts
4. Register with the agent factory

See the documentation for detailed instructions.

## Quick Agent Creation

Want to create a new agent quickly? Here are the minimal steps:

### 1. Create Agent Directory
```bash
mkdir examples/my_agent
mkdir examples/my_agent/tools
mkdir examples/my_agent/tools_schemas
mkdir examples/my_agent/prompts
```

### 2. Create Agent Class
```python
# examples/my_agent/agent.py
from core.agents.common.base_agent import BaseAgent
from .prompts.my_prompt import MY_PROMPT
from .tools_schemas.my_tool import my_tool_schema
from .tools.my_tool import my_tool_function

class MyAgent(BaseAgent):
    def __init__(self, **kwargs):
        super().__init__(agent_name="my_agent", **kwargs)
        self._register_tools()
    
    def _register_tools(self):
        self.register_tool(my_tool_schema, my_tool_function)
```

### 3. Add Tool Schema
```python
# examples/my_agent/tools_schemas/my_tool.py
my_tool_schema = {
    "type": "function",
    "function": {
        "name": "my_tool_function",
        "description": "What this tool does",
        "parameters": {
            "type": "object",
            "properties": {
                "param1": {"type": "string", "description": "Description"}
            },
            "required": ["param1"]
        }
    }
}
```

### 4. Implement Tool Function
```python
# examples/my_agent/tools/my_tool.py
async def my_tool_function(**kwargs):
    # Your tool logic here
    return {"result": "success"}
```

### 5. Create Prompt
```python
# examples/my_agent/prompts/my_prompt.py
MY_PROMPT = """
You are MyAgent, an expert in your domain. Help users with their requests.
"""
```

### 6. Register Agent
```python
# core/agents/common/agent_factory.py
from examples.my_agent.agent import MyAgent

class AgentTypeEnums(Enum):
    CUSTOMER_SERVICE = "customer_service"
    MY_AGENT = "my_agent"  # Add this

class AgentRegistry:
    _agents: Dict[AgentTypeEnums, Type[BaseAgent]] = {
        AgentTypeEnums.CUSTOMER_SERVICE: CustomerServiceAgent,
        AgentTypeEnums.MY_AGENT: MyAgent,  # Add this
    }
```

### 7. Test Your Agent
```bash
# Start server
python main.py

# Test via API
curl -X POST "http://localhost:8000/agents/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hello",
    "chat_id": "test123",
    "user_id": "user123",
    "agent_type": "my_agent"
  }'
```

That's it! Your agent is now ready to use. For more details, see the [full documentation](docs/README.md).

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

MIT License is an open source license that allows for:
- Commercial use
- Modification
- Distribution
- Private use

While requiring:
- License and copyright notice inclusion 