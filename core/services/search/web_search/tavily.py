"""Updated Tavily service with enhanced API parameters and new methods."""

import asyncio
import time
from typing import Dict, List, Optional, Any, Union
from urllib.parse import urlparse
from datetime import datetime, timezone

from core.exceptions import WebSearchServiceException
from .base_web_search import BaseWebSearchService, SearchQuery, SearchResponse, SearchResult


class TavilyWebSearchService(BaseWebSearchService):
    """Enhanced Tavily implementation with full API parameter support."""
    
    def __init__(self, api_key: str, **kwargs):
        super().__init__(api_key, **kwargs)
        
        # Import tavily here to make it optional
        try:
            from tavily import AsyncTavilyClient
            self.client = AsyncTavilyClient(api_key=api_key)
        except ImportError:
            raise WebSearchServiceException("Tavily package not installed. Run: pip install tavily-python")
        
        self.logger.info("tavily_service_initialized", api_key_set=bool(api_key))
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            return urlparse(url).netloc
        except Exception:
            return ""
    
    def _prepare_tavily_params(self, search_query: SearchQuery) -> Dict[str, Any]:
        """Prepare parameters for Tavily API with all supported options."""
        params = {
            "query": search_query.query,
            "auto_parameters": search_query.auto_parameters,
            "topic": search_query.topic,
            "search_depth": search_query.search_depth,
            "chunks_per_source": search_query.chunks_per_source,
            "max_results": search_query.max_results,
            "days": search_query.days,
            "include_answer": search_query.include_answer,
            "include_raw_content": search_query.include_raw_content,
            "include_images": search_query.include_images,
            "include_image_descriptions": search_query.include_image_descriptions,
        }
        
        # Add optional parameters if specified
        if search_query.time_range:
            params["time_range"] = search_query.time_range
        
        if search_query.include_domains:
            params["include_domains"] = search_query.include_domains
            
        if search_query.exclude_domains:
            params["exclude_domains"] = search_query.exclude_domains
            
        if search_query.country:
            params["country"] = search_query.country
        
        return params
    
    def _parse_tavily_response(self, query: str, tavily_response: Dict[str, Any]) -> SearchResponse:
        """Parse Tavily API response into standardized format."""
        results = []
        
        for result in tavily_response.get('results', []):
            search_result = SearchResult(
                title=result.get('title', ''),
                url=result.get('url', ''),
                content=result.get('content', ''),
                score=result.get('score', 0.0),
                published_date=result.get('published_date'),
                source_domain=self._extract_domain(result.get('url', ''))
            )
            results.append(search_result)
        
        return SearchResponse(
            query=query,
            results=results,
            answer=tavily_response.get('answer'),
            total_results=len(results),
            timestamp=datetime.now(timezone.utc).isoformat()
        )
    
    async def _perform_search(self, search_query: SearchQuery) -> SearchResponse:
        """Perform search using Tavily API with enhanced parameters."""
        try:
            # Prepare comprehensive parameters
            tavily_params = self._prepare_tavily_params(search_query)
            
            self.logger.debug("tavily_search_request", query=search_query.query, params=tavily_params)
            
            # Execute search with timeout
            tavily_response = await asyncio.wait_for(
                self.client.search(**tavily_params),
                timeout=self.request_timeout
            )
            
            response = self._parse_tavily_response(search_query.query, tavily_response)
            
            self.logger.debug(
                "tavily_search_response", 
                query=search_query.query,
                results_count=len(response.results),
                has_answer=bool(response.answer)
            )
            
            return response
            
        except asyncio.TimeoutError:
            self.logger.error("tavily_search_timeout", query=search_query.query, timeout=self.request_timeout)
            raise WebSearchServiceException(f"Tavily search timeout after {self.request_timeout}s")
        except Exception as e:
            self.logger.error("tavily_search_error", query=search_query.query, error=str(e))
            raise WebSearchServiceException(f"Tavily search failed: {str(e)}") from e
    
    async def _extract_content(self, url: str) -> Dict[str, Any]:
        """Extract content from URL using Tavily."""
        try:
            self.logger.debug("tavily_extract_request", url=url)
            
            extracted_data = await asyncio.wait_for(
                self.client.extract(url),
                timeout=self.request_timeout
            )
            
            # Parse Tavily extraction response
            results = extracted_data.get("results", [])
            if results:
                result = results[0]  # Take first result
                content_data = {
                    "url": url,
                    "content": result.get("content", ""),
                    "title": result.get("title", ""),
                    "success": bool(result.get("content", "").strip()),
                    "extracted_at": datetime.now(timezone.utc).isoformat(),
                    "raw_content": result.get("raw_content") if result.get("raw_content") else None
                }
            else:
                content_data = {
                    "url": url,
                    "content": "",
                    "title": "",
                    "success": False,
                    "extracted_at": datetime.now(timezone.utc).isoformat(),
                    "error": "No content extracted"
                }
            
            self.logger.debug(
                "tavily_extract_response", 
                url=url,
                success=content_data["success"],
                content_length=len(content_data["content"])
            )
            
            return content_data
            
        except asyncio.TimeoutError:
            self.logger.error("tavily_extract_timeout", url=url, timeout=self.request_timeout)
            return {
                "url": url,
                "content": "",
                "title": "",
                "success": False,
                "extracted_at": datetime.now(timezone.utc).isoformat(),
                "error": f"Extraction timeout after {self.request_timeout}s"
            }
        except Exception as e:
            self.logger.error("tavily_extract_error", url=url, error=str(e))
            return {
                "url": url,
                "content": "",
                "title": "",
                "success": False,
                "extracted_at": datetime.now(timezone.utc).isoformat(),
                "error": str(e)
            }
    
    async def quick_search_links(
        self, 
        queries: Union[str, List[str]], 
        min_score: float = 0.5,
        max_results_per_query: int = 10,
        **kwargs
    ) -> Dict[str, Any]:
        """Quick search for links with simplified parameters."""
        # Convert to SearchQuery objects with optimized settings for link retrieval
        if isinstance(queries, str):
            queries = [queries]
        
        search_queries = []
        for query in queries:
            search_queries.append(SearchQuery(
                query=query,
                max_results=max_results_per_query,
                search_depth="basic",  # Faster for just links
                include_answer=False,  # Don't need answers for links
                include_raw_content=False,  # Don't need raw content for links
                auto_parameters=True,  # Let Tavily optimize
                **kwargs
            ))
        
        return await self.search_links(search_queries, min_score)
    
    async def comprehensive_search_extract(
        self, 
        queries: Union[str, List[Union[str, Dict[str, Any]]]], 
        min_score: float = 0.5,
        max_extractions: Optional[int] = 20,
        search_depth: str = "advanced",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Comprehensive search and extract similar to original Tavily example.
        Handles both string queries and dict queries with parameters.
        """
        try:
            start_time = time.time()
            
            # Convert queries to SearchQuery objects
            search_queries = []
            for query in queries if isinstance(queries, list) else [queries]:
                if isinstance(query, str):
                    search_queries.append(SearchQuery(
                        query=query,
                        search_depth=search_depth,
                        include_answer=True,
                        include_raw_content=False,
                        auto_parameters=True,
                        **kwargs
                    ))
                elif isinstance(query, dict):
                    # Handle dict format like original example
                    search_queries.append(SearchQuery(
                        query=query["query"],
                        max_results=query.get("max_results", 10),
                        search_depth=query.get("search_depth", search_depth),
                        include_domains=query.get("include_domains", []),
                        exclude_domains=query.get("exclude_domains", []),
                        include_answer=query.get("include_answer", True),
                        include_raw_content=query.get("include_raw_content", False),
                        auto_parameters=query.get("auto_parameters", True),
                        topic=query.get("topic", "general"),
                        chunks_per_source=query.get("chunks_per_source", 3),
                        days=query.get("days", 7),
                        **kwargs
                    ))
                else:
                    search_queries.append(query)  # Already SearchQuery object
            
            self.logger.info("comprehensive_search_started", query_count=len(search_queries))
            
            # Use the base class method for search and extract
            result = await self.search_extract_content(
                search_queries, 
                min_score=min_score, 
                max_extractions=max_extractions
            )
            
            # Add timing information
            total_time_ms = (time.time() - start_time) * 1000
            result["timing"] = {
                "total_time_ms": round(total_time_ms, 2),
                "completed_at": datetime.now(timezone.utc).isoformat()
            }
            
            # Add service statistics
            result["service_stats"] = self.get_stats()
            
            self.logger.info(
                "comprehensive_search_completed",
                **result["summary"],
                total_time_ms=total_time_ms
            )
            
            return result
            
        except Exception as e:
            self.logger.error("comprehensive_search_failed", error=str(e))
            raise WebSearchServiceException(f"Comprehensive search and extract failed: {e}") from e
    
    async def health_check(self) -> Dict[str, Any]:
        """Check if Tavily service is healthy."""
        try:
            # Perform a simple test search
            test_query = SearchQuery(
                query="test health check", 
                max_results=1, 
                search_depth="basic",
                include_answer=False,
                auto_parameters=True
            )
            
            start_time = time.time()
            response = await self._perform_search(test_query)
            response_time = (time.time() - start_time) * 1000
            
            return {
                "status": "healthy",
                "service": "tavily",
                "response_time_ms": round(response_time, 2),
                "test_results_count": len(response.results),
                "statistics": self.get_stats()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "service": "tavily",
                "error": str(e),
                "statistics": self.get_stats()
            }