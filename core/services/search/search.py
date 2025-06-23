from typing import Dict, Any, List
from .laptop_search import LaptopSearchService
from .models.base import SupportedProductPrompts

class ProductSearchAPI:
    """Main API class for product search"""
    
    def __init__(self):
        self.services = {
            SupportedProductPrompts.LAPTOP.value: LaptopSearchService()
        }
    
    async def search(self, *args,**kwargs) -> List[Dict[str, Any]]:
        """
        Main search method that routes to appropriate service
        
        Args:
            config: Search configuration dictionary
            
        Returns:
            List of products matching the search criteria
        """
        sub_category = kwargs.get("sub_category")
        
        if not sub_category:
            raise ValueError("sub_category is required")
        
        if sub_category not in self.services:
            raise ValueError(f"Unsupported sub_category: {sub_category}")
        
        service = self.services[sub_category]
        return await service.search(*args, **kwargs)