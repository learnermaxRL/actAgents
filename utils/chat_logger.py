"""Enhanced Chat Logger with file-based organization and filtering options."""

import json
import threading
import traceback
import os
from datetime import datetime
from enum import Enum
from queue import Queue
from typing import Any, Dict, Optional, Set
from pathlib import Path
import copy


class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    TOOL_CALL = "TOOL_CALL"
    TOOL_RESULT = "TOOL_RESULT"
    LLM_REQUEST = "LLM_REQUEST"
    LLM_RESPONSE = "LLM_RESPONSE"
    STATE_UPDATE = "STATE_UPDATE"


class LogOutput(Enum):
    CONSOLE_ALL = "console_all"           # All logs to console (current behavior)
    CONSOLE_FILTERED = "console_filtered" # Only specific chat IDs to console
    FILES_SEPARATE = "files_separate"     # Each chat ID gets its own file
    FILES_DAILY = "files_daily"          # Daily log files with chat ID sections
    STRUCTURED_JSON = "structured_json"   # JSON format for log aggregation tools


class ChatLogger:
    """Enhanced chat logger with multiple output strategies for production use."""

    COLORS = {
        LogLevel.DEBUG: "\033[90m",      # Gray
        LogLevel.INFO: "\033[94m",       # Blue
        LogLevel.WARNING: "\033[93m",    # Yellow
        LogLevel.ERROR: "\033[91m",      # Red
        LogLevel.TOOL_CALL: "\033[95m",  # Magenta
        LogLevel.TOOL_RESULT: "\033[92m", # Green
        LogLevel.LLM_REQUEST: "\033[96m", # Cyan
        LogLevel.LLM_RESPONSE: "\033[36m", # Light Cyan
        LogLevel.STATE_UPDATE: "\033[33m"  # Orange
    }
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    
    MAX_TOOL_RESULTS_TO_SHOW = 3

    def __init__(
        self, 
        max_result_length: int = 1000, 
        toggle_logging: bool = True, 
        verbose: bool = False,
        output_mode: LogOutput = LogOutput.STRUCTURED_JSON,
        log_directory: str = "./logs",
        console_chat_filter: Optional[Set[str]] = None,
        max_log_files: int = 100  # Cleanup old files
    ):
        self.max_result_length = max_result_length
        self.verbose = verbose
        self.toggle_logging = toggle_logging
        self.output_mode = output_mode
        self.log_directory = Path(log_directory)
        self.console_chat_filter = console_chat_filter or set()
        self.max_log_files = max_log_files
        
        # Create log directory if it doesn't exist
        if self.output_mode in [LogOutput.FILES_SEPARATE, LogOutput.FILES_DAILY, LogOutput.STRUCTURED_JSON]:
            self.log_directory.mkdir(exist_ok=True, parents=True)
            
        # File handles for separate chat files
        self.chat_file_handles = {}
        self.file_lock = threading.Lock()
        
        # Only initialize queue and thread if logging is enabled
        if self.toggle_logging:
            self.log_queue = Queue()
            self.processing_thread = threading.Thread(target=self._process_logs, daemon=True)
            self.processing_thread.start()
        else:
            self.log_queue = None
            self.processing_thread = None
            print("ChatLogger: Logging is disabled. Set toggle_logging=True to enable.")

    def _get_daily_log_file(self) -> Path:
        """Get the daily log file path."""
        today = datetime.now().strftime("%Y-%m-%d")
        return self.log_directory / f"chat_logs_{today}.log"

    def _get_chat_log_file(self, chat_id: str) -> Path:
        """Get the log file path for a specific chat."""
        # Sanitize chat_id for filename
        safe_chat_id = "".join(c for c in chat_id if c.isalnum() or c in "._-")[:50]
        return self.log_directory / f"chat_{safe_chat_id}.log"

    def _get_json_log_file(self) -> Path:
        """Get the JSON log file path."""
        today = datetime.now().strftime("%Y-%m-%d")
        return self.log_directory / f"structured_logs_{today}.jsonl"

    def _cleanup_old_files(self):
        """Remove old log files if we exceed max_log_files."""
        if not self.log_directory.exists():
            return
            
        log_files = list(self.log_directory.glob("*.log")) + list(self.log_directory.glob("*.jsonl"))
        if len(log_files) > self.max_log_files:
            # Sort by modification time and remove oldest
            log_files.sort(key=lambda x: x.stat().st_mtime)
            for old_file in log_files[:-self.max_log_files]:
                try:
                    old_file.unlink()
                except OSError:
                    pass

    def _write_to_file(self, file_path: Path, content: str):
        """Thread-safe file writing."""
        with self.file_lock:
            try:
                with open(file_path, 'a', encoding='utf-8') as f:
                    f.write(content + '\n')
                    f.flush()
            except Exception as e:
                print(f"Error writing to log file {file_path}: {e}")

    def _process_logs(self):
        """Process logs from the queue based on output mode."""
        while True:
            try:
                log_entry = self.log_queue.get()
                if log_entry is None:  # Shutdown signal
                    break
                    
                self._handle_log_entry(log_entry)
                self.log_queue.task_done()
            except Exception as e:
                print(f"Error processing log queue: {e}")

    def _handle_log_entry(self, entry: Dict[str, Any]):
        """Handle a log entry based on the configured output mode."""
        chat_id = entry["chat_id"]
        
        if self.output_mode == LogOutput.CONSOLE_ALL:
            self._print_log(entry)
            
        elif self.output_mode == LogOutput.CONSOLE_FILTERED:
            if chat_id in self.console_chat_filter:
                self._print_log(entry)
                
        elif self.output_mode == LogOutput.FILES_SEPARATE:
            log_file = self._get_chat_log_file(chat_id)
            formatted_log = self._format_log_for_file(entry)
            self._write_to_file(log_file, formatted_log)
            
        elif self.output_mode == LogOutput.FILES_DAILY:
            log_file = self._get_daily_log_file()
            formatted_log = self._format_log_for_file(entry)
            self._write_to_file(log_file, formatted_log)
            
        elif self.output_mode == LogOutput.STRUCTURED_JSON:
            json_file = self._get_json_log_file()
            json_log = self._format_log_as_json(entry)
            self._write_to_file(json_file, json_log)

    def _format_log_for_file(self, entry: Dict[str, Any]) -> str:
        """Format log entry for file output (without colors)."""
        level = entry["level"]
        timestamp = entry["timestamp"].strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        
        lines = []
        lines.append(f"[{timestamp}] [{level.value:<12}] {entry['agent']} | {entry['chat_id']}")
        lines.append(f"  {entry['message']}")
        
        if "data" in entry:
            if level == LogLevel.TOOL_RESULT:
                data_str = self._format_tool_result_data(entry["data"])
            else:
                data_str = self._format_data(entry["data"])
            
            trimmed_data = self._trim_content(data_str)
            indented_data = "\n".join([f"    {line}" for line in trimmed_data.splitlines()])
            lines.append(indented_data)

        if "error" in entry:
            lines.append(f"  Error: {entry.get('error')}")
            if self.verbose and entry.get("stack_trace"):
                lines.append(f"  Stack trace:\n{entry['stack_trace']}")
        
        lines.append("")  # Empty line for separation
        return "\n".join(lines)

    def _format_log_as_json(self, entry: Dict[str, Any]) -> str:
        """Format log entry as JSON for structured logging."""
        json_entry = {
            "timestamp": entry["timestamp"].isoformat(),
            "level": entry["level"].value,
            "agent": entry["agent"],
            "chat_id": entry["chat_id"],
            "message": entry["message"]
        }
        
        # Add optional fields
        for key in ["data", "error", "stack_trace"]:
            if key in entry:
                json_entry[key] = entry[key]
                
        return json.dumps(json_entry, ensure_ascii=False, default=str)

    def _format_data(self, data: Any) -> str:
        """Intelligently format data for logging, with special handling for Pydantic models."""
        if hasattr(data, 'model_dump'):  # Pydantic v2
            try:
                data = data.model_dump(exclude_none=True)
            except Exception:
                pass
        elif hasattr(data, 'dict'):  # Pydantic v1
            try:
                data = data.dict(exclude_none=True)
            except Exception:
                pass

        if isinstance(data, (dict, list)):
            try:
                return json.dumps(data, indent=4, ensure_ascii=False, default=str)
            except (TypeError, ValueError):
                return str(data)
        return str(data)

    def _format_tool_result_data(self, data: Dict[str, Any]) -> str:
        """Special formatter for tool results that truncates long lists."""
        processed_data = copy.deepcopy(data)

        if isinstance(processed_data.get("result"), list):
            results_list = processed_data["result"]
            original_len = len(results_list)

            if original_len > self.MAX_TOOL_RESULTS_TO_SHOW:
                processed_data["result"] = results_list[:self.MAX_TOOL_RESULTS_TO_SHOW]
                processed_data["_summary"] = f"Showing {self.MAX_TOOL_RESULTS_TO_SHOW} of {original_len} results."
        
        return self._format_data(processed_data)

    def _trim_content(self, content: str) -> str:
        """Trim content if it exceeds max length for conciseness."""
        if not self.verbose and len(content) > self.max_result_length:
            return f"{content[:self.max_result_length]}...\n(trimmed for brevity)"
        return content

    def _print_log(self, entry: Dict[str, Any]):
        """The core log printing function for console output."""
        level = entry["level"]
        color = self.COLORS.get(level, self.RESET)
        timestamp = entry["timestamp"].strftime("%H:%M:%S.%f")[:-3]
        
        header = f"{color}{self.BOLD}[{timestamp}] [{level.value:<12}] {entry['agent']} | {entry['chat_id']}{self.RESET}"
        print(header)

        print(f"  {color}{entry['message']}{self.RESET}")
        
        if "data" in entry:
            if level == LogLevel.TOOL_RESULT:
                data_str = self._format_tool_result_data(entry["data"])
            else:
                data_str = self._format_data(entry["data"])
            
            trimmed_data = self._trim_content(data_str)
            indented_data = "\n".join([f"    {line}" for line in trimmed_data.splitlines()])
            print(f"{color}{self.DIM}{indented_data}{self.RESET}")

        if "error" in entry:
            error_details = f"{self.COLORS[LogLevel.ERROR]}Error: {entry.get('error')}{self.RESET}"
            if self.verbose and entry.get("stack_trace"):
                error_details += f"\n{self.COLORS[LogLevel.ERROR]}{self.DIM}Stack trace:\n{entry['stack_trace']}{self.RESET}"
            indented_error = "\n".join([f"  {line}" for line in error_details.splitlines()])
            print(indented_error)

        print()

    def log(self, level: LogLevel, *, agent: str, chat_id: str, message: str, **kwargs):
        """Log an entry to the queue if logging is enabled."""
        if not self.toggle_logging:
            return
            
        entry = {
            "timestamp": datetime.now(),
            "level": level,
            "agent": agent,
            "chat_id": chat_id,
            "message": message,
            **kwargs
        }
        
        if level == LogLevel.ERROR and "stack_trace" not in entry:
            entry["stack_trace"] = traceback.format_exc()
            
        if self.log_queue is not None:
            self.log_queue.put(entry)

    def add_console_filter(self, chat_id: str):
        """Add a chat ID to the console filter."""
        self.console_chat_filter.add(chat_id)

    def remove_console_filter(self, chat_id: str):
        """Remove a chat ID from the console filter."""
        self.console_chat_filter.discard(chat_id)

    def set_output_mode(self, mode: LogOutput):
        """Change the output mode at runtime."""
        self.output_mode = mode
        if mode in [LogOutput.FILES_SEPARATE, LogOutput.FILES_DAILY, LogOutput.STRUCTURED_JSON]:
            self.log_directory.mkdir(exist_ok=True, parents=True)

    def get_chat_log_file_path(self, chat_id: str) -> str:
        """Get the log file path for a specific chat (useful for external tools)."""
        return str(self._get_chat_log_file(chat_id))

    def log_state_update(self, chat_id: str, state_type: str, update_data: Dict[str, Any]):
        """Convenience method for logging state updates."""
        self.log(
            LogLevel.STATE_UPDATE,
            agent="state_service",
            chat_id=chat_id,
            message=f"State updated: {state_type}",
            data=update_data
        )

    def close(self):
        """Gracefully shut down the logging thread and close file handles."""
        if self.toggle_logging and self.log_queue is not None:
            self.log_queue.put(None)
            
            if self.processing_thread and self.processing_thread.is_alive():
                self.processing_thread.join(timeout=5.0)
        
        # Close any open file handles
        with self.file_lock:
            for handle in self.chat_file_handles.values():
                try:
                    handle.close()
                except:
                    pass
            self.chat_file_handles.clear()
            
        # Cleanup old files
        self._cleanup_old_files()
        print("ChatLogger: Closed gracefully.")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Usage examples for different production scenarios:

def create_production_logger():
    """Example: Production setup with separate files per chat."""
    return ChatLogger(
        output_mode=LogOutput.FILES_SEPARATE,
        log_directory="./production_logs",
        max_result_length=500,
        verbose=False
    )

# def create_development_logger(debug_chat_ids: Set[str]):
#     """Example: Development setup with filtered console output."""
#     return ChatLogger(
#         output_mode=LogOutput.CONSOLE_FILTERED,
#         console_chat_filter=debug_chat_ids,
#         verbose=True
#     )

# def create_monitoring_logger():
#     """Example: For log aggregation and monitoring tools."""
#     return ChatLogger(
#         output_mode=LogOutput.STRUCTURED_JSON,
#         log_directory="./monitoring_logs",
#         max_result_length=2000
#     )