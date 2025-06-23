"""Factory function to create web search service instances."""

from typing import Dict, Any, Optional
from utils.exceptions import WebSearchException
from .base_web_search import BaseWebSearchService



def create_web_search_service(
    provider: str = "tavily",
    api_key: Optional[str] = None,
    **kwargs
) -> 'BaseWebSearchService':
    """
    Factory function to create web search service instances.
    
    Args:
        provider: Search provider name (currently supports: "tavily")
        api_key: API key for the search provider
        **kwargs: Additional configuration parameters
        
    Returns:
        BaseWebSearchService: Configured search service instance
        
    Raises:
        WebSearchException: If provider is unsupported or configuration is invalid
    """
    
    # Map of available providers to their implementation classes
    providers = {
        "tavily": "TavilyWebSearchService",
        # Future providers can be added here:
        # "google": "GoogleWebSearchService",
        # "bing": "BingWebSearchService",
    }
    
    if provider not in providers:
        available_providers = list(providers.keys())
        raise WebSearchException(
            f"Unsupported search provider: '{provider}'. "
            f"Available providers: {available_providers}"
        )
    
    if not api_key:
        raise WebSearchException(f"API key is required for {provider} search provider")
    
    # Import and instantiate the appropriate service class
    if provider == "tavily":
        from .tavily import TavilyWebSearchService
        return TavilyWebSearchService(api_key=api_key, **kwargs)
    
    # This should never be reached due to the check above, but keeping for safety
    raise WebSearchException(f"Provider '{provider}' is recognized but not implemented")