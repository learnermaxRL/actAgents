from abc import ABC, abstractmethod
from typing import Dict, Any, List
from enum import Enum


class SupportedProductPrompts(Enum):
    LAPTOP = "laptop"
    TV = "tv"
    HEADPHONES = "headphones"
    REFRIGERATOR = "refrigerator"


class BaseProductModel(ABC):
    """Base class for all product models"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.category = config.get("category")
        self.sub_category = config.get("sub_category")
        self.primary_use = config.get("primary_use")
        self.budget = config.get("budget", {})
        self.brand = config.get("brand", [])
        self.condition = config.get("condition")