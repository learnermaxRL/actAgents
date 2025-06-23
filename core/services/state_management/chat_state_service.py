"""Enhanced state management service with robust tool call handling and corruption recovery."""

import json
from datetime import datetime
from typing import Dict, List, Optional, Any, Type, Tuple
import uuid
import asyncio
from collections import defaultdict

from config.settings import settings
from utils.exceptions import StateServiceException
from pydantic import BaseModel, Field
from utils.logger import get_logger
from utils.chat_logger import ChatLogger
from .storage_service import StorageInterface



class TurnMetadata(BaseModel):
    """Metadata for a conversation turn."""
    turn_id: str
    user_message_id: str
    assistant_message_id: str
    tool_call_ids: List[str] = Field(default_factory=list)
    completed_tool_results: List[str] = Field(default_factory=list)
    is_complete: bool = False
    created_at: str
    completed_at: Optional[str] = None


class ChatState(BaseModel):
    """Chat state model."""
    chat_id: str
    created_at: str
    updated_at: str
    user_preferences: Dict[str, Any] = Field(default_factory=dict)
    conversation_context: Dict[str, Any] = Field(default_factory=dict)
    
    @classmethod
    def create_default(cls, chat_id: str) -> 'ChatState':
        """Create default chat state."""
        now = datetime.now().isoformat()
        return cls(
            chat_id=chat_id,
            created_at=now,
            updated_at=now
        )


class ChatStateManagerService:
    """Enhanced service for managing chat states with robust tool call handling."""
    
    def __init__(
        self, 
        storage: Optional[StorageInterface] = None,
        storage_type: str = "redis",
        store_tool_history: bool = True,
        include_tool_calls_in_history: bool = True,
        max_recovery_attempts: int = 3,
        turn_completion_timeout: float = 30.0,
        **storage_kwargs
    ):
        self.store_tool_history = store_tool_history
        self.include_tool_calls_in_history = include_tool_calls_in_history
        self.max_recovery_attempts = max_recovery_attempts
        self.turn_completion_timeout = turn_completion_timeout
        self.logger = get_logger("enhanced_state_service")
        self.chat_logger = ChatLogger()
        
        # Track active turns and tool calls
        self._active_turns: Dict[str, Dict[str, TurnMetadata]] = defaultdict(dict)
        self._turn_locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        
        # Initialize storage backend
        if storage:
            self.storage = storage
        else:
            self.storage = self._create_storage(storage_type, **storage_kwargs)
    
    def _create_storage(self, storage_type: str, **kwargs) -> StorageInterface:
        """Create storage backend based on type."""
        from .storage_service import RedisStorage
        
        storage_map = {
            "redis": RedisStorage,
            
        }
        
        if storage_type not in storage_map:
            raise StateServiceException(f"Unsupported storage type: {storage_type}")
        
        storage_class = storage_map[storage_type]
        return storage_class(**kwargs)
    
    async def connect(self):
        """Connect to the storage backend."""
        try:
            await self.storage.connect()
            # self.logger.info("storage_connected", storage_type=type(self.storage).__name__)
        except Exception as e:
            self.logger.error("storage_connection_failed", error=str(e))
            raise StateServiceException(f"Failed to connect to storage: {e}") from e
    
    async def disconnect(self):
        """Disconnect from the storage backend."""
        try:
            await self.storage.disconnect()
            # self.logger.info("storage_disconnected")
        except Exception as e:
            self.logger.error("storage_disconnection_failed", error=str(e))
            
    
    def _generate_message_id(self) -> str:
        """Generate unique message ID."""
        return f"msg_{uuid.uuid4().hex[:12]}"
    
    def _generate_turn_id(self) -> str:
        """Generate unique turn ID."""
        return f"turn_{uuid.uuid4().hex[:12]}"
    
    async def _get_turn_lock(self, chat_id: str) -> asyncio.Lock:
        """Get or create turn lock for a chat."""
        return self._turn_locks[chat_id]
    
    async def start_turn(self, chat_id: str, user_message: str) -> Tuple[str, str]:
        """Start a new conversation turn and return turn_id and message_id."""
        async with await self._get_turn_lock(chat_id):
            turn_id = self._generate_turn_id()
            user_message_id = self._generate_message_id()
            
            # Create turn metadata
            turn_metadata = TurnMetadata(
                turn_id=turn_id,
                user_message_id=user_message_id,
                assistant_message_id="",  # Will be set when assistant responds
                created_at=datetime.now().isoformat()
            )
            
            self._active_turns[chat_id][turn_id] = turn_metadata
            
            # Save user message immediately
            user_msg = {
                "message_id": user_message_id,
                "turn_id": turn_id,
                "role": "user",
                "content": user_message,
                "timestamp": datetime.now().isoformat()
            }
            
            await self.storage.add_chat_message(chat_id, user_msg)
            
            # self.logger.info("turn_started", chat_id=chat_id, turn_id=turn_id, user_message_id=user_message_id)
            return turn_id, user_message_id
    
    async def add_assistant_message(
        self, 
        chat_id: str, 
        turn_id: str,
        content: str,
        tool_calls: Optional[List[Dict]] = None
    ) -> str:
        """Add assistant message to a turn."""
        async with await self._get_turn_lock(chat_id):
            if turn_id not in self._active_turns[chat_id]:
                raise StateServiceException(f"Turn {turn_id} not found or already completed")
            
            assistant_message_id = self._generate_message_id()
            turn_metadata = self._active_turns[chat_id][turn_id]
            turn_metadata.assistant_message_id = assistant_message_id
            
            # Prepare assistant message
            assistant_msg = {
                "message_id": assistant_message_id,
                "turn_id": turn_id,
                "role": "assistant",
                "content": content,
                "timestamp": datetime.now().isoformat()
            }
            
            if tool_calls:
                assistant_msg["tool_calls"] = tool_calls
                # Track expected tool call IDs
                turn_metadata.tool_call_ids = [tc["id"] for tc in tool_calls]
            else:
                # No tool calls means turn is complete
                turn_metadata.is_complete = True
                turn_metadata.completed_at = datetime.now().isoformat()
            
            await self.storage.add_chat_message(chat_id, assistant_msg)
            
            # self.logger.info(
            #     "assistant_message_added", 
            #     chat_id=chat_id, 
            #     turn_id=turn_id, 
            #     assistant_message_id=assistant_message_id,
            #     has_tool_calls=bool(tool_calls),
            #     expected_tool_calls=len(tool_calls) if tool_calls else 0
            # )
            
            return assistant_message_id
    
    async def add_tool_result(
        self,
        chat_id: str,
        turn_id: str,
        tool_call_id: str,
        tool_name: str,
        result: Any,
        error: Optional[str] = None
    ) -> bool:
        """Add tool result and return whether turn is now complete."""
        async with await self._get_turn_lock(chat_id):
            if turn_id not in self._active_turns[chat_id]:
                self.logger.warning("tool_result_for_unknown_turn", chat_id=chat_id, turn_id=turn_id)
                return False
            
            turn_metadata = self._active_turns[chat_id][turn_id]
            
            if tool_call_id not in turn_metadata.tool_call_ids:
                self.logger.warning(
                    "unexpected_tool_call_id", 
                    chat_id=chat_id, 
                    turn_id=turn_id, 
                    tool_call_id=tool_call_id,
                    expected_ids=turn_metadata.tool_call_ids
                )
                return False
            
            # Create tool result message
            tool_result_msg = {
                "message_id": self._generate_message_id(),
                "turn_id": turn_id,
                "role": "tool",
                "tool_call_id": tool_call_id,
                "name": tool_name,
                "content": json.dumps(result) if isinstance(result, (dict, list)) else str(result),
                "timestamp": datetime.now().isoformat()
            }
            
            if error:
                tool_result_msg["error"] = error
            
            await self.storage.add_chat_message(chat_id, tool_result_msg)
            
            # Track completed tool result
            if tool_call_id not in turn_metadata.completed_tool_results:
                turn_metadata.completed_tool_results.append(tool_call_id)
            
            # Check if turn is complete
            if set(turn_metadata.completed_tool_results) == set(turn_metadata.tool_call_ids):
                turn_metadata.is_complete = True
                turn_metadata.completed_at = datetime.now().isoformat()
                # self.logger.info("turn_completed", chat_id=chat_id, turn_id=turn_id)
                return True
            
            # self.logger.info(
            #     "tool_result_added", 
            #     chat_id=chat_id, 
            #     turn_id=turn_id,
            #     tool_call_id=tool_call_id,
            #     completed_count=len(turn_metadata.completed_tool_results),
            #     expected_count=len(turn_metadata.tool_call_ids)
            # )
            
            return False
    
    async def force_complete_turn(self, chat_id: str, turn_id: str) -> bool:
        """Force complete a turn (for interruptions or timeouts)."""
        async with await self._get_turn_lock(chat_id):
            if turn_id not in self._active_turns[chat_id]:
                return False
            
            turn_metadata = self._active_turns[chat_id][turn_id]
            turn_metadata.is_complete = True
            turn_metadata.completed_at = datetime.now().isoformat()
            
            # self.logger.info("turn_force_completed", chat_id=chat_id, turn_id=turn_id)
            return True
    
    async def cleanup_active_turns(self, chat_id: str, max_age_minutes: int = 60):
        """Clean up old active turns that may have been orphaned."""
        async with await self._get_turn_lock(chat_id):
            current_time = datetime.now()
            to_remove = []
            
            for turn_id, turn_metadata in self._active_turns[chat_id].items():
                created_time = datetime.fromisoformat(turn_metadata.created_at)
                age_minutes = (current_time - created_time).total_seconds() / 60
                
                if age_minutes > max_age_minutes:
                    to_remove.append(turn_id)
            
            for turn_id in to_remove:
                await self.force_complete_turn(chat_id, turn_id)
                del self._active_turns[chat_id][turn_id]
                # self.logger.info("orphaned_turn_cleaned", chat_id=chat_id, turn_id=turn_id)
    
    def _validate_and_repair_tool_calls(self, messages: List[Dict]) -> List[Dict]:
        """Validate and repair tool call sequences in message history."""
        repaired_messages = []
        pending_tool_calls = {}  # tool_call_id -> assistant_message
        
        for msg in messages:
            role = msg.get("role")
            
            if role == "assistant" and msg.get("tool_calls"):
                # Assistant message with tool calls
                for tool_call in msg["tool_calls"]:
                    pending_tool_calls[tool_call["id"]] = msg
                repaired_messages.append(msg)
                
            elif role == "tool":
                # Tool result message
                tool_call_id = msg.get("tool_call_id")
                if tool_call_id and tool_call_id in pending_tool_calls:
                    # Valid tool result
                    repaired_messages.append(msg)
                    del pending_tool_calls[tool_call_id]
                else:
                    # Orphaned tool result - skip it
                    self.logger.warning(
                        "orphaned_tool_result_skipped", 
                        tool_call_id=tool_call_id,
                        message_id=msg.get("message_id")
                    )
                    
            else:
                # Regular user/assistant message
                # If we have pending tool calls, we need to remove the assistant message that initiated them
                if pending_tool_calls and role == "user":
                    # Remove assistant messages with unresolved tool calls before this user message
                    messages_to_remove = set()
                    for i in range(len(repaired_messages) - 1, -1, -1):
                        if repaired_messages[i] in pending_tool_calls.values():
                            messages_to_remove.add(i)
                    
                    for i in sorted(messages_to_remove, reverse=True):
                        removed_msg = repaired_messages.pop(i)
                        # self.logger.warning(
                        #     "incomplete_tool_call_removed",
                        #     message_id=removed_msg.get("message_id"),
                        #     tool_calls=len(removed_msg.get("tool_calls", []))
                        # )
                    
                    pending_tool_calls.clear()
                
                repaired_messages.append(msg)
        
        # Final cleanup: remove any remaining incomplete tool calls at the end
        if pending_tool_calls:
            messages_to_remove = set()
            for i in range(len(repaired_messages) - 1, -1, -1):
                if repaired_messages[i] in pending_tool_calls.values():
                    messages_to_remove.add(i)
            
            for i in sorted(messages_to_remove, reverse=True):
                removed_msg = repaired_messages.pop(i)
                # self.logger.warning(
                #     "trailing_incomplete_tool_call_removed",
                #     message_id=removed_msg.get("message_id")
                # )
        
        return repaired_messages
    
    def _extract_turns_from_messages(self, messages: List[Dict], k_turns: Optional[int] = None) -> List[Dict]:
        """Extract the last k complete turns from messages."""
        if not messages:
            return []
        
        turns = []
        current_turn = []
        
        for msg in messages:
            role = msg.get("role")
            
            if role == "user":
                # Start of new turn - save previous turn if it exists
                if current_turn:
                    turns.append(current_turn)
                current_turn = [msg]
                
            elif role in ["assistant", "tool"]:
                # Part of current turn
                if current_turn:  # Only add if we have a user message to start the turn
                    current_turn.append(msg)
                else:
                    # Orphaned assistant/tool message without user message - skip
                    self.logger.warning("orphaned_message_skipped", role=role, message_id=msg.get("message_id"))
        
        # Add the last turn if it exists
        if current_turn:
            turns.append(current_turn)
        
        # Return last k turns if specified
        if k_turns is not None and k_turns > 0:
            turns = turns[-k_turns:]
        
        # Flatten turns back to message list
        result_messages = []
        for turn in turns:
            result_messages.extend(turn)
        
        return result_messages
    
    async def get_chat_history(
        self, 
        chat_id: str, 
        limit: Optional[int] = None,
        k_turns: Optional[int] = None,
        include_tool_calls: Optional[bool] = None
    ) -> List[Dict]:
        """Get chat history with robust tool call handling."""
        try:
            # Use instance setting if not explicitly provided
            if include_tool_calls is None:
                include_tool_calls = self.include_tool_calls_in_history
            
            # Clean up any orphaned active turns first
            await self.cleanup_active_turns(chat_id)
            
            # Get raw history from storage
            raw_limit = limit or settings.chat_history_limit
            raw_history = await self.storage.get_chat_history(chat_id, raw_limit * 2)  # Get more to account for filtering
            
            if not raw_history:
                return []
            
            # Sort by timestamp to ensure chronological order
            try:
                sorted_history = sorted(raw_history, key=lambda x: x.get("timestamp", ""))
            except:
                sorted_history = raw_history
            
            # Validate and repair tool call sequences
            if include_tool_calls:
                repaired_history = self._validate_and_repair_tool_calls(sorted_history)
            else:
                # Filter out tool-related messages
                repaired_history = [
                    msg for msg in sorted_history 
                    if msg.get("role") not in ["tool"] and not msg.get("tool_calls")
                ]
            
            # Extract turns if requested
            if k_turns is not None:
                final_history = self._extract_turns_from_messages(repaired_history, k_turns)
            else:
                final_history = repaired_history
            
            # Apply final limit
            if limit and len(final_history) > limit:
                final_history = final_history[-limit:]
            
            # self.logger.debug(
            #     "chat_history_retrieved", 
            #     chat_id=chat_id, 
            #     raw_count=len(raw_history),
            #     repaired_count=len(repaired_history),
            #     final_count=len(final_history),
            #     k_turns=k_turns,
            #     include_tool_calls=include_tool_calls
            # )
            
            return final_history
            
        except Exception as e:
            self.logger.error("get_chat_history_failed", chat_id=chat_id, error=str(e))
            raise StateServiceException(f"Failed to get chat history: {e}") from e
    
    async def get_chat_state(self, chat_id: str) -> Dict[str, Any]:
        """Get dynamic chat state (AI-managed JSON)."""
        try:
            state = await self.storage.get_chat_state(chat_id)
            
            if not state:
                default_state = ChatState.create_default(chat_id).dict()
                await self.storage.set_chat_state(chat_id, default_state)
                # self.logger.info("chat_state_created", chat_id=chat_id)
                return default_state
            
            # self.logger.debug("chat_state_retrieved", chat_id=chat_id, state_keys=list(state.keys()))
            return state
            
        except Exception as e:
            self.logger.error("get_chat_state_failed", chat_id=chat_id, error=str(e))
            raise StateServiceException(f"Failed to get chat state: {e}") from e
    
    async def update_chat_state(self, chat_id: str, state_update: Dict[str, Any]):
        """Update chat state with AI-generated updates."""
        try:
            current_state = await self.get_chat_state(chat_id)
            
            # Merge updates
            current_state.update(state_update)
            current_state["updated_at"] = datetime.now().isoformat()
            
            await self.storage.set_chat_state(chat_id, current_state)
            
            # self.chat_logger.log_state_update(chat_id, "CHAT_STATE", state_update)
            # self.logger.info("chat_state_updated", chat_id=chat_id, update_keys=list(state_update.keys()))
            
        except Exception as e:
            self.logger.error("update_chat_state_failed", chat_id=chat_id, error=str(e))
            raise StateServiceException(f"Failed to update chat state: {e}") from e
    
    async def get_full_context(
        self, 
        chat_id: str, 
        k_turns: Optional[int] = None,
        include_tool_history: bool = False,
        include_tool_calls: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Get complete context including state, chat history, and optionally tool history."""
        try:
            context = {
                "chat_state": await self.get_chat_state(chat_id),
                "chat_history": await self.get_chat_history(
                    chat_id, 
                    k_turns=k_turns,
                    include_tool_calls=include_tool_calls
                ),
            }
            
            if include_tool_history and self.store_tool_history:
                context["tool_history"] = await self.get_tool_history(chat_id)
            
            # self.logger.debug(
            #     "full_context_retrieved", 
            #     chat_id=chat_id, 
            #     k_turns=k_turns,
            #     include_tools=include_tool_history
            # )
            return context
            
        except Exception as e:
            # self.logger.error("get_full_context_failed", chat_id=chat_id, error=str(e))
            raise StateServiceException(f"Failed to get full context: {e}") from e
    
    async def get_tool_history(self, chat_id: str, limit: int = None) -> List[Dict]:
        """Get tool call history if enabled."""
        if not self.store_tool_history:
            return []
        
        try:
            limit = limit or getattr(settings, 'tool_history_limit', 100)
            history = await self.storage.get_tool_history(chat_id, limit)
            
            # self.logger.debug("tool_history_retrieved", chat_id=chat_id, tool_count=len(history))
            return history
            
        except Exception as e:
            # self.logger.error("get_tool_history_failed", chat_id=chat_id, error=str(e))
            raise StateServiceException(f"Failed to get tool history: {e}") from e
    
    async def add_tool_call(
        self,
        chat_id: str,
        tool_name: str,
        tool_call_id: str,
        arguments: Dict[str, Any],
        result: Any = None,
        error: str = None,
        duration_ms: float = None
    ):
        """Add tool call to history if enabled."""
        if not self.store_tool_history:
            return
        
        try:
            tool_call = {
                "tool_call_id": tool_call_id,
                "tool_name": tool_name,
                "arguments": arguments,
                "timestamp": datetime.now().isoformat(),
                "duration_ms": duration_ms
            }
            
            if result is not None:
                tool_call["result"] = result
            if error:
                tool_call["error"] = error
            
            await self.storage.add_tool_call(chat_id, tool_call)
            
            # Trim tool history if needed
            tool_limit = getattr(settings, 'tool_history_limit', 100)
            await self.storage.trim_history(chat_id, tool_limit)
            
            # self.logger.debug("tool_call_added", chat_id=chat_id, tool_name=tool_name, has_error=bool(error))
            
        except Exception as e:
            self.logger.error("add_tool_call_failed", chat_id=chat_id, error=str(e))
            self.logger.warning("tool_history_disabled_due_to_error", chat_id=chat_id)
    
    async def clear_chat_data(self, chat_id: str):
        """Clear all data for a specific chat."""
        try:
            # Clear active turns
            async with await self._get_turn_lock(chat_id):
                self._active_turns[chat_id].clear()
            
            # Clear storage
            await self.storage.set_chat_state(chat_id, ChatState.create_default(chat_id).dict())
            await self.storage.trim_history(chat_id, 0)  # Clear all history
            
            # self.logger.info("chat_data_cleared", chat_id=chat_id)
            
        except Exception as e:
            # self.logger.error("clear_chat_data_failed", chat_id=chat_id, error=str(e))
            raise StateServiceException(f"Failed to clear chat data: {e}") from e
    
    def configure_tool_call_handling(
        self, 
        include_in_history: bool = True,
        store_tool_history: bool = True
    ):
        """Configure tool call handling behavior."""
        self.include_tool_calls_in_history = include_in_history
        self.store_tool_history = store_tool_history
        
        # self.logger.info(
        #     "tool_call_handling_configured",
        #     include_in_history=include_in_history,
        #     store_tool_history=store_tool_history
        # )