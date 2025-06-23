from typing import Dict, Any, List, Optional
from .base import BaseProductModel


class LaptopModel(BaseProductModel):
    """Laptop product model"""

    def __init__(self, config: Dict[str, Any]):
        """
        Initializes the LaptopModel.

        This constructor is designed to handle a flattened dictionary (from the tool)
        and transform it into the nested structure required for the search API.
        """
        super().__init__(config)

        # ---- Transform flat inputs into nested structures ----

        # Handle budget range
        if "budget_min" in config or "budget_max" in config:
            self.budget = {
                "min": config.get("budget_min"),
                "max": config.get("budget_max")
            }

        # Handle display size range
        display_spec = {}
        if "display_size_min" in config or "display_size_max" in config:
            display_spec["size_inches"] = {
                "min": config.get("display_size_min"),
                "max": config.get("display_size_max")
            }
        
        # Handle RAM range
        memory_spec = {}
        if "ram_min" in config or "ram_max" in config:
            memory_spec["ram_gb"] = {
                "min": config.get("ram_min"),
                "max": config.get("ram_max")
            }

        # Handle storage capacity range
        storage_spec = {"type": config.get("storage_types", [])}
        if "storage_capacity_min" in config or "storage_capacity_max" in config:
            storage_spec["capacity_gb"] = {
                "min": config.get("storage_capacity_min"),
                "max": config.get("storage_capacity_max")
            }

        # Assemble the final nested specifications dictionary
        self.specifications = {
            "display": display_spec,
            "processor": {
                "brand": config.get("processor_brands", []),
                "model": config.get("processor_models", [])
            },
            "graphics": {
                "brand": config.get("graphics_brands", []),
                "model": config.get("graphics_models", [])
            },
            "memory": memory_spec,
            "storage": storage_spec,
            "operating_system": config.get("operating_system", [])
        }
        
        # --- Extract nested dictionaries for property access ---
        self.display = self.specifications.get("display", {})
        self.processor = self.specifications.get("processor", {})
        self.graphics = self.specifications.get("graphics", {})
        self.memory = self.specifications.get("memory", {})
        self.storage = self.specifications.get("storage", {})
        self.operating_system = self.specifications.get("operating_system", [])

    @property
    def display_size_range(self) -> Optional[Dict[str, int]]:
        return self.display.get("size_inches")

    @property
    def processor_brands(self) -> List[str]:
        return self.processor.get("brand", [])

    @property
    def processor_models(self) -> List[str]:
        return self.processor.get("model", [])

    @property
    def graphics_brands(self) -> List[str]:
        return self.graphics.get("brand", [])

    @property
    def graphics_models(self) -> List[str]:
        return self.graphics.get("model", [])

    @property
    def ram_range(self) -> Optional[Dict[str, int]]:
        return self.memory.get("ram_gb")

    @property
    def storage_types(self) -> List[str]:
        return self.storage.get("type", [])

    @property
    def storage_capacity_range(self) -> Optional[Dict[str, int]]:
        return self.storage.get("capacity_gb")