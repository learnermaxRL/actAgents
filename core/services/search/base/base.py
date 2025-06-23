from abc import ABC, abstractmethod
from typing import Dict, Any, List



class BaseSearchService(ABC):
    """Base search service for all products"""
    
    @abstractmethod
    async def search(self, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Search method to be implemented by subclasses"""
        pass