"""Enhanced base agent class with robust conversation and tool call management."""

import json
import traceback
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Callable, Union, AsyncIterator
from datetime import datetime
import os

from pydantic import BaseModel
import litellm
from litellm import acompletion, supports_response_schema, get_supported_openai_params
from litellm.utils import trim_messages

from config.settings import settings
from utils.exceptions import AgentException, ToolCallException
from core.services.state_management.chat_state_service import ChatStateManagerService
from utils.chat_logger import ChatLogger, LogLevel
import warnings
warnings.filterwarnings("ignore", category=UserWarning)

litellm._logging._disable_debugging()


class BaseAgent(ABC):
    """Enhanced base class for all agents with robust conversation and tool call management."""
    
    def __init__(
        self, 
        agent_name: str,
        model_name: str = None,
        enable_json_validation: bool = True,
        model_api_key: Optional[str] = None,
        model_api_base_url: Optional[str] = None,
        state_service: ChatStateManagerService = None,
        enable_state_management: bool = True,
        store_tool_history: bool = True,
        include_tool_calls_in_history: bool = True,
        storage_type: str = "redis",
        max_tool_call_timeout: float = 30.0,
        tool_call_retry_attempts: int = 3,
        **storage_kwargs
    ):
        self.model_name = model_name or os.environ.get("MODEL_DEPLOYMENT_NAME", "gpt-4o")
        self.agent_name = agent_name
        self.chat_logger = ChatLogger(max_result_length=500)
        self.tools: List[Dict] = []
        self.available_functions: Dict[str, Callable] = {}
        self.model_api_key = model_api_key or os.environ.get("MODEL_API_KEY")
        self.model_api_base_url = model_api_base_url or os.environ.get("MODEL_API_BASE_URL")
        self.max_tool_call_timeout = max_tool_call_timeout
        self.tool_call_retry_attempts = tool_call_retry_attempts
        
        # State management setup
        self.enable_state_management = enable_state_management
        if enable_state_management:
            if state_service:
                self.state_service = state_service
            else:
                self.state_service = ChatStateManagerService(
                    storage_type=storage_type,
                    store_tool_history=store_tool_history,
                    include_tool_calls_in_history=include_tool_calls_in_history,
                    **storage_kwargs
                )
        else:
            self.state_service = None

        # Configure litellm
        litellm.enable_json_schema_validation = enable_json_validation
        
        self.chat_logger.log(
            LogLevel.INFO,
            agent=self.agent_name,
            chat_id="system_setup",
            message=f"Agent initialized with state_management={enable_state_management}"
        )
    
    async def initialize(self):
        """Initialize the agent and connect to state service."""
        if self.state_service:
            await self.state_service.connect()
            self.chat_logger.log(
                LogLevel.INFO,
                agent=self.agent_name,
                chat_id="system_setup",
                message="State service connected"
            )
    
    def register_tool(self, tool_definition: Dict[str, Any], function: Callable):
        """Register a tool with its definition and implementation."""
        self.tools.append(tool_definition)
        function_name = tool_definition["function"]["name"]
        self.available_functions[function_name] = function
        
        self.chat_logger.log(
            LogLevel.INFO,
            agent=self.agent_name,
            chat_id="system_setup",
            message=f"Tool registered: {function_name}"
        )
    
    async def get_chat_context(
        self, 
        chat_id: str, 
        include_history: bool = True,
        k_turns: Optional[int] = 4,
        include_tool_calls: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Get chat context including state and optionally history."""
        if not self.state_service:
            return {}
        
        try:
            context = await self.state_service.get_full_context(
                chat_id, 
                k_turns=k_turns,
                include_tool_history=True,
                include_tool_calls=include_tool_calls
            )
            
            if not include_history:
                context.pop("chat_history", None)
                context.pop("tool_history", None)
            
            return context
            
        except Exception as e:
            self.chat_logger.log(
                LogLevel.WARNING,
                agent=self.agent_name,
                chat_id=chat_id,
                message=f"Failed to get chat context: {e}"
            )
            return {}
    
    async def update_chat_state(self, chat_id: str, state_update: Dict[str, Any]):
        """Update chat state if state management is enabled."""
        if not self.state_service:
            return
        
        try:
            await self.state_service.update_chat_state(chat_id, state_update)
        except Exception as e:
            self.chat_logger.log(
                LogLevel.WARNING,
                agent=self.agent_name,
                chat_id=chat_id,
                message=f"Failed to update chat state: {e}"
            )
    
    def _prepare_messages_with_system_prompt(
        self, 
        messages: List[Dict], 
        system_prompt: Optional[str] = None
    ) -> List[Dict]:
        """Prepare messages by adding system prompt at the beginning."""
        # Filter out any existing system messages from the input
        conversation_messages = [msg for msg in messages if msg.get("role") != "system"]
        
        # Prepare final messages list
        final_messages = []
        
        # Add system prompt at the beginning if provided
        if system_prompt:
            final_messages.append({"role": "system", "content": system_prompt})
        
        # Add conversation messages
        final_messages.extend(conversation_messages)
        
        return final_messages
    
    async def complete(
        self,
        message: str,
        chat_id: str,
        system_prompt: Optional[str] = None,
        max_iterations: Optional[int] = None,
        stream: bool = False,
        save_to_history: bool = True,
        k_turns: Optional[int] = None,
        include_tool_calls: Optional[bool] = None,
        **kwargs
    ) -> Union[Dict, AsyncIterator]:
        """Complete a conversation with enhanced tool call handling."""
        max_iterations = max_iterations or settings.max_tool_iterations
        iteration = 0
        
        self.chat_logger.log(
            LogLevel.INFO,
            agent=self.agent_name,
            chat_id=chat_id,
            message=f"Starting enhanced conversation (stream={stream}, k_turns={k_turns})"
        )
        
        # Start a new turn if state management is enabled
        turn_id = None
        if save_to_history and self.state_service:
            try:
                turn_id, user_message_id = await self.state_service.start_turn(chat_id, message)
                self.chat_logger.log(
                    LogLevel.INFO,
                    agent=self.agent_name,
                    chat_id=chat_id,
                    message=f"Started turn {turn_id}"
                )
            except Exception as e:
                self.chat_logger.log(
                    LogLevel.WARNING,
                    agent=self.agent_name,
                    chat_id=chat_id,
                    message=f"Failed to start turn: {e}"
                )
        
        try:
            # Get conversation history
            conversation_messages = []
            if self.state_service:
                history = await self.state_service.get_chat_history(
                    chat_id, 
                    k_turns=k_turns,
                    include_tool_calls=include_tool_calls
                )
                # Clean history for LLM (remove metadata)
                conversation_messages = [
                    {k: v for k, v in msg.items() 
                     if k in ["role", "content", "tool_calls", "tool_call_id", "name"]}
                    for msg in history
                ]
            
            # Add current user message
            conversation_messages.append({"role": "user", "content": message})
            
            # Prepare messages for LLM
            llm_messages = self._prepare_messages_with_system_prompt(conversation_messages, system_prompt)
            
            # Main conversation loop
            while iteration < max_iterations:
                try:
                    self.chat_logger.log(
                        LogLevel.LLM_REQUEST,
                        agent=self.agent_name,
                        chat_id=chat_id,
                        message={
                            "iteration": iteration + 1,
                            "messages": llm_messages[1:],  # Skip system prompt
                        }
                    )
                    
                    request_params = {
                        "model": self.model_name,
                        "messages": llm_messages,
                        "stream": stream,
                        "api_key": self.model_api_key,
                        "api_base": self.model_api_base_url,
                        # **kwargs
                    }
                    
                    if self.tools:
                        request_params["tools"] = self.tools
                    
                    response = await acompletion(**request_params)
                    
                    if stream:
                        return  self._handle_streaming_response(
                            response, chat_id, turn_id, iteration, max_iterations, 
                            save_to_history, system_prompt, k_turns, include_tool_calls
                        )
                    else:
                        # Handle non-streaming response
                        response_message = response.choices[0].message
                        
                        if hasattr(response_message, 'tool_calls') and response_message.tool_calls:
                            # Assistant wants to use tools
                            assistant_content = response_message.content or ""
                            
                            # Convert tool calls to dict format
                            tool_calls_dict = [
                                {
                                    "id": tc.id,
                                    "type": "function",
                                    "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                                } for tc in response_message.tool_calls
                            ]
                            
                            # Save assistant message with tool calls
                            if save_to_history and self.state_service and turn_id:
                                try:
                                    await self.state_service.add_assistant_message(
                                        chat_id, turn_id, assistant_content, tool_calls_dict
                                    )
                                except Exception as e:
                                    self.chat_logger.log(
                                        LogLevel.WARNING,
                                        agent=self.agent_name,
                                        chat_id=chat_id,
                                        message=f"Failed to save assistant message: {e}"
                                    )
                            
                            # Add to LLM messages for next iteration
                            llm_messages.append({
                                "role": "assistant",
                                "content": assistant_content,
                                "tool_calls": tool_calls_dict
                            })
                            
                            # Execute tool calls with timeout and retry
                            tool_results = await self._execute_tool_calls_with_retry(
                                response_message.tool_calls, chat_id, turn_id, save_to_history
                            )
                            
                            # Add tool results to LLM messages
                            for result in tool_results:
                                llm_messages.append(result)
                            
                            iteration += 1
                            
                        else:
                            # Final assistant response
                            final_content = response_message.content or ""
                            
                            # Save final assistant message
                            if save_to_history and self.state_service and turn_id:
                                try:
                                    await self.state_service.add_assistant_message(
                                        chat_id, turn_id, final_content
                                    )
                                except Exception as e:
                                    self.chat_logger.log(
                                        LogLevel.WARNING,
                                        agent=self.agent_name,
                                        chat_id=chat_id,
                                        message=f"Failed to save final response: {e}"
                                    )
                            
                            return {"role": "assistant", "content": final_content}
                
                except Exception as e:
                    self.chat_logger.log(
                        LogLevel.ERROR,
                        agent=self.agent_name,
                        chat_id=chat_id,
                        message=f"Error in conversation iteration {iteration + 1}: {e}",
                        stack_trace=traceback.format_exc()
                    )
                    
                    # Force complete turn on error
                    if turn_id and self.state_service:
                        await self.state_service.force_complete_turn(chat_id, turn_id)
                    
                    raise AgentException(f"Conversation failed: {e}") from e
            
            # Max iterations reached
            if turn_id and self.state_service:
                await self.state_service.force_complete_turn(chat_id, turn_id)
            
            return {
                "role": "assistant", 
                "content": "I've reached the maximum number of iterations. Please try rephrasing your request."
            }
        
        except Exception as e:
            # Ensure turn is completed on any error
            if turn_id and self.state_service:
                try:
                    await self.state_service.force_complete_turn(chat_id, turn_id)
                except:
                    pass  # Best effort cleanup
            raise
    
    async def _execute_tool_calls_with_retry(
        self, 
        tool_calls: List, 
        chat_id: str, 
        turn_id: Optional[str],
        save_to_history: bool
    ) -> List[Dict[str, Any]]:
        """Execute tool calls with timeout and retry logic."""
        async def execute_single_tool_call(tool_call):
            for attempt in range(self.tool_call_retry_attempts):
                try:
                    result = await asyncio.wait_for(
                        self._execute_tool_call(tool_call, chat_id, turn_id, save_to_history),
                        timeout=self.max_tool_call_timeout
                    )
                    return result
                except asyncio.TimeoutError:
                    if attempt < self.tool_call_retry_attempts - 1:
                        self.chat_logger.log(
                            LogLevel.WARNING,
                            agent=self.agent_name,
                            chat_id=chat_id,
                            message=f"Tool call timeout, retrying {attempt + 1}/{self.tool_call_retry_attempts}"
                        )
                        continue
                    else:
                        return {
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": tool_call.function.name,
                            "content": f"Tool call timed out after {self.max_tool_call_timeout}s"
                        }
                except Exception as e:
                    if attempt < self.tool_call_retry_attempts - 1:
                        self.chat_logger.log(
                            LogLevel.WARNING,
                            agent=self.agent_name,
                            chat_id=chat_id,
                            message=f"Tool call failed, retrying {attempt + 1}/{self.tool_call_retry_attempts}: {e}"
                        )
                        continue
                    else:
                        return {
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": tool_call.function.name,
                            "content": f"Tool call failed after {self.tool_call_retry_attempts} attempts: {str(e)}"
                        }
        
        # Execute all tool calls concurrently with individual timeouts
        tasks = [execute_single_tool_call(tc) for tc in tool_calls]
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _execute_tool_call(
        self, 
        tool_call, 
        chat_id: str, 
        turn_id: Optional[str],
        save_to_history: bool = True
    ) -> Dict[str, Any]:
        """Execute a single tool call with enhanced error handling."""
        function_name = tool_call.function.name
        
        try:
            function_args = json.loads(tool_call.function.arguments)
            
            if function_name not in self.available_functions:
                raise ToolCallException(f"Function {function_name} not available")
            
            start_time = datetime.now()
            result = await self.available_functions[function_name](**function_args)
            duration = (datetime.now() - start_time).total_seconds() * 1000
            
            # Save to tool history (separate from conversation)
            if save_to_history and self.state_service:
                try:
                    await self.state_service.add_tool_call(
                        chat_id=chat_id,
                        tool_name=function_name,
                        tool_call_id=tool_call.id,
                        arguments=function_args,
                        result=result,
                        duration_ms=round(duration, 2)
                    )
                except Exception as e:
                    self.chat_logger.log(
                        LogLevel.WARNING,
                        agent=self.agent_name,
                        chat_id=chat_id,
                        message=f"Failed to save tool call to history: {e}"
                    )
            
            # Save tool result to turn
            if save_to_history and self.state_service and turn_id:
                try:
                    await self.state_service.add_tool_result(
                        chat_id=chat_id,
                        turn_id=turn_id,
                        tool_call_id=tool_call.id,
                        tool_name=function_name,
                        result=result
                    )
                except Exception as e:
                    self.chat_logger.log(
                        LogLevel.WARNING,
                        agent=self.agent_name,
                        chat_id=chat_id,
                        message=f"Failed to save tool result to turn: {e}"
                    )
            
            return {
                "tool_call_id": tool_call.id,
                "role": "tool",
                "name": function_name,
                "content": json.dumps(result) if isinstance(result, (dict, list)) else str(result)
            }
            
        except Exception as e:
            error_content = f"Error executing tool '{function_name}': {str(e)}"
            
            # Save error to turn
            if save_to_history and self.state_service and turn_id:
                try:
                    await self.state_service.add_tool_result(
                        chat_id=chat_id,
                        turn_id=turn_id,
                        tool_call_id=tool_call.id,
                        tool_name=function_name,
                        result=None,
                        error=str(e)
                    )
                except Exception as history_error:
                    self.chat_logger.log(
                        LogLevel.WARNING,
                        agent=self.agent_name,
                        chat_id=chat_id,
                        message=f"Failed to save tool error to turn: {history_error}"
                    )
            
            return {
                "tool_call_id": tool_call.id,
                "role": "tool",
                "name": function_name,
                "content": error_content
            }
    
    async def _handle_streaming_response(
        self,
        response: AsyncIterator,
        chat_id: str,
        turn_id: Optional[str],
        iteration: int,
        max_iterations: int,
        save_to_history: bool = True,
        system_prompt: Optional[str] = None,
        k_turns: Optional[int] = None,
        include_tool_calls: Optional[bool] = None
    ) -> AsyncIterator:
        """Handle streaming response with enhanced tool call management."""
        tool_calls = []
        content_buffer = ""
        
        # Collect streaming response
        async for chunk in response:
            if hasattr(chunk.choices[0], 'delta') and chunk.choices[0].delta.tool_calls:
                # Handle tool call deltas
                for tc_delta in chunk.choices[0].delta.tool_calls:
                    while len(tool_calls) <= tc_delta.index:
                        tool_calls.append({
                            "id": None,
                            "type": "function", 
                            "function": {"name": "", "arguments": ""}
                        })
                    
                    if tc_delta.id:
                        tool_calls[tc_delta.index]["id"] = tc_delta.id
                    if tc_delta.function and tc_delta.function.name:
                        tool_calls[tc_delta.index]["function"]["name"] = tc_delta.function.name
                    if tc_delta.function and tc_delta.function.arguments:
                        tool_calls[tc_delta.index]["function"]["arguments"] += tc_delta.function.arguments
            
            if hasattr(chunk.choices[0], 'delta') and chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                content_buffer += content
                yield {"type": "content", "content": content}
        
        # Save assistant message
        if save_to_history and self.state_service and turn_id:
            try:
                await self.state_service.add_assistant_message(
                    chat_id, turn_id, content_buffer, tool_calls if tool_calls else None
                )
            except Exception as e:
                self.chat_logger.log(
                    LogLevel.WARNING,
                    agent=self.agent_name,
                    chat_id=chat_id,
                    message=f"Failed to save streamed assistant message: {e}"
                )
        
        # Handle tool calls if present and within iteration limit
        if tool_calls and iteration < max_iterations:
            # Execute tools
            for tool_call in tool_calls:
                try:
                    # Create mock tool call object for execution
                    class MockToolCall:
                        def __init__(self, tc_dict):
                            self.id = tc_dict["id"]
                            self.function = type('obj', (object,), {
                                'name': tc_dict["function"]["name"],
                                'arguments': tc_dict["function"]["arguments"]
                            })()
                    
                    mock_tc = MockToolCall(tool_call)
                    await self._execute_tool_call(mock_tc, chat_id, turn_id, save_to_history)
                    
                except Exception as e:
                    self.chat_logger.log(
                        LogLevel.ERROR,
                        agent=self.agent_name,
                        chat_id=chat_id,
                        message=f"Error executing tool in stream: {e}"
                    )
            
            # Wait a bit for tool results to be saved
            await asyncio.sleep(0.1)
            
            # Get final response by making a new complete call
            try:
                final_stream = await self.complete(
                    "",  # Empty message - will use history
                    chat_id,
                    system_prompt=system_prompt,
                    max_iterations=max_iterations - iteration - 1,
                    stream=True,
                    save_to_history=False,  # Don't start new turn
                    k_turns=k_turns,
                    include_tool_calls=include_tool_calls
                )
                
                async for chunk in final_stream:
                    yield chunk
                    
            except Exception as e:
                self.chat_logger.log(
                    LogLevel.ERROR,
                    agent=self.agent_name,
                    chat_id=chat_id,
                    message=f"Error in post-tool streaming: {e}"
                )
                yield {"type": "error", "content": "Error processing tool results"}
    
    async def process_message(
        self,
        message: str,
        chat_id: str,
        system_prompt: Optional[str] = None,
        stream: bool = True,
        save_to_history: bool = True,
        k_turns: Optional[int] = None,
        include_tool_calls: Optional[bool] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """Process a message with enhanced state management."""
        try:
            if stream:
                # Streaming response
                stream_response = await self.complete(
                    message=message,
                    chat_id=chat_id,
                    system_prompt=system_prompt,
                    stream=True,
                    save_to_history=save_to_history,
                    k_turns=k_turns,
                    include_tool_calls=include_tool_calls,
                    **kwargs
                )
                
                async for chunk in stream_response:
                    if chunk.get("type") == "content":
                        yield chunk.get("content", "")
                    elif chunk.get("type") == "error":
                        yield f"❌ {chunk.get('content', 'An error occurred')}"
            else:
                # Non-streaming response
                response = await self.complete(
                    message=message,
                    chat_id=chat_id,
                    system_prompt=system_prompt,
                    stream=False,
                    save_to_history=save_to_history,
                    k_turns=k_turns,
                    include_tool_calls=include_tool_calls,
                    # **kwargs
                )
                
                yield response.get("content", "")
                
        except Exception as e:
            self.chat_logger.log(
                LogLevel.ERROR,
                agent=self.agent_name,
                chat_id=chat_id,
                message=f"Error in process_message: {e}",
                stack_trace=traceback.format_exc()
            )
            yield "I'm sorry, I encountered an error. Please try again."
    
    async def close(self):
        """Clean up resources."""
        if self.state_service:
            await self.state_service.disconnect()
        self.chat_logger.close()