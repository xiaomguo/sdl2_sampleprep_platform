"""
Component Manager for SDL2 Workflows

Component registration and monitoring system that tracks component usage
and maintains individual files for each component:
- JSON files for usage stats only: logs/sdl2_components/component_name_usage.json
- Log files for component activity: logs/sdl2_components/component_name_history.log
- Settings are loaded from YAML: implementations/SDL2/deck_sdl2_settings.yaml
"""

import json
import atexit
import signal
import sys
import os
from pathlib import Path
from typing import Any, Dict, Type, Optional
from datetime import datetime
from .logger import logger


def track_component_calls(component_name: str):
    """
    Decorator to automatically track function calls on a component.
    You can choose which functions to track by adding the decorator to the function.
    
    Usage:
        @track_component_calls("pHStrip")
        def move(self):
            # function implementation
    """
    def decorator(func):
        def wrapper(self, *args, **kwargs):
            # Track the function call
            component_manager.track_function_call(component_name, func.__name__, args, kwargs)
            
            # Call the original function
            try:
                result = func(self, *args, **kwargs)
                component_manager.log_component_usage(component_name, "function_success", f"{func.__name__} completed successfully")
                return result
            except Exception as e:
                component_manager.log_component_error(component_name, f"{func.__name__} failed: {str(e)}")
                raise
        return wrapper
    return decorator


class ComponentManager:
    """
    Simple component manager for SDL2 workflows.
    
    Features:
    - Register multiple components at once
    - Track usage with timestamps
    - Individual JSON files per component
    - Debug-level logging for component activities
    - Simple reset functionality
    """
    
    def __init__(self, data_dir: Path = None):
        env_data_dir = os.environ.get("SDL2_COMPONENT_LOG_DIR")
        default_data_dir = Path(__file__).resolve().parents[4] / "logs" / "sdl2_components"
        self.data_dir = Path(data_dir) if data_dir else Path(env_data_dir) if env_data_dir else default_data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.registered_components: Dict[str, Any] = {}
        self.component_loggers: Dict[str, Any] = {}
        self._component_registry: Dict[str, Type] = {}
        self._is_shutting_down = False
        
        # Create ComponentManager's own debug logger
        self.manager_logger = self._create_manager_logger()
        
        # Register cleanup on exit
        atexit.register(self.cleanup_all)
        
        # Register signal handlers for Ctrl+C
        self._setup_signal_handlers()
        
        logger.info("ComponentManager initialized")
        self.manager_logger.debug("ComponentManager initialized with data directory: %s", self.data_dir)
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown on Ctrl+C."""
        def signal_handler(signum, frame):
            logger.info(f"Received Ctrl+C (signal {signum}), cleaning up components...")
            self.cleanup_all()
            logger.info("Cleanup completed. Exiting.")
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
    
    def _create_manager_logger(self):
        """Create ComponentManager's own debug logger with log rotation."""
        import logging
        from logging.handlers import RotatingFileHandler
        from .logger import formatter
        
        # Create logger for ComponentManager using component naming convention
        manager_logger = logging.getLogger("component.ComponentManager")
        manager_logger.setLevel(logging.DEBUG)
        
        # Avoid duplicate handlers
        if manager_logger.handlers:
            return manager_logger
        
        # Create rotating file handler for ComponentManager logs
        # Max 5MB per file, keep 3 backup files (15MB total for ComponentManager)
        log_file = self.data_dir / "componentmanager_history.log"
        file_handler = RotatingFileHandler(
            log_file, 
            maxBytes=5*1024*1024,   # 5MB
            backupCount=3,          # Keep 3 backup files
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        
        # Use the same formatter from the existing logger infrastructure
        file_handler.setFormatter(formatter)
        
        # Add handler to logger (file only, no console spam for internal debug)
        manager_logger.addHandler(file_handler)
        
        # Prevent propagation to root logger to avoid console output without timestamps
        manager_logger.propagate = False
        
        return manager_logger
    
    def _create_component_logger(self, component_name: str):
        """Create a logger for a specific component with log rotation."""
        import logging
        from logging.handlers import RotatingFileHandler
        from .logger import formatter
        
        # Create logger
        comp_logger = logging.getLogger(f"component.{component_name}")
        comp_logger.setLevel(logging.DEBUG)
        
        # Avoid duplicate handlers
        if comp_logger.handlers:
            return comp_logger
        
        # Create rotating file handler for this component
        # Max 20MB per file, keep 5 backup files (100MB total per component)
        log_file = self.data_dir / f"{component_name.lower()}_history.log"
        file_handler = RotatingFileHandler(
            log_file, 
            maxBytes=20*1024*1024,  # 20MB
            backupCount=5,          # Keep 5 backup files
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        
        # Create console handler for this component  
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        
        # Use the same formatter from existing logger infrastructure
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # Add both handlers to logger
        comp_logger.addHandler(file_handler)
        comp_logger.addHandler(console_handler)
        
        # Prevent propagation to avoid double logging or interference with root logger
        comp_logger.propagate = False
        
        self.manager_logger.debug("Created rotating file logger for %s (max 20MB, 5 backups)", component_name)
        
        return comp_logger
    
    def reg_all_comps(self, *components):
        """
        Register multiple components for monitoring.
        
        Args:
            *components: Variable number of component instances to register
        """
        self.manager_logger.debug("Starting registration of %d components", len([c for c in components if c is not None]))
        
        for component in components:
            if component is None:
                continue
                
            component_name = type(component).__name__
            
            if component_name in self.registered_components:
                logger.warning(f"Component {component_name} already registered, skipping")
                self.manager_logger.debug("Skipping already registered component: %s", component_name)
                continue
            
            # Register component
            self.registered_components[component_name] = component
            self.manager_logger.debug("Registered component instance: %s", component_name)
            
            # Create individual logger for this component with file handler
            self.component_loggers[component_name] = self._create_component_logger(component_name)
            self.manager_logger.debug("Created dedicated logger for component: %s", component_name)
            
            # Assign the component logger to the instance for disconnect methods
            if hasattr(component, '_comp_logger') or hasattr(component, '__dict__'):
                component._comp_logger = self.component_loggers[component_name]
                self.manager_logger.debug("Assigned component logger to %s instance", component_name)
            
            # Initialize component data file
            self._initialize_component_data(component_name)
            self.manager_logger.debug("Initialized data file for component: %s", component_name)
            
            # Log registration and track initialization
            self.log_component_usage(component_name, "initialized", "Component registered for monitoring")
            logger.info(f"Registered component: {component_name}")
    
    def _initialize_component_data(self, component_name: str):
        """Initialize JSON data file for a component."""
        data_file = self.data_dir / f"{component_name.lower()}_usage.json"
        
        if not data_file.exists():
            initial_data = {
                "component_name": component_name,
                "usage_count": 0,
                "last_used": None,
                "created_at": datetime.now().isoformat()
            }
            
            with open(data_file, 'w') as f:
                json.dump(initial_data, f, indent=2)
            
            self.component_loggers[component_name].debug(f"Initialized data file: {data_file}")
    
    def _load_component_data(self, component_name: str) -> Dict:
        """Load component data from JSON file."""
        data_file = self.data_dir / f"{component_name.lower()}_usage.json"
        
        try:
            with open(data_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.component_loggers[component_name].error(f"Failed to load data: {e}")
            return {}
    
    def _save_component_data(self, component_name: str, data: Dict):
        """Save component data to JSON file."""
        data_file = self.data_dir / f"{component_name.lower()}_usage.json"
        
        try:
            with open(data_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.component_loggers[component_name].error(f"Failed to save data: {e}")
    
    def log_component_usage(self, component_name: str, action: str, details: str = ""):
        """
        Log component usage with timestamp.
        
        Args:
            component_name: Name of the component
            action: Action being performed (e.g., "initialized", "used", "error")
            details: Additional details about the action
        """
        self.manager_logger.debug("Logging usage for component: %s, action: %s", component_name, action)
        
        if component_name not in self.registered_components:
            logger.warning(f"Component {component_name} not registered")
            self.manager_logger.debug("Attempted to log usage for unregistered component: %s", component_name)
            return
        
        # Load current data
        data = self._load_component_data(component_name)
        
        # Update usage count
        if action == "used":
            data["usage_count"] += 1
        
        # Update last used timestamp
        data["last_used"] = datetime.now().isoformat()
        
        # Save data
        self._save_component_data(component_name, data)
        self.manager_logger.debug("Updated usage data for %s: count=%d, action=%s", component_name, data["usage_count"], action)
        
        # Log to component logger
        log_message = f"Action: {action}"
        if details:
            log_message += f" - {details}"
        
        self.component_loggers[component_name].debug(log_message)
    
    def reset_component_usage(self, component_name: str):
        """
        Reset component usage counter to zero.
        
        Args:
            component_name: Name of the component to reset
        """
        if component_name not in self.registered_components:
            logger.warning(f"Component {component_name} not registered")
            return
        
        data = self._load_component_data(component_name)
        data["usage_count"] = 0
        data["reset_at"] = datetime.now().isoformat()
        
        self._save_component_data(component_name, data)
        
        self.component_loggers[component_name].debug("Usage counter reset to zero")
        logger.info(f"Reset usage counter for {component_name}")
    
    def get_component_usage_count(self, component_name: str) -> int:
        """Get current usage count for a component."""
        if component_name not in self.registered_components:
            return 0
        
        data = self._load_component_data(component_name)
        return data.get("usage_count", 0)

    def log_component_error(self, component_name: str, error_message: str):
        """Log an error for a component."""
        self.log_component_usage(component_name, "error", error_message)
        self.component_loggers[component_name].error(error_message)
    
    def log_component_info(self, component_name: str, message: str):
        """Log an info message for a component."""
        self.log_component_usage(component_name, "info", message)
        self.component_loggers[component_name].info(message)
    
    def track_function_call(self, component_name: str, function_name: str, args: tuple = (), kwargs: dict = None):
        """
        Track a function call on a component.
        
        Args:
            component_name: Name of the component
            function_name: Name of the function being called
            args: Function arguments
            kwargs: Function keyword arguments
        """
        if component_name not in self.registered_components:
            return
        
        kwargs = kwargs or {}
        details = f"Function call: {function_name}"
        if args:
            details += f" with args: {args}"
        if kwargs:
            details += f" with kwargs: {kwargs}"
        
        self.log_component_usage(component_name, "function_call", details)
    
    def reg_comp(self, comp_name: str, comp_class: Type, settings_key: str = None):
        """
        Register a component class for auto-instantiation.
        
        Args:
            comp_name: Name to use for the component
            comp_class: The class to instantiate
            settings_key: Key in YAML settings file (defaults to comp_name.lower())
        """
        settings_key_used = settings_key or comp_name.lower()
        self.manager_logger.debug("Registering component class: %s -> %s (settings_key: %s)", comp_name, comp_class.__name__, settings_key_used)
        
        self._component_registry[comp_name] = {
            "class": comp_class,
            "settings_key": settings_key_used
        }
        
        # Initialize component data file for tracking only
        data_file = self.data_dir / f"{comp_name.lower()}_usage.json"
        if not data_file.exists():
            initial_data = {
                "component_name": comp_name,
                "usage_count": 0,
                "last_used": None,
                "created_at": datetime.now().isoformat()
            }
            with open(data_file, 'w') as f:
                json.dump(initial_data, f, indent=2)
            self.manager_logger.debug("Created initial data file for component: %s", comp_name)
        
        logger.info(f"Registered component class: {comp_name} -> {comp_class.__name__}")
        self.manager_logger.debug("Component class registration completed: %s", comp_name)
    
    def create_component(self, component_name: str, settings_file: Path = None, **override_kwargs) -> Any:
        """
        Create and register a component instance using YAML settings.
        
        Args:
            component_name: Name of the component to create
            settings_file: Path to YAML settings file (defaults to deck_sdl2_settings.yaml)
            **override_kwargs: Additional arguments to override settings
            
        Returns:
            The instantiated component
        """
        if component_name not in self._component_registry:
            raise ValueError(f"Component class '{component_name}' not registered. Use register_component_class() first.")
        
        # Load settings from YAML
        from .settings_loader import get_component_settings
        
        registry_entry = self._component_registry[component_name]
        component_class = registry_entry["class"]
        settings_key = registry_entry["settings_key"]
        
        # Load settings from YAML file
        settings = get_component_settings(settings_key, settings_file)
        
        # Override with any provided kwargs
        settings.update(override_kwargs)
        
        # Create component logger first
        comp_logger = self._create_component_logger(component_name)
        self.component_loggers[component_name] = comp_logger
        
        try:
            # Instantiate the component
            comp_logger.info(f"Creating {component_name} with settings: {settings}")
            component = component_class(**settings)
            
            # Assign the component logger to the instance for disconnect methods
            if hasattr(component, '_comp_logger') or hasattr(component, '__dict__'):
                component._comp_logger = comp_logger
                comp_logger.debug(f"Assigned component logger to {component_name} instance")
            
            # Register the component
            self.registered_components[component_name] = component
            
            # Log creation
            self.log_component_usage(component_name, "created", f"Component instantiated with settings: {settings}")
            
            logger.info(f"Created and registered component: {component_name}")
            return component
            
        except Exception as e:
            error_msg = f"Failed to create {component_name}: {str(e)}"
            comp_logger.error(error_msg)
            logger.error(error_msg)
            raise
    
    def get_component(self, component_name: str) -> Optional[Any]:
        """
        Get a registered component instance.
        
        Args:
            component_name: Name of the component
            
        Returns:
            The component instance or None if not found
        """
        return self.registered_components.get(component_name)
    
    def create_components(self, *component_names: str, settings_file: Path = None) -> Dict[str, Any]:
        """
        Create multiple components at once.
        
        Args:
            *component_names: Names of components to create
            settings_file: Path to YAML settings file
            
        Returns:
            Dictionary mapping component names to instances
        """
        components = {}
        for name in component_names:
            try:
                components[name] = self.create_component(name, settings_file=settings_file)
            except Exception as e:
                logger.error(f"Failed to create component {name}: {e}")
                
        return components
    
    def cleanup_component(self, component_name: str):
        """
        Cleanup a specific component.
        
        Args:
            component_name: Name of the component to cleanup
        """
        if component_name not in self.registered_components:
            logger.warning(f"Component {component_name} not registered")
            return
        
        component = self.registered_components[component_name]
        comp_logger = self.component_loggers[component_name]
        
        try:
            # Try common cleanup methods
            cleanup_methods = ['disconnect', 'close', 'stop', 'cleanup', 'shutdown']
            
            for method_name in cleanup_methods:
                if hasattr(component, method_name):
                    method = getattr(component, method_name)
                    if callable(method):
                        comp_logger.debug(f"Calling {method_name}() on {component_name}")
                        method()
                        self.log_component_usage(component_name, "cleanup", f"Successfully called {method_name}()")
                        break
            else:
                comp_logger.debug(f"No standard cleanup method found for {component_name}")
                self.log_component_usage(component_name, "cleanup", "No cleanup method found")
                
        except Exception as e:
            error_msg = f"Error cleaning up {component_name}: {e}"
            comp_logger.error(error_msg)
            self.log_component_usage(component_name, "cleanup_error", error_msg)
    
    def cleanup_all(self):
        """Simple cleanup of all registered components."""
        if self._is_shutting_down:
            self.manager_logger.debug("Cleanup already in progress, skipping duplicate call")
            return
        
        self._is_shutting_down = True
        logger.info("Cleaning up components...")
        self.manager_logger.debug("Starting cleanup of %d registered components", len(self.registered_components))
        
        try:
            # Cleanup all registered components
            for component_name in list(self.registered_components.keys()):
                self.manager_logger.debug("Cleaning up component: %s", component_name)
                self.cleanup_component(component_name)
                self.log_component_usage(component_name, "exit", "Component cleanup completed")
            
            logger.info("Component cleanup completed")
            self.manager_logger.debug("All component cleanup operations completed successfully")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            self.manager_logger.debug("Error during cleanup process: %s", str(e))
        finally:
            self._is_shutting_down = False
    
    def cleanup_old_logs(self, days_to_keep: int = 30):
        """
        Clean up old log files and backups older than specified days.
        
        Args:
            days_to_keep: Number of days of logs to keep (default: 30)
        """
        import glob
        import time
        from pathlib import Path
        
        cutoff_time = time.time() - (days_to_keep * 24 * 60 * 60)
        cleaned_count = 0
        
        self.manager_logger.debug("Starting cleanup of log files older than %d days", days_to_keep)
        
        # Clean up all log files and backups in data directory
        log_patterns = [
            "*.log",
            "*.log.*"  # Backup files like component_history.log.1
        ]
        
        for pattern in log_patterns:
            log_files = glob.glob(str(self.data_dir / pattern))
            for log_file in log_files:
                try:
                    file_path = Path(log_file)
                    if file_path.stat().st_mtime < cutoff_time:
                        file_path.unlink()
                        cleaned_count += 1
                        self.manager_logger.debug("Removed old log file: %s", file_path.name)
                except Exception as e:
                    self.manager_logger.debug("Could not remove log file %s: %s", log_file, str(e))
        
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} old log files (older than {days_to_keep} days)")
            self.manager_logger.debug("Log cleanup completed: removed %d files", cleaned_count)
        else:
            self.manager_logger.debug("No old log files found to clean up")


# Global instance
component_manager = ComponentManager()


# Convenience functions for backward compatibility
def register_for_cleanup(component):
    """Register a component for cleanup (backward compatibility)."""
    component_manager.reg_all_comps(component)


def emergency_shutdown():
    """Trigger cleanup and exit."""
    component_manager.cleanup_all()
    sys.exit(1)
