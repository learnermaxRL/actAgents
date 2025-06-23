"""Updated storage interface with production-ready methods."""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any


class StorageInterface(ABC):
    """Enhanced abstract interface for storage backends with production features."""
    
    @abstractmethod
    async def connect(self):
        """Connect to the storage backend."""
        pass
    
    @abstractmethod
    async def disconnect(self):
        """Disconnect from the storage backend."""
        pass
    
    @abstractmethod
    async def get_chat_state(self, chat_id: str) -> Optional[Dict[str, Any]]:
        """Get chat state by ID."""
        pass
    
    @abstractmethod
    async def set_chat_state(self, chat_id: str, state: Dict[str, Any]):
        """Set chat state."""
        pass
    
    @abstractmethod
    async def get_chat_history(self, chat_id: str, limit: int = None) -> List[Dict]:
        """Get chat history with consistent ordering."""
        pass
    
    @abstractmethod
    async def add_chat_message(self, chat_id: str, message: Dict[str, Any]):
        """Add message to chat history with idempotency."""
        pass
    
    @abstractmethod
    async def get_tool_history(self, chat_id: str, limit: int = None) -> List[Dict]:
        """Get tool call history."""
        pass
    
    @abstractmethod
    async def add_tool_call(self, chat_id: str, tool_call: Dict[str, Any]):
        """Add tool call to history with idempotency."""
        pass
    
    @abstractmethod
    async def trim_history(self, chat_id: str, limit: int):
        """Trim history to specified limit."""
        pass
    
    @abstractmethod
    async def atomic_turn_operation(self, chat_id: str, operations: List[Dict[str, Any]]) -> bool:
        """Execute multiple operations atomically within a turn."""
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on storage backend."""
        pass
    
    @abstractmethod
    async def get_chat_metadata(self, chat_id: str) -> Dict[str, Any]:
        """Get metadata about a chat (message count, last activity, etc.)."""
        pass