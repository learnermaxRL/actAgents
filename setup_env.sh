#!/bin/bash

# Setup script for AI Agent System environment

echo "Setting up environment for AI Agent System..."

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env file..."
    cat > .env << EOF
# Model API Configuration (Generic - works with OpenAI, Azure, Anthropic, etc.)
MODEL_API_KEY=your_model_api_key_here
MODEL_DEPLOYMENT_NAME=gpt-4o
MODEL_API_BASE_URL=https://api.openai.com/v1

# For Azure OpenAI, use:
# MODEL_API_KEY=your_azure_openai_api_key
# MODEL_DEPLOYMENT_NAME=your_deployment_name
# MODEL_API_BASE_URL=https://your-resource.openai.azure.com

# For Anthropic Claude, use:
# MODEL_API_KEY=your_anthropic_api_key
# MODEL_DEPLOYMENT_NAME=claude-3-sonnet-20240229
# MODEL_API_BASE_URL=https://api.anthropic.com

# Redis Configuration
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_URL=redis://redis:6379
REDIS_DB=0
REDIS_PASSWORD=

# Storage Configuration
STORAGE_TYPE=redis

# Agent System Configuration
ENABLE_STATE_MANAGEMENT=true
STORE_TOOL_HISTORY=true
MAX_TOOL_ITERATIONS=4
CHAT_HISTORY_LIMIT=5

# Server Configuration
AGENTS_SERVER_PORT=8000
LOG_LEVEL=info
EOF
    echo ".env file created successfully!"
else
    echo ".env file already exists. Skipping creation."
fi

echo "Environment setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your actual API keys and configuration"
echo "2. Install dependencies: pip install -r requirements.txt"
echo "3. Start Redis server"
echo "4. Run the application: python main.py"
echo ""
echo "For Docker setup: docker-compose up --build" 