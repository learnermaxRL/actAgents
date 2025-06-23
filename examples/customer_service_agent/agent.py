"""Customer Service Agent implementation with ticket management and FAQ handling."""

import sys 
sys.path.append(".")  # Adjust path to import base_agent and utils
import json
import traceback
from typing import Dict, List, Any, Optional, AsyncIterator, Union
from datetime import datetime
from pydantic import BaseModel, Field

from core.agents.common.base_agent import BaseAgent
from config.settings import settings
from utils.logger import get_logger
from .prompts.customer_service_prompt import CUSTOMER_SERVICE_PROMPT
from .tools_schemas.ticket_tool import create_ticket_tool_schema, update_ticket_tool_schema
from .tools_schemas.faq_tool import search_faq_tool_schema
from .tools.ticket_management import create_ticket, update_ticket
from .tools.faq_search import search_faq



class CustomerServiceAgent(BaseAgent):
    """Customer service agent specialized for ticket management and FAQ handling."""
    
    def __init__(
        self,
        verbose: bool = True,
        enable_state_management: bool = True,
        store_tool_history: bool = True,
        storage_type: str = "redis",
        **kwargs
    ):
        # Initialize with enhanced BaseAgent parameters
        super().__init__(
            agent_name="customer_service_agent",
            verbose=verbose,
            max_result_length=2000,  # Longer for detailed responses
            enable_json_validation=True,
            enable_state_management=enable_state_management,
            store_tool_history=store_tool_history,
            storage_type=storage_type,
            **kwargs
        )
        
        # Store verbose for access in demo
        self.verbose = verbose
        self.logger = get_logger("customer_service_agent")
        self.customer_service_prompt = CUSTOMER_SERVICE_PROMPT
        
        # Register tools
        self._register_tools()
    
    async def initialize_agent(self):
        """Initialize the agent and its state management."""
        await self.initialize()
        self.logger.info("Customer service agent initialized with state management")
    
    def _register_tools(self):
        """Register available tools for the customer service agent."""
        self.register_tool(create_ticket_tool_schema, create_ticket)
        self.register_tool(update_ticket_tool_schema, update_ticket)
        self.register_tool(search_faq_tool_schema, search_faq)
    

    async def process_message(
        self,
        message: str,
        chat_id: str,
        stream: bool = True,
        **kwargs
    ) -> AsyncIterator[str]:
        """
        Process customer service requests using the base agent's unified API.
        
        Args:
            message: User message about customer service needs
            chat_id: Unique chat identifier
            stream: Whether to stream from LLM (True) or buffer complete response (False)
            **kwargs: Additional parameters
        
        Returns:
            AsyncIterator[str] yielding content chunks
        """
        async for chunk in super().process_message(
            message=message,
            chat_id=chat_id,
            system_prompt=self.customer_service_prompt,
            stream=stream,
            save_to_history=True,
            use_stored_history=True,
            **kwargs
        ):
            yield chunk


if __name__ == "__main__":
    import asyncio
    import uuid

    # Use a try-except block to gracefully handle if 'rich' is not installed
    try:
        from rich.console import Console
        from rich.markdown import Markdown
        RICH_AVAILABLE = True
    except ImportError:
        print("WARNING: 'rich' library not found. For a better experience with colors and Markdown, please install it:")
        print("pip install rich")
        RICH_AVAILABLE = False
        
        # Define dummy classes so the script can run without 'rich'
        class Console:
            def print(self, *args, **kwargs):
                # Extract text from rich markup
                plain_text = ' '.join(str(arg) for arg in args)
                import re
                plain_text = re.sub(r'\[/?.*?\]', '', plain_text)
                print(plain_text)
                
            def input(self, prompt=""):
                # Clean up rich markup from prompt
                import re
                clean_prompt = re.sub(r'\[/?.*?\]', '', prompt)
                return input(clean_prompt)

        class Markdown:
            def __init__(self, text, **kwargs):
                self.text = text
            def __str__(self):
                return self.text

    async def main():
        """
        Runs an interactive command-line chat session with the CustomerServiceAgent.
        """
        console = Console()
        
        # Initialize agent with enhanced features
        agent = CustomerServiceAgent(
            verbose=True,
            enable_state_management=True,
            store_tool_history=True
        )
        
        # Initialize the agent (connects to state management)
        try:
            await agent.initialize_agent()
            console.print("[bold green]✅ Agent initialized with state management[/bold green]" if RICH_AVAILABLE else "✅ Agent initialized with state management")
        except Exception as e:
            console.print(f"[bold red]Failed to initialize agent: {e}[/bold red]" if RICH_AVAILABLE else f"Failed to initialize agent: {e}")
            console.print("Running without state management..." if RICH_AVAILABLE else "Running without state management...")
            # Create agent without state management as fallback
            agent = CustomerServiceAgent(
                verbose=True,
                enable_state_management=False
            )
        
        chat_id = f"interactive_session_{uuid.uuid4()}"
        
        if RICH_AVAILABLE:
            console.print(Markdown("# 🎧 Welcome to the Interactive Customer Service Agent!", style="bold magenta"))
        else:
            console.print("🎧 Welcome to the Interactive Customer Service Agent!")
            
        console.print("You can start chatting now. Type 'exit', 'quit', or 'help' for more options.")
        console.print("-" * 50)
        
        try:
            while True:
                user_input = console.input("\n[bold green]You: [/bold green]" if RICH_AVAILABLE else "\nYou: ")
                
                if user_input.lower() in ["exit", "quit"]:
                    if RICH_AVAILABLE:
                        console.print(Markdown("### 👋 Thank you for using the Customer Service Agent! Goodbye!", style="bold magenta"))
                    else:
                        console.print("👋 Thank you for using the Customer Service Agent! Goodbye!")
                    break
                    
                elif user_input.lower() == "help":
                    help_text = """
**Available Commands:**
- `exit` or `quit`: End the session
- `context`: Show current conversation context
- `history`: Show conversation history
- `reset`: Start a fresh conversation
- Or just ask me about customer service!

**Example queries:**
- "I need help with my order"
- "Create a support ticket for billing issue"
- "What's your return policy?"
- "How do I reset my password?"
- "Update my ticket status"
                    """
                    if RICH_AVAILABLE:
                        console.print(Markdown(help_text))
                    else:
                        console.print(help_text)
                    continue
                    
                elif user_input.lower() == "context":
                    try:
                        context = await agent.get_chat_context(chat_id)
                        if RICH_AVAILABLE:
                            console.print(Markdown("### Current Context", style="bold blue"))
                            console.print(Markdown(f"```json\n{json.dumps(context, indent=2)}\n```"))
                        else:
                            console.print("### Current Context")
                            console.print(json.dumps(context, indent=2))
                    except Exception as e:
                        console.print(f"Failed to get context: {e}")
                    continue
                    
                elif user_input.lower() == "history":
                    try:
                        context = await agent.get_chat_context(chat_id, include_history=True, k_turns=10)
                        history = context.get("chat_history", [])
                        if RICH_AVAILABLE:
                            console.print(Markdown("### Conversation History", style="bold blue"))
                        else:
                            console.print("### Conversation History")
                        
                        for i, msg in enumerate(history[-5:], 1):  # Show last 5 messages
                            role = msg.get("role", "unknown")
                            content = msg.get("content", "")[:100] + "..." if len(msg.get("content", "")) > 100 else msg.get("content", "")
                            if RICH_AVAILABLE:
                                console.print(f"**{i}. {role.title()}:** {content}")
                            else:
                                console.print(f"{i}. {role.title()}: {content}")
                    except Exception as e:
                        console.print(f"Failed to get history: {e}")
                    continue
                    
                elif user_input.lower() == "reset":
                    chat_id = f"interactive_session_{uuid.uuid4()}"
                    if RICH_AVAILABLE:
                        console.print(Markdown("### 🔄 Conversation reset! New session started.", style="bold green"))
                    else:
                        console.print("🔄 Conversation reset! New session started.")
                    continue
                
                # Process user message
                if RICH_AVAILABLE:
                    console.print("\n[bold blue]Agent: [/bold blue]", end="")
                else:
                    console.print("\nAgent: ", end="")
                
                try:
                    async for chunk in agent.process_message(
                        message=user_input,
                        chat_id=chat_id,
                        stream=True
                    ):
                        print(chunk, end="", flush=True)
                    print()  # New line after response
                    
                except Exception as e:
                    if RICH_AVAILABLE:
                        console.print(f"\n[bold red]Error: {e}[/bold red]")
                    else:
                        console.print(f"\nError: {e}")
                    
        except KeyboardInterrupt:
            if RICH_AVAILABLE:
                console.print(Markdown("\n### 👋 Session interrupted. Goodbye!", style="bold yellow"))
            else:
                console.print("\n👋 Session interrupted. Goodbye!")
        
        finally:
            # Cleanup
            try:
                await agent.close()
            except Exception as e:
                console.print(f"Warning: Error during cleanup: {e}")

    # Run the main function
    asyncio.run(main()) 