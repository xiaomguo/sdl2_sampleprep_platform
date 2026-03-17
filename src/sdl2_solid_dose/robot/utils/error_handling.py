"""
Unified Error Handling and Retry Utilities for SDL2

Combines exception handling, retry decorators, and error recovery in one module.
"""
import asyncio
import socket
import threading
import time
import traceback
from functools import wraps
from typing import Optional, List, Callable, Type, Union
from .logger import logger
from .component_manager import component_manager

# ============================================================================
# Global Exception Handling
# ============================================================================

# Global registry for monitoring recovery handlers
_monitoring_recovery_handlers = []


def register_monitoring_recovery_handler(handler):
    """Register a monitoring recovery handler for automatic exception handling.
    Note: Primarily used for timeout recovery.
    """
    global _monitoring_recovery_handlers
    _monitoring_recovery_handlers.append(handler)
    logger.debug(f"Registered monitoring recovery handler: {type(handler).__name__}")


def application_thread_exception_handler(args):
    """Capture and log background thread exceptions from application components."""
    thread_name = args.thread.name if args.thread else "Unknown"
    exc_type = args.exc_type.__name__ if args.exc_type else "Unknown"
    exc_value = str(args.exc_value) if args.exc_value else "Unknown"
    
    logger.error("="*60)
    logger.error(f"APPLICATION THREAD EXCEPTION DETECTED")
    logger.error(f"Thread: {thread_name}")
    logger.error(f"Exception Type: {exc_type}")
    logger.error(f"Exception Value: {exc_value}")
    
    if args.exc_traceback:
        tb_lines = traceback.format_tb(args.exc_traceback)
        logger.error("Full Traceback:")
        for line in tb_lines:
            logger.error(line.rstrip())
    
    # Attempt automatic recovery for critical thread timeouts
    recovery_attempted = False
    global _monitoring_recovery_handlers
    
    # Only attempt recovery for timeout-related issues
    if exc_type in ["timeout", "socket.timeout", "TimeoutError"] or "timed out" in exc_value.lower():
        for recovery_handler in _monitoring_recovery_handlers:
            try:
                if recovery_handler.handle_monitoring_thread_exception(args):
                    recovery_attempted = True
                    logger.info("Recovery attempted for thread timeout")
                    break
            except Exception as recovery_error:
                logger.error(f"Error in recovery handler {type(recovery_handler).__name__}: {recovery_error}")
    
    # Device-specific error analysis
    _analyze_device_error(thread_name, exc_type, exc_value, args.exc_traceback, recovery_attempted)
    
    logger.warning("TROUBLESHOOTING: Check connections, controller status, hardware availability")
    logger.error("="*60)


def _analyze_device_error(thread_name: str, exc_type: str, exc_value: str, exc_traceback, recovery_attempted: bool):
    """Analyze and provide device-specific troubleshooting advice."""
    traceback_str = str(exc_traceback).lower() if exc_traceback else ""
    
    # RTDE-specific analysis
    if "rtde" in traceback_str or "RTDEControlInterface" in str(exc_traceback):
        logger.error("RTDE COMMUNICATION ERROR:")
        logger.error("- Check robot controller connection and status")
        logger.error("- Verify RTDE interface is enabled on robot")
        logger.error("- Ensure robot is in Remote Control mode")
        
    # Camera thread analysis  
    elif "VideoCap" in thread_name or "capture" in thread_name.lower() or "stream" in thread_name.lower():
        logger.error("CAMERA THREAD ERROR:")
        logger.error("- Check camera connection and drivers")
        logger.error("- Verify video capture device availability")
        logger.error("- Check camera permissions and resource access")
        
    # OPC-UA thread analysis
    elif "MettlerToledo" in thread_name or "asyncio" in traceback_str or "opcua" in traceback_str:
        logger.error("OPC-UA COMMUNICATION ERROR:")
        logger.error("- Check EasyMax device server connection")
        logger.error("- Verify OPC-UA server is running")
        logger.error("- Check network connectivity to reactor controller")
        
    # Socket/Network timeout analysis
    elif exc_type in ["timeout", "socket.timeout", "TimeoutError"] or "timed out" in exc_value.lower():
        logger.error("NETWORK/COMMUNICATION TIMEOUT:")
        logger.error("- Check network connectivity to devices")
        logger.error("- Verify device controllers are responsive")
        logger.error("- Consider increasing timeout values if persistent")
        if recovery_attempted:
            logger.info("- Automatic recovery was attempted")
            
    # Robotiq gripper analysis
    elif "Robotiq" in str(exc_traceback) or "gripper" in traceback_str:
        logger.error("ROBOTIQ GRIPPER ERROR:")
        logger.error("- Check gripper connection and power")
        logger.error("- Verify gripper TCP/IP communication")
        logger.error("- Check gripper activation status")


def configure_global_exception_handler():
    """Configure global thread exception handling for the application."""
    threading.excepthook = application_thread_exception_handler
    logger.info("Global application thread exception handler configured")


# ============================================================================
# Convenience Functions
# ============================================================================

def safe_execute(func: Callable, *args, default=None, log_errors=True, **kwargs):
    """
    Safely execute a function with automatic error handling.
    
    Args:
        func: Function to execute
        *args: Function arguments
        default: Default value to return on error
        log_errors: Whether to log errors
        **kwargs: Function keyword arguments
        
    Returns:
        Function result or default value on error
        
    Examples:
        weight = safe_execute(balance.weigh, default=0.0)
        ph_value = safe_execute(ph_strip.read, default=7.0, log_errors=False)
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        if log_errors:
            logger.error(f"Error in {func.__name__}: {type(e).__name__}: {e}")
        return default


def with_timeout(func: Callable, timeout_seconds: float, *args, **kwargs):
    """
    Execute a function with a timeout.
    
    Args:
        func: Function to execute
        timeout_seconds: Timeout in seconds
        *args: Function arguments
        **kwargs: Function keyword arguments
        
    Returns:
        Function result
        
    Raises:
        TimeoutError: If function takes longer than timeout_seconds
        
    Examples:
        robot_pos = with_timeout(robot.get_position, 5.0)
        hplc_data = with_timeout(hplc.run_analysis, 300.0)
    """
    import signal
    
    def timeout_handler(signum, frame):
        raise TimeoutError(f"Function {func.__name__} timed out after {timeout_seconds} seconds")
    
    # Set up the timeout
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(int(timeout_seconds))
    
    try:
        result = func(*args, **kwargs)
    finally:
        # Restore the old handler and cancel the alarm
        signal.signal(signal.SIGALRM, old_handler)
        signal.alarm(0)
    
    return result


# ============================================================================
# Retry and Recovery Functions
# ============================================================================

def socket_timeout_retry(operation_name=None, max_retries=5, retry_delay=3.0):
    """
    Decorator for automatic retry on socket timeout with exponential backoff.
    
    Handles both sync socket timeouts and async timeout errors:
    - socket.timeout (from socket operations)
    - asyncio.TimeoutError (from asyncio.wait_for)
    - TimeoutError (built-in timeout exception)
    
    Args:
        operation_name: Custom name for the operation (default: function name)
        max_retries: Maximum number of retry attempts (default: 5)
        retry_delay: Initial delay between retries in seconds (default: 3.0)
        
    Usage:
        @socket_timeout_retry(max_retries=3)
        def communicate_with_device(self):
            # Network communication code here
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            op_name = operation_name or f"{func.__name__}(...)" if args else f"{func.__name__}()"
            actual_max_retries = getattr(self, '_socket_retry_max_retries', max_retries)
            actual_retry_delay = getattr(self, '_socket_retry_delay', retry_delay)
            current_delay = actual_retry_delay
            
            # Try to find component-specific logger based on class name
            class_name = type(self).__name__
            component_logger = component_manager.component_loggers.get(class_name) or logger
            
            for attempt in range(actual_max_retries):
                try:
                    return func(self, *args, **kwargs)
                except (socket.timeout, asyncio.TimeoutError, TimeoutError) as e:
                    component_logger.error(f"Timeout during {op_name} (attempt {attempt + 1}/{actual_max_retries})")
                    component_logger.error(f"Timeout details: {type(e).__name__}: {e}")
                    component_logger.error(f"This likely indicates network communication issues with device controller")
                    
                    if attempt < actual_max_retries - 1:
                        component_logger.warning(f"Retrying {op_name} in {current_delay:.1f} seconds...")
                        time.sleep(current_delay)
                        # Exponential backoff for subsequent retries
                        current_delay *= 1.5
                    else:
                        component_logger.error(f"All {actual_max_retries} attempts failed for {op_name} due to timeout")
                        component_logger.error("This indicates a persistent network communication issue with the device")
                        raise
                except Exception as e:
                    # Non-timeout errors - don't retry, log and re-raise immediately
                    component_logger.error(f"{op_name} failed with non-timeout error: {type(e).__name__}: {e}")
                    raise
        return wrapper
    return decorator


def balance_error_retry(max_retries=3, retry_delay=1.0, acceptable_errors=None):
    """
    Decorator to handle balance operation errors with automatic retry and comprehensive logging.
    
    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        retry_delay: Initial delay between retries in seconds (default: 1.0)
        acceptable_errors: List of exception types that should be retried (default: common balance errors)
    
    Usage:
        @balance_error_retry()
        def weigh_sample(self):
            return self.balance.weigh(False)
            
        @balance_error_retry(max_retries=5, acceptable_errors=[ValueError, ConnectionError])
        def complex_balance_operation(self):
            # Your balance operation here
    """
    if acceptable_errors is None:
        # Common balance-related errors that should be retried
        acceptable_errors = [
            ValueError,      # Invalid weight readings
            ConnectionError, # Communication issues
            TimeoutError,    # Balance timeout
            OSError,         # Hardware communication errors
            RuntimeError,    # Balance not ready
        ]
    
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            operation_name = f"balance_{func.__name__}"
            current_delay = retry_delay
            
            # Use balance component logger if available, otherwise fall back to generic logger
            balance_logger = component_manager.component_loggers.get("MTXPRBalance") or logger
            
            for attempt in range(max_retries):
                try:
                    balance_logger.debug(f"Starting {operation_name} (attempt {attempt + 1}/{max_retries})")
                    result = func(self, *args, **kwargs)
                    
                    if attempt > 0:  # Log successful retry
                        balance_logger.info(f"SUCCESS: {operation_name} succeeded after {attempt + 1} attempts")
                    
                    return result
                    
                except tuple(acceptable_errors) as e:
                    balance_logger.error(f"ERROR: Balance error in {operation_name} (attempt {attempt + 1}/{max_retries})")
                    balance_logger.error(f"Error details: {type(e).__name__}: {e}")
                    
                    if attempt < max_retries - 1:
                        balance_logger.warning(f"RETRY: Retrying {operation_name} in {current_delay:.1f} seconds...")
                        balance_logger.warning("HINT: Possible causes: balance not stable, door open, vibration, scale drift")
                        time.sleep(current_delay)
                        current_delay *= 1.5  # Exponential backoff
                    else:
                        balance_logger.error(f"FAILED: All {max_retries} attempts failed for {operation_name}")
                        raise
                        
                except Exception as e:
                    # Non-retryable errors (programming errors, etc.)
                    balance_logger.error(f"FATAL: Non-retryable error in {operation_name}: {type(e).__name__}: {e}")
                    raise
                    
        return wrapper
    return decorator