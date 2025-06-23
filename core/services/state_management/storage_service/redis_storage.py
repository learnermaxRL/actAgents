"""Production-ready Redis storage with distributed locking and consistency guarantees."""

import json
import asyncio
import uuid
import time
from typing import Dict, List, Optional, Any, AsyncContextManager
from datetime import datetime, timezone
from contextlib import asynccontextmanager

import redis.asyncio as redis
from config.settings import settings
from utils.exceptions import StateServiceException
from utils.logger import get_logger
from .base_storage import StorageInterface


class DistributedLock:
    """Redis-based distributed lock implementation."""
    
    def __init__(self, redis_client: redis.Redis, key: str, timeout: float = 30.0, retry_delay: float = 0.1):
        self.redis_client = redis_client
        self.key = f"lock:{key}"
        self.timeout = timeout
        self.retry_delay = retry_delay
        self.identifier = f"{uuid.uuid4().hex}:{time.time()}"
        self.acquired = False
        self.logger = get_logger("distributed_lock")
    
    async def __aenter__(self):
        await self.acquire()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.release()
    
    async def acquire(self) -> bool:
        """Acquire the distributed lock with timeout."""
        end_time = time.time() + self.timeout
        
        while time.time() < end_time:
            # Try to acquire lock with expiration
            result = await self.redis_client.set(
                self.key, 
                self.identifier, 
                nx=True,  # Only set if key doesn't exist
                ex=int(self.timeout)  # Set expiration
            )
            
            if result:
                self.acquired = True
                # self.logger.debug("lock_acquired", key=self.key, identifier=self.identifier)
                return True
            
            # Brief delay before retry
            await asyncio.sleep(self.retry_delay)
        
        # self.logger.warning("lock_acquisition_timeout", key=self.key, timeout=self.timeout)
        raise StateServiceException(f"Failed to acquire lock {self.key} within {self.timeout}s")
    
    async def release(self) -> bool:
        """Release the distributed lock if we own it."""
        if not self.acquired:
            return False
        
        # Lua script to atomically check and delete only if we own the lock
        lua_script = """
        if redis.call("GET", KEYS[1]) == ARGV[1] then
            return redis.call("DEL", KEYS[1])
        else
            return 0
        end
        """
        
        try:
            result = await self.redis_client.eval(lua_script, 1, self.key, self.identifier)
            released = bool(result)
            if released:
                self.acquired = False
                # self.logger.debug("lock_released", key=self.key, identifier=self.identifier)
            else:
                self.logger.warning("lock_release_failed_not_owner", key=self.key, identifier=self.identifier)
            return released
        except Exception as e:
            # self.logger.error("lock_release_error", key=self.key, error=str(e))
            return False


class RedisStorage(StorageInterface):
    """Production-ready Redis storage with distributed locking and consistency guarantees."""
    
    def __init__(self, **kwargs):
        self.redis_url = kwargs.get("redis_url") or settings.redis_url
        self.redis_client = None
        self.logger = get_logger("redis_storage")
        
        # Configuration
        self.default_ttl = kwargs.get("default_ttl", 86400 * 30)  # 30 days
        self.lock_timeout = kwargs.get("lock_timeout", 30.0)
        self.max_retries = kwargs.get("max_retries", 3)
        self.retry_delay = kwargs.get("retry_delay", 0.1)
        
        # Connection pool settings
        self.connection_kwargs = {
            "max_connections": kwargs.get("max_connections", 20),
            "retry_on_timeout": True,
            "health_check_interval": kwargs.get("health_check_interval", 30),
            "socket_keepalive": True,
            "socket_keepalive_options": {},
        }
    
    async def connect(self):
        """Connect to Redis with connection pooling."""
        try:
            # Create connection pool
            pool = redis.ConnectionPool.from_url(
                self.redis_url, 
                **self.connection_kwargs
            )
            self.redis_client = redis.Redis(connection_pool=pool)
            
            # Test connection
            await self.redis_client.ping()
            self.logger.info("redis_connected", url=self.redis_url)
            
        except Exception as e:
            self.logger.error("redis_connection_failed", error=str(e))
            raise StateServiceException(f"Failed to connect to Redis: {e}") from e
    
    async def disconnect(self):
        """Disconnect from Redis."""
        if self.redis_client:
            await self.redis_client.close()
            self.logger.info("redis_disconnected")
    
    @asynccontextmanager
    async def _get_distributed_lock(self, lock_key: str) -> AsyncContextManager[DistributedLock]:
        """Get a distributed lock for the given key."""
        lock = DistributedLock(self.redis_client, lock_key, self.lock_timeout)
        async with lock:
            yield lock
    
    def _get_keys(self, chat_id: str) -> Dict[str, str]:
        """Get all Redis keys for a chat."""
        return {
            "state": f"chat_state:{chat_id}",
            "history": f"chat_history:{chat_id}",
            "tool_history": f"tool_history:{chat_id}",
            "turn_counter": f"turn_counter:{chat_id}",
            "message_counter": f"msg_counter:{chat_id}",
        }
    
    async def _execute_with_retry(self, operation, *args, **kwargs):
        """Execute Redis operation with retry logic."""
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                return await operation(*args, **kwargs)
            except (redis.ConnectionError, redis.TimeoutError) as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    self.logger.warning(
                        "redis_operation_retry", 
                        attempt=attempt + 1, 
                        error=str(e)
                    )
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))  # Exponential backoff
                else:
                    self.logger.error("redis_operation_failed_all_retries", error=str(e))
        
        raise StateServiceException(f"Redis operation failed after {self.max_retries} retries: {last_exception}")
    
    async def get_chat_state(self, chat_id: str) -> Optional[Dict[str, Any]]:
        """Get chat state by ID with atomic operation."""
        keys = self._get_keys(chat_id)
        
        try:
            state_data = await self._execute_with_retry(
                self.redis_client.get, keys["state"]
            )
            
            if not state_data:
                return None
            
            return json.loads(state_data.decode())
            
        except json.JSONDecodeError as e:
            self.logger.error("chat_state_json_decode_error", chat_id=chat_id, error=str(e))
            # Return None to trigger recreation of state
            return None
        except Exception as e:
            self.logger.error("get_chat_state_failed", chat_id=chat_id, error=str(e))
            raise StateServiceException(f"Failed to get chat state: {e}") from e
    
    async def set_chat_state(self, chat_id: str, state: Dict[str, Any]):
        """Set chat state with TTL and atomic operation."""
        keys = self._get_keys(chat_id)
        
        try:
            # Add metadata
            state_with_meta = {
                **state,
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "version": state.get("version", 0) + 1
            }
            
            await self._execute_with_retry(
                self.redis_client.setex,
                keys["state"],
                self.default_ttl,
                json.dumps(state_with_meta)
            )
            
        except Exception as e:
            self.logger.error("set_chat_state_failed", chat_id=chat_id, error=str(e))
            raise StateServiceException(f"Failed to set chat state: {e}") from e
    
    async def get_chat_history(self, chat_id: str, limit: int = None) -> List[Dict]:
        """Get chat history with consistent ordering."""
        keys = self._get_keys(chat_id)
        limit = limit or settings.chat_history_limit
        
        try:
            # Get messages with proper ordering (newest first in Redis list)
            messages = await self._execute_with_retry(
                self.redis_client.lrange, 
                keys["history"], 
                -limit, 
                -1
            )
            
            # Parse and sort by timestamp for consistency
            parsed_messages = []
            for msg_data in messages:
                try:
                    message = json.loads(msg_data.decode())
                    parsed_messages.append(message)
                except json.JSONDecodeError as e:
                    self.logger.warning("corrupted_message_skipped", chat_id=chat_id, error=str(e))
                    continue
            
            # Sort by timestamp to ensure chronological order
            parsed_messages.sort(key=lambda x: x.get("timestamp", ""))
            
            return parsed_messages
            
        except Exception as e:
            self.logger.error("get_chat_history_failed", chat_id=chat_id, error=str(e))
            raise StateServiceException(f"Failed to get chat history: {e}") from e
    
    async def add_chat_message(self, chat_id: str, message: Dict[str, Any]):
        """Add message to chat history with distributed locking and idempotency."""
        async with self._get_distributed_lock(f"chat_write:{chat_id}"):
            keys = self._get_keys(chat_id)
            
            try:
                # Generate unique message ID if not present
                if "message_id" not in message:
                    message_counter = await self._execute_with_retry(
                        self.redis_client.incr, keys["message_counter"]
                    )
                    message["message_id"] = f"{chat_id}:msg:{message_counter}"
                
                # Add timestamp if not present
                if "timestamp" not in message:
                    message["timestamp"] = datetime.now(timezone.utc).isoformat()
                
                # Check for duplicate message ID to ensure idempotency
                existing_messages = await self._execute_with_retry(
                    self.redis_client.lrange, keys["history"], 0, -1
                )
                
                for existing_msg_data in existing_messages:
                    try:
                        existing_msg = json.loads(existing_msg_data.decode())
                        if existing_msg.get("message_id") == message["message_id"]:
                            self.logger.debug("duplicate_message_skipped", 
                                            chat_id=chat_id, 
                                            message_id=message["message_id"])
                            return  # Message already exists
                    except json.JSONDecodeError:
                        continue
                
                # Use pipeline for atomic operations
                pipe = self.redis_client.pipeline()
                pipe.rpush(keys["history"], json.dumps(message))
                pipe.expire(keys["history"], self.default_ttl)
                
                await self._execute_with_retry(pipe.execute)
                
                self.logger.debug("message_added", 
                                chat_id=chat_id, 
                                message_id=message.get("message_id"),
                                role=message.get("role"))
                
            except Exception as e:
                self.logger.error("add_chat_message_failed", chat_id=chat_id, error=str(e))
                raise StateServiceException(f"Failed to add chat message: {e}") from e
    
    async def get_tool_history(self, chat_id: str, limit: int = None) -> List[Dict]:
        """Get tool call history."""
        keys = self._get_keys(chat_id)
        limit = limit or getattr(settings, 'tool_history_limit', 100)
        
        try:
            tool_calls = await self._execute_with_retry(
                self.redis_client.lrange, 
                keys["tool_history"], 
                -limit, 
                -1
            )
            
            parsed_calls = []
            for call_data in tool_calls:
                try:
                    tool_call = json.loads(call_data.decode())
                    parsed_calls.append(tool_call)
                except json.JSONDecodeError as e:
                    self.logger.warning("corrupted_tool_call_skipped", chat_id=chat_id, error=str(e))
                    continue
            
            # Sort by timestamp
            parsed_calls.sort(key=lambda x: x.get("timestamp", ""))
            return parsed_calls
            
        except Exception as e:
            self.logger.error("get_tool_history_failed", chat_id=chat_id, error=str(e))
            raise StateServiceException(f"Failed to get tool history: {e}") from e
    
    async def add_tool_call(self, chat_id: str, tool_call: Dict[str, Any]):
        """Add tool call to history with idempotency."""
        async with self._get_distributed_lock(f"tool_write:{chat_id}"):
            keys = self._get_keys(chat_id)
            
            try:
                # Add timestamp if not present
                if "timestamp" not in tool_call:
                    tool_call["timestamp"] = datetime.now(timezone.utc).isoformat()
                
                # Check for duplicate tool call ID
                tool_call_id = tool_call.get("tool_call_id")
                if tool_call_id:
                    existing_calls = await self._execute_with_retry(
                        self.redis_client.lrange, keys["tool_history"], 0, -1
                    )
                    
                    for existing_call_data in existing_calls:
                        try:
                            existing_call = json.loads(existing_call_data.decode())
                            if existing_call.get("tool_call_id") == tool_call_id:
                                self.logger.debug("duplicate_tool_call_skipped", 
                                                chat_id=chat_id, 
                                                tool_call_id=tool_call_id)
                                return
                        except json.JSONDecodeError:
                            continue
                
                # Use pipeline for atomic operations
                pipe = self.redis_client.pipeline()
                pipe.rpush(keys["tool_history"], json.dumps(tool_call))
                pipe.expire(keys["tool_history"], self.default_ttl)
                
                await self._execute_with_retry(pipe.execute)
                
                self.logger.debug("tool_call_added", 
                                chat_id=chat_id, 
                                tool_call_id=tool_call.get("tool_call_id"),
                                tool_name=tool_call.get("tool_name"))
                
            except Exception as e:
                self.logger.error("add_tool_call_failed", chat_id=chat_id, error=str(e))
                raise StateServiceException(f"Failed to add tool call: {e}") from e
    
    async def trim_history(self, chat_id: str, limit: int):
        """Trim both chat and tool history atomically."""
        async with self._get_distributed_lock(f"trim:{chat_id}"):
            keys = self._get_keys(chat_id)
            
            try:
                pipe = self.redis_client.pipeline()
                
                if limit == 0:
                    # Delete everything
                    pipe.delete(keys["history"])
                    pipe.delete(keys["tool_history"])
                else:
                    # Keep only the last 'limit' items
                    pipe.ltrim(keys["history"], -limit, -1)
                    pipe.ltrim(keys["tool_history"], -limit, -1)
                
                await self._execute_with_retry(pipe.execute)
                
                self.logger.info("history_trimmed", chat_id=chat_id, limit=limit)
                
            except Exception as e:
                self.logger.error("trim_history_failed", chat_id=chat_id, error=str(e))
                raise StateServiceException(f"Failed to trim history: {e}") from e
    
    async def atomic_turn_operation(
        self, 
        chat_id: str, 
        operations: List[Dict[str, Any]]
    ) -> bool:
        """Execute multiple operations atomically within a distributed lock."""
        async with self._get_distributed_lock(f"turn:{chat_id}"):
            try:
                pipe = self.redis_client.pipeline()
                keys = self._get_keys(chat_id)
                
                for op in operations:
                    op_type = op["type"]
                    
                    if op_type == "add_message":
                        message = op["message"]
                        if "timestamp" not in message:
                            message["timestamp"] = datetime.now(timezone.utc).isoformat()
                        pipe.rpush(keys["history"], json.dumps(message))
                        
                    elif op_type == "add_tool_call":
                        tool_call = op["tool_call"]
                        if "timestamp" not in tool_call:
                            tool_call["timestamp"] = datetime.now(timezone.utc).isoformat()
                        pipe.rpush(keys["tool_history"], json.dumps(tool_call))
                        
                    elif op_type == "update_state":
                        state = op["state"]
                        state["last_updated"] = datetime.now(timezone.utc).isoformat()
                        pipe.setex(keys["state"], self.default_ttl, json.dumps(state))
                
                # Set TTL on all keys
                for key in [keys["history"], keys["tool_history"]]:
                    pipe.expire(key, self.default_ttl)
                
                results = await self._execute_with_retry(pipe.execute)
                
                self.logger.info("atomic_turn_operation_completed", 
                               chat_id=chat_id, 
                               operation_count=len(operations))
                
                return all(results)
                
            except Exception as e:
                self.logger.error("atomic_turn_operation_failed", chat_id=chat_id, error=str(e))
                raise StateServiceException(f"Atomic turn operation failed: {e}") from e
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on Redis connection."""
        try:
            start_time = time.time()
            await self.redis_client.ping()
            latency = (time.time() - start_time) * 1000  # ms
            
            info = await self.redis_client.info()
            
            return {
                "status": "healthy",
                "latency_ms": round(latency, 2),
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "unknown"),
                "redis_version": info.get("redis_version", "unknown")
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def get_chat_metadata(self, chat_id: str) -> Dict[str, Any]:
        """Get metadata about a chat (message count, last activity, etc.)."""
        keys = self._get_keys(chat_id)
        
        try:
            pipe = self.redis_client.pipeline()
            pipe.llen(keys["history"])
            pipe.llen(keys["tool_history"])
            pipe.get(keys["state"])
            
            results = await self._execute_with_retry(pipe.execute)
            message_count, tool_count, state_data = results
            
            last_activity = None
            if state_data:
                try:
                    state = json.loads(state_data.decode())
                    last_activity = state.get("last_updated")
                except json.JSONDecodeError:
                    pass
            
            return {
                "chat_id": chat_id,
                "message_count": message_count or 0,
                "tool_call_count": tool_count or 0,
                "last_activity": last_activity,
                "has_state": bool(state_data)
            }
            
        except Exception as e:
            self.logger.error("get_chat_metadata_failed", chat_id=chat_id, error=str(e))
            return {
                "chat_id": chat_id,
                "error": str(e)
            }