"""Production-robust web search service with base class and Tavily implementation."""

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json

from utils.logger import get_logger
from utils.exceptions import WebSearchException


@dataclass
class SearchQuery:
    """Structured search query with parameters."""
    query: str
    max_results: int = 10
    search_depth: str = "basic"  # basic, advanced
    include_domains: List[str] = field(default_factory=list)
    exclude_domains: List[str] = field(default_factory=list)
    include_answer: bool = True
    include_raw_content: bool = False
    search_type: str = "search"  # search, news, academic
    # New Tavily-specific parameters
    auto_parameters: bool = False
    topic: str = "general"  # general, news
    chunks_per_source: int = 3
    time_range: Optional[str] = None
    days: int = 7
    include_images: bool = False
    include_image_descriptions: bool = False
    country: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API calls."""
        return {
            "query": self.query,
            "max_results": self.max_results,
            "search_depth": self.search_depth,
            "include_domains": self.include_domains,
            "exclude_domains": self.exclude_domains,
            "include_answer": self.include_answer,
            "include_raw_content": self.include_raw_content,
            "auto_parameters": self.auto_parameters,
            "topic": self.topic,
            "chunks_per_source": self.chunks_per_source,
            "time_range": self.time_range,
            "days": self.days,
            "include_images": self.include_images,
            "include_image_descriptions": self.include_image_descriptions,
            "country": self.country
        }


@dataclass
class SearchResult:
    """Standardized search result structure."""
    title: str
    url: str
    content: str
    score: float = 0.0
    published_date: Optional[str] = None
    source_domain: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "url": self.url,
            "content": self.content,
            "score": self.score,
            "published_date": self.published_date,
            "source_domain": self.source_domain
        }


@dataclass
class SearchResponse:
    """Complete search response with metadata."""
    query: str
    results: List[SearchResult]
    answer: Optional[str] = None
    total_results: int = 0
    search_time_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def filter_by_score(self, min_score: float = 0.5) -> 'SearchResponse':
        """Filter results by minimum score."""
        filtered_results = [r for r in self.results if r.score >= min_score]
        return SearchResponse(
            query=self.query,
            results=filtered_results,
            answer=self.answer,
            total_results=len(filtered_results),
            search_time_ms=self.search_time_ms,
            timestamp=self.timestamp
        )
    
    def get_urls(self) -> List[str]:
        """Get list of result URLs."""
        return [result.url for result in self.results]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "query": self.query,
            "results": [r.to_dict() for r in self.results],
            "answer": self.answer,
            "total_results": self.total_results,
            "search_time_ms": self.search_time_ms,
            "timestamp": self.timestamp
        }


class BaseWebSearchService(ABC):
    """Abstract base class for web search services."""
    
    def __init__(
        self,
        api_key: str,
        max_concurrent_requests: int = 5,
        request_timeout: float = 30.0,
        retry_attempts: int = 3,
        retry_delay: float = 1.0,
        rate_limit_calls: int = 100,
        rate_limit_period: int = 60,
        **kwargs
    ):
        self.api_key = api_key
        self.max_concurrent_requests = max_concurrent_requests
        self.request_timeout = request_timeout
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self.rate_limit_calls = rate_limit_calls
        self.rate_limit_period = rate_limit_period
        
        self.logger = get_logger(f"{self.__class__.__name__.lower()}")
        
        # Rate limiting
        self._request_semaphore = asyncio.Semaphore(max_concurrent_requests)
        self._rate_limit_requests = []
        
        # Statistics
        self._stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_search_time_ms": 0.0
        }
    
    async def _check_rate_limit(self):
        """Check and enforce rate limiting."""
        current_time = time.time()
        
        # Remove old requests outside the rate limit window
        self._rate_limit_requests = [
            req_time for req_time in self._rate_limit_requests 
            if current_time - req_time < self.rate_limit_period
        ]
        
        if len(self._rate_limit_requests) >= self.rate_limit_calls:
            sleep_time = self.rate_limit_period - (current_time - self._rate_limit_requests[0])
            if sleep_time > 0:
                self.logger.warning("rate_limit_hit", sleep_time=sleep_time)
                await asyncio.sleep(sleep_time)
        
        self._rate_limit_requests.append(current_time)
    
    async def _execute_with_retry(self, operation, *args, **kwargs):
        """Execute operation with retry logic."""
        last_exception = None
        
        for attempt in range(self.retry_attempts):
            try:
                return await operation(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < self.retry_attempts - 1:
                    delay = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    self.logger.warning(
                        "request_retry",
                        attempt=attempt + 1,
                        delay=delay,
                        error=str(e)
                    )
                    await asyncio.sleep(delay)
                else:
                    self.logger.error("request_failed_all_retries", error=str(e))
        
        raise WebSearchException(f"Request failed after {self.retry_attempts} attempts: {last_exception}")
    
    @abstractmethod
    async def _perform_search(self, search_query: SearchQuery) -> SearchResponse:
        """Perform the actual search operation. Must be implemented by subclasses."""
        pass
    
    @abstractmethod
    async def _extract_content(self, url: str) -> Dict[str, Any]:
        """Extract content from a URL. Must be implemented by subclasses."""
        pass
    
    async def search(
        self, 
        query: Union[str, SearchQuery], 
        **kwargs
    ) -> SearchResponse:
        """Perform a web search with rate limiting and retries."""
        # Convert string query to SearchQuery object
        if isinstance(query, str):
            search_query = SearchQuery(query=query, **kwargs)
        else:
            search_query = query
        
        async with self._request_semaphore:
            await self._check_rate_limit()
            
            start_time = time.time()
            self._stats["total_requests"] += 1
            
            try:
                response = await self._execute_with_retry(
                    self._perform_search, 
                    search_query
                )
                
                # Update timing
                search_time_ms = (time.time() - start_time) * 1000
                response.search_time_ms = search_time_ms
                
                self._stats["successful_requests"] += 1
                self._stats["total_search_time_ms"] += search_time_ms
                
                self.logger.info(
                    "search_completed",
                    query=search_query.query,
                    results_count=len(response.results),
                    search_time_ms=search_time_ms
                )
                
                return response
                
            except Exception as e:
                self._stats["failed_requests"] += 1
                self.logger.error("search_failed", query=search_query.query, error=str(e))
                raise WebSearchException(f"Search failed for query '{search_query.query}': {e}") from e
    
    async def batch_search(
        self, 
        queries: List[Union[str, SearchQuery]]
    ) -> List[SearchResponse]:
        """Perform multiple searches concurrently."""
        self.logger.info("batch_search_started", query_count=len(queries))
        
        try:
            responses = await asyncio.gather(
                *[self.search(q) for q in queries],
                return_exceptions=True
            )
            
            # Separate successful responses from exceptions
            successful_responses = []
            failed_count = 0
            
            for i, response in enumerate(responses):
                if isinstance(response, Exception):
                    failed_count += 1
                    query_str = queries[i] if isinstance(queries[i], str) else queries[i].query
                    self.logger.error("batch_search_item_failed", query=query_str, error=str(response))
                else:
                    successful_responses.append(response)
            
            self.logger.info(
                "batch_search_completed",
                total_queries=len(queries),
                successful=len(successful_responses),
                failed=failed_count
            )
            
            return successful_responses
            
        except Exception as e:
            self.logger.error("batch_search_failed", error=str(e))
            raise WebSearchException(f"Batch search failed: {e}") from e
    
    async def extract_content(self, url: str) -> Dict[str, Any]:
        """Extract content from a URL with rate limiting."""
        async with self._request_semaphore:
            await self._check_rate_limit()
            
            try:
                return await self._execute_with_retry(self._extract_content, url)
            except Exception as e:
                self.logger.error("content_extraction_failed", url=url, error=str(e))
                raise WebSearchException(f"Content extraction failed for {url}: {e}") from e
    
    async def batch_extract(self, urls: List[str]) -> List[Dict[str, Any]]:
        """Extract content from multiple URLs concurrently."""
        self.logger.info("batch_extract_started", url_count=len(urls))
        
        try:
            results = await asyncio.gather(
                *[self.extract_content(url) for url in urls],
                return_exceptions=True
            )
            
            # Filter out exceptions and log them
            successful_extractions = []
            failed_count = 0
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    failed_count += 1
                    self.logger.error("batch_extract_item_failed", url=urls[i], error=str(result))
                else:
                    successful_extractions.append(result)
            
            self.logger.info(
                "batch_extract_completed",
                total_urls=len(urls),
                successful=len(successful_extractions),
                failed=failed_count
            )
            
            return successful_extractions
            
        except Exception as e:
            self.logger.error("batch_extract_failed", error=str(e))
            raise WebSearchException(f"Batch extraction failed: {e}") from e
    
    async def search_links(
        self, 
        queries: Union[str, List[Union[str, SearchQuery]]], 
        min_score: float = 0.5,
        **kwargs
    ) -> Dict[str, Any]:
        """Search and return only links with scores."""
        # Normalize to list
        if isinstance(queries, str):
            queries = [queries]
        
        try:
            self.logger.info("search_links_started", query_count=len(queries))
            
            # Perform batch search
            responses = await self.batch_search(queries)
            
            # Collect links with metadata
            all_links = []
            query_results = {}
            
            for response in responses:
                # Filter by score
                filtered_results = [r for r in response.results if r.score >= min_score]
                
                links_data = []
                for result in filtered_results:
                    links_data.append({
                        "url": result.url,
                        "title": result.title,
                        "score": result.score,
                        "source_domain": result.source_domain,
                        "published_date": result.published_date
                    })
                
                query_results[response.query] = {
                    "links": links_data,
                    "count": len(links_data),
                    "answer": response.answer
                }
                
                all_links.extend([link["url"] for link in links_data])
            
            # Remove duplicates while preserving highest scores
            unique_links = list(dict.fromkeys(all_links))
            
            return {
                "queries": query_results,
                "unique_links": unique_links,
                "total_unique_links": len(unique_links),
                "min_score_filter": min_score,
                "successful_queries": len(responses),
                "failed_queries": len(queries) - len(responses)
            }
            
        except Exception as e:
            self.logger.error("search_links_failed", error=str(e))
            raise WebSearchException(f"Search links failed: {e}") from e
    
    async def search_extract_content(
        self, 
        queries: Union[str, List[Union[str, SearchQuery]]], 
        min_score: float = 0.5,
        max_extractions: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Search and extract content from results."""
        try:
            # First get the links
            links_result = await self.search_links(queries, min_score, **kwargs)
            
            # Get unique URLs for extraction
            urls_to_extract = links_result["unique_links"]
            
            # Limit extractions if specified
            if max_extractions and len(urls_to_extract) > max_extractions:
                # Sort URLs by highest score from any query
                url_scores = {}
                for query_data in links_result["queries"].values():
                    for link in query_data["links"]:
                        url = link["url"]
                        score = link["score"]
                        if url not in url_scores or score > url_scores[url]:
                            url_scores[url] = score
                
                sorted_urls = sorted(
                    urls_to_extract,
                    key=lambda url: url_scores.get(url, 0),
                    reverse=True
                )
                urls_to_extract = sorted_urls[:max_extractions]
            
            self.logger.info("search_extract_content_extraction", url_count=len(urls_to_extract))
            
            # Extract content from URLs
            extracted_contents = await self.batch_extract(urls_to_extract)
            
            # Separate successful and failed extractions
            successful_extractions = []
            failed_extractions = []
            
            for content in extracted_contents:
                if content.get("success", True) and content.get("content", "").strip():
                    successful_extractions.append(content)
                else:
                    failed_extractions.append(content)
            
            return {
                "search_results": links_result["queries"],
                "extracted_content": successful_extractions,
                "failed_extractions": failed_extractions,
                "summary": {
                    "total_queries": len(queries) if isinstance(queries, list) else 1,
                    "successful_queries": links_result["successful_queries"],
                    "failed_queries": links_result["failed_queries"],
                    "total_links_found": links_result["total_unique_links"],
                    "links_attempted_extraction": len(urls_to_extract),
                    "successful_extractions": len(successful_extractions),
                    "failed_extractions": len(failed_extractions),
                    "min_score_filter": min_score,
                    "max_extractions_limit": max_extractions
                }
            }
            
        except Exception as e:
            self.logger.error("search_extract_content_failed", error=str(e))
            raise WebSearchException(f"Search and extract content failed: {e}") from e

    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics."""
        avg_search_time = (
            self._stats["total_search_time_ms"] / max(self._stats["successful_requests"], 1)
        )
        
        return {
            **self._stats,
            "average_search_time_ms": round(avg_search_time, 2),
            "success_rate": round(
                self._stats["successful_requests"] / max(self._stats["total_requests"], 1) * 100, 2
            )
        }


