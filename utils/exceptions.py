"""Custom exceptions for the AI agent system."""


class AIAgentException(Exception):
    """Base exception for AI agent system."""
    pass


class LLMServiceException(AIAgentException):
    """Exception raised for LLM service errors."""
    pass


class StateServiceException(AIAgentException):
    """Exception raised for state management service errors."""
    pass


class ProductServiceException(AIAgentException):
    """Exception raised for product service errors."""
    pass


class WebSearchException(AIAgentException):
    """Exception raised for web search errors."""
    pass


class AgentException(AIAgentException):
    """Exception raised for agent-related errors."""
    pass


class ToolCallException(AIAgentException):
    """Exception raised for tool call errors."""
    pass


class ConfigurationException(AIAgentException):
    """Exception raised for configuration errors."""
    pass 