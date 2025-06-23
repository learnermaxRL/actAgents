from typing import Dict, Any, List
from .base.base import BaseSearchService
from .models.laptop_model import LaptopModel
import os

from abc import ABC, abstractmethod
from typing import Dict, Any, List


class LaptopSearchService(BaseSearchService):
    """Search service for laptops"""

    def __init__(self):
        """Initialize the service with environment configuration"""
        self.base_url = os.getenv("SEARCH_API_BASE_URL", "http://localhost:3000/api/v1")
        self.search_endpoint = os.getenv("SEARCH_ENDPOINT_SUFFIX", "/search/os/get-matches")

    async def search(self, *args, **kwargs) -> Dict[str, Any]:
        """
        Search for laptops based on the provided configuration.

        Args:
            **kwargs: Dictionary containing search criteria, including optional 'page' and 'size'.

        Returns:
            Dictionary containing the list of products and pagination details.
        """
        page = kwargs.pop('page', 1)
        size = kwargs.pop('size', 5)
        
        laptop_model = LaptopModel(config=kwargs)

        # Build search query based on laptop specifications
        search_results = await self._execute_search(laptop_model, page, size)

        return search_results

    async def _execute_search(self, laptop_model: LaptopModel, page: int, size: int) -> Dict[str, Any]:
        """
        Execute the actual search logic by calling the API asynchronously.

        Args:
            laptop_model: LaptopModel instance with search criteria.
            page: The page number for pagination.
            size: The number of results per page.

        Returns:
            Dictionary containing the list of matching laptops and pagination information.
        """
        import aiohttp
        import json

        # Build the original nested config structure for the API
        config_payload = {
            "config": {
                "category": laptop_model.category,
                "sub_category": laptop_model.sub_category,
                "primary_use": laptop_model.primary_use,
                "budget": laptop_model.budget,
                "specifications": {
                    "display": {
                        "size_inches": laptop_model.display_size_range
                    } if laptop_model.display_size_range else {},
                    "processor": {
                        "brand": laptop_model.processor_brands,
                        "model": laptop_model.processor_models
                    },
                    "graphics": {
                        "brand": laptop_model.graphics_brands,
                        "model": laptop_model.graphics_models
                    },
                    "memory": {
                        "ram_gb": laptop_model.ram_range
                    } if laptop_model.ram_range else {},
                    "storage": {
                        "type": laptop_model.storage_types,
                        "capacity_gb": laptop_model.storage_capacity_range
                    } if laptop_model.storage_capacity_range else {"type": laptop_model.storage_types},
                    "operating_system": laptop_model.operating_system
                },
                "brand": laptop_model.brand,
                "condition": laptop_model.condition
            }
        }

        # Remove empty/None values from nested structure
        config_payload = self._clean_empty_values(config_payload)

        try:
            # Build API URL from environment variables and add pagination params
            api_url = f"{self.base_url}{self.search_endpoint}?size={size}&page={page}"

            # Make async API call
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    api_url,
                    json=config_payload,
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    response.raise_for_status()
                    return await response.json()

        
        except Exception as e:
            print(f"Unexpected error: {e}")
            return {"products": [], "pagination": {}}

    def _clean_empty_values(self, obj):
        """
        Recursively remove empty/None values from nested dictionary.

        Args:
            obj: Dictionary to clean.

        Returns:
            Cleaned dictionary.
        """
        if isinstance(obj, dict):
            cleaned = {}
            for key, value in obj.items():
                if value is not None:
                    if isinstance(value, dict):
                        cleaned_value = self._clean_empty_values(value)
                        if cleaned_value:  # Only add if not empty
                            cleaned[key] = cleaned_value
                    elif isinstance(value, list):
                        if value:  # Only add if list is not empty
                            cleaned[key] = value
                    else:
                        cleaned[key] = value
            return cleaned
        return obj