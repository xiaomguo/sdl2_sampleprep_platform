# logger.py
import logging
import socket
import getpass
import traceback
import functools
import sys
from datetime import datetime
from pathlib import Path
from io import StringIO
from typing import Union, Callable, Optional

# Create a logger object
logger = logging.getLogger(__name__)

# Set the log level - Note: DEBUG will show all messages
logger.setLevel(logging.DEBUG)

# Display logs on the console
console_handler = logging.StreamHandler()

# Create a formatter for the log messages
# Shows: timestamp - [LEVEL] - CALLING_MODULE - message
formatter = logging.Formatter(
    fmt="%(asctime)s - [%(levelname)s] - %(module)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
console_handler.setFormatter(formatter)

# Add the console handler to the logger
logger.addHandler(console_handler)

# Optionally, if you want to prevent the root logger from propagating the logs, set:
logger.propagate = False

# Suppress external library loggers from creating separate log files
# This prevents modules like ImageReqClient from creating their own log files
def suppress_external_loggers():
    """Prevent external libraries from creating separate log files"""
    external_loggers = [
        'ImageReqClientLogger',
        'image_req_client', 
        'requests',
        'urllib3',
        'PIL',
        'matplotlib',
        'opencv',
        'cv2'
    ]
    
    for logger_name in external_loggers:
        external_logger = logging.getLogger(logger_name)
        external_logger.handlers = []  # Remove any existing handlers
        external_logger.addHandler(logging.NullHandler())  # Add null handler to suppress
        external_logger.propagate = False  # Prevent propagation to root logger

# Apply external logger suppression
suppress_external_loggers()

# Default flag to determine whether file logging is enabled or not
is_file_logging_enabled = False  # Start with file logging disabled
current_log_file = None  # Track current log file to prevent duplicates


def file_log(enable: bool, filename=None, path=None, logger_name=None):
    """
    Enables or disables file logging dynamically.
    Prevents creating multiple log files by reusing existing file handlers.

    :param enable: If True, enables file logging, otherwise disables it.
    :param filename: The filename to log to. If None, uses a dynamic filename.
    :param path: The path to save the log file. If None, uses '~/Logs/'.
    :param logger_name: The logger name to include in filename. If None, uses 'lle-workflow'.
    """
    global is_file_logging_enabled, current_log_file
    
    # If file logging is already enabled, don't create another file handler
    if enable and is_file_logging_enabled and current_log_file:
        print(f"File logging already enabled, using existing log: {current_log_file}")
        return
    
    is_file_logging_enabled = enable

    # If enabling file logging, add a file handler
    if enable:
        add_file_handler(filename, path, logger_name)
    else:
        remove_file_handler()


def add_file_handler(filename=None, path=None, logger_name=None):
    """ Add a file handler dynamically with an optional filename.
    Prevents creating duplicate file handlers.

    :param filename: The filename to log to. If None, uses the formatted filename.
    :param path: The path to save the log file. If None, uses '~/Logs/'.
    :param logger_name: The logger name to include in filename. If None, uses 'lle-workflow'.

    """
    global current_log_file
    
    # Check if a file handler already exists
    for handler in logger.handlers:
        if isinstance(handler, logging.FileHandler):
            current_log_file = handler.baseFilename
            print(f"File logging already active: {current_log_file}")
            return
    
    if path is None:
        # Use ~/Logs/ as default path (cross-platform home directory)
        path = Path.home() / "Logs"
    else:
        # Convert string path to Path object for consistency
        path = Path(path).expanduser()  # Handle ~ in custom paths too
    if filename is None:
        # Generate filename in format: <hostname>_<username>_<logger_name>_<timestamp>.log
        hostname = socket.gethostname()
        username = getpass.getuser()
        logger_name = logger_name or 'lle-workflow'
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        filename = f"{hostname}_{username}_{logger_name}_{timestamp}.log"

    # Ensure the directory exists (Path.mkdir works cross-platform)
    path.mkdir(parents=True, exist_ok=True)

    # Create full file path
    full_path = path / filename

    file_handler = logging.FileHandler(str(full_path))
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    current_log_file = str(full_path)
    print(f"Logging to file: {full_path}")


def remove_file_handler():
    """ Remove the file handler from the logger if it exists. """
    global current_log_file
    for handler in logger.handlers:
        if isinstance(handler, logging.FileHandler):
            logger.removeHandler(handler)
            handler.close()  # Properly close the file handler
            print("File logging disabled.")
            current_log_file = None
            break


def log_exception(func):
    """
    Decorator that automatically logs exceptions with full traceback
    Use this for functions where you just want to troubleshoot the error
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # Log the exception with full traceback
            logger.error(f"EXCEPTION in {func.__name__}: {type(e).__name__}: {e}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            
            # Also print a clean error message to console
            print(f"\nERROR: {func.__name__} failed: {type(e).__name__}: {e}")
            print("Full error details have been logged.")
            
            # Re-raise the exception so normal error handling still works
            raise
    return wrapper


def log_and_catch_exception(func):
    """
    Decorator that logs exceptions and catches them (doesn't re-raise)
    Use this for functions where you want to continue execution despite errors
    USE THIS WITH CAUTION
    ONLY USE THIS FOR FUNCTIONS WHERE YOU WANT TO CONTINUE EXECUTION DESPITE ERRORS
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # Log the exception with full traceback
            logger.error(f"CAUGHT EXCEPTION in {func.__name__}: {type(e).__name__}: {e}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            
            # Print a clean error message to console
            print(f"\nWARNING: {func.__name__} failed but continuing: {type(e).__name__}: {e}")
            
            # Return None instead of raising
            return None
    return wrapper


# =============================================================================
# FUNCTION LOGGING DECORATORS
# =============================================================================

def log_function_calls(
    log_level: str = 'info',
    log_args: bool = False,
    log_return: bool = False,
    log_duration: bool = True,
    capture_prints: bool = False
):
    """
    Decorator for high-level unit operations that logs function entry, exit, and duration.
    Designed for tracking major workflow steps and operations.
    
    Args:
        log_level: Log level ('debug', 'info', 'warning', 'error')
        log_args: Whether to log function arguments
        log_return: Whether to log return values
        log_duration: Whether to log execution duration
        capture_prints: Whether to capture and log print statements (default: False)
        
    Usage:
        # For high-level unit operations (recommended)
        @log_function_calls()
        def run_extraction():
            # Unit operation logic
            return "extraction_complete"
            
        # For detailed debugging with print capture
        @log_function_calls(capture_prints=True)
        def debug_function():
            print("This will be logged with [debug_function] prefix")
            return "result"
    """
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            import time
            
            # Get the appropriate logger method
            log_method = getattr(logger, log_level.lower(), logger.info)
            func_name = func.__name__
            
            # Log function entry
            if log_args and (args or kwargs):
                args_str = ', '.join([repr(a) for a in args])
                kwargs_str = ', '.join([f"{k}={repr(v)}" for k, v in kwargs.items()])
                all_args = ', '.join(filter(None, [args_str, kwargs_str]))
                log_method(f"[{func_name}] ENTRY: {func_name}({all_args})")
            else:
                log_method(f"[{func_name}] ENTRY: Starting {func_name}")
            
            start_time = time.time() if log_duration else None
            original_stdout = sys.stdout
            # Create a real-time logging wrapper instead of buffering
            class RealTimeLogger:
                def __init__(self, original_stdout, log_method, func_name):
                    self.original_stdout = original_stdout
                    self.log_method = log_method
                    self.func_name = func_name
                    
                def write(self, text):
                    # Write to original stdout for console output
                    self.original_stdout.write(text)
                    # Also log each line immediately (skip empty lines)
                    if text.strip():
                        # Handle multi-line strings
                        for line in text.strip().split('\n'):
                            if line.strip():
                                self.log_method(f"[{self.func_name}] {line}")
                
                def flush(self):
                    self.original_stdout.flush()
            
            real_time_logger = RealTimeLogger(sys.stdout, log_method, func_name) if capture_prints else None
            
            try:
                # Replace stdout with real-time logger if requested
                if capture_prints:
                    sys.stdout = real_time_logger
                
                # Execute function
                result = func(*args, **kwargs)
                
                # Log function exit
                if log_duration and start_time:
                    duration = time.time() - start_time
                    if log_return and result is not None:
                        log_method(f"[{func_name}] EXIT: Completed in {duration:.3f}s, returned: {repr(result)}")
                    else:
                        log_method(f"[{func_name}] EXIT: Completed in {duration:.3f}s")
                else:
                    if log_return and result is not None:
                        log_method(f"[{func_name}] EXIT: returned: {repr(result)}")
                    else:
                        log_method(f"[{func_name}] EXIT: Completed")
                
                return result
                
            except Exception as e:
                # Log exception
                if log_duration and start_time:
                    duration = time.time() - start_time
                    log_method(f"[{func_name}] ERROR: Exception after {duration:.3f}s: {type(e).__name__}: {e}")
                else:
                    log_method(f"[{func_name}] ERROR: Exception: {type(e).__name__}: {e}")
                raise
                
            finally:
                # Always restore stdout
                if capture_prints:
                    sys.stdout = original_stdout
                    
        return wrapper
    return decorator


def log_with_function_name(log_level: str = 'info'):
    """
    Simple decorator that adds function name prefix to all logger calls within the function.
    
    Usage:
        @log_with_function_name()
        def my_function():
            logger.info("This message")  # Becomes "[my_function] This message"
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            func_name = func.__name__
            
            # Store original logger methods
            original_debug = logger.debug
            original_info = logger.info
            original_warning = logger.warning
            original_error = logger.error
            original_critical = logger.critical
            
            # Create wrapped logger methods that add function name prefix
            def wrapped_debug(msg, *args, **kwargs):
                return original_debug(f"[{func_name}] {msg}", *args, **kwargs)
            def wrapped_info(msg, *args, **kwargs):
                return original_info(f"[{func_name}] {msg}", *args, **kwargs)
            def wrapped_warning(msg, *args, **kwargs):
                return original_warning(f"[{func_name}] {msg}", *args, **kwargs)
            def wrapped_error(msg, *args, **kwargs):
                return original_error(f"[{func_name}] {msg}", *args, **kwargs)
            def wrapped_critical(msg, *args, **kwargs):
                return original_critical(f"[{func_name}] {msg}", *args, **kwargs)
            
            try:
                # Replace logger methods temporarily
                logger.debug = wrapped_debug
                logger.info = wrapped_info
                logger.warning = wrapped_warning
                logger.error = wrapped_error
                logger.critical = wrapped_critical
                
                # Execute function
                return func(*args, **kwargs)
                
            finally:
                # Always restore original logger methods
                logger.debug = original_debug
                logger.info = original_info
                logger.warning = original_warning
                logger.error = original_error
                logger.critical = original_critical
                
        return wrapper
    return decorator

def log_entry_exit(log_level: str = 'info'):
    """
    Simple decorator that logs function entry and exit only.
    Usage:
        @log_entry_exit()
        def my_function():
            pass  # Function body
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            func_name = func.__name__
            log_method = getattr(logger, log_level.lower(), logger.info)
            
            log_method(f"[{func_name}] ENTRY")
            try:
                result = func(*args, **kwargs)
                log_method(f"[{func_name}] EXIT")
                return result
            except Exception as e:
                log_method(f"[{func_name}] ERROR: {type(e).__name__}: {e}")
                raise
                
        return wrapper
    return decorator


if __name__ == "__main__":
    print("Testing logger functionality...")
    
    # Test basic console logging
    logger.info("Testing console logging - INFO level")
    logger.debug("Testing console logging - DEBUG level")
    logger.warning("Testing console logging - WARNING level")
    logger.error("Testing console logging - ERROR level")
    
    # Test file logging with default settings (~/Logs/)
    print("\n--- Testing file logging with default settings (~/Logs/) ---")
    file_log(enable=True)
    logger.info("This message goes to both console and file in ~/Logs/")
    logger.error("This error message also goes to both outputs")
    
    # Test exception decorators
    print("\n--- Testing exception logging decorators ---")
    
    @log_exception
    def test_function_with_error():
        """Test function that will raise an exception"""
        logger.info("About to raise a test exception...")
        raise ValueError("This is a test exception for logging")
    
    @log_and_catch_exception  
    def test_function_catch_error():
        """Test function that catches and logs exceptions"""
        logger.info("About to raise a test exception (will be caught)...")
        raise RuntimeError("This exception will be caught and logged")
    
    # Test the decorators
    print("Testing log_and_catch_exception decorator...")
    result = test_function_catch_error()  # This will catch the exception
    print(f"Function returned: {result}")
    print("Caught exception test completed")
    
    print("Testing log_exception decorator...")
    try:
        test_function_with_error()  # This will log and re-raise
    except ValueError as e:
        print(f"Caught expected exception: {e}")
    
    # Test disabling file logging
    print("\n--- Testing disable file logging ---")
    file_log(enable=False)
    logger.info("This message only goes to console after disabling file logging")
    
    print("\nLogger testing completed!")
