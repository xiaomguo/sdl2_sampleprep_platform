"""
Simple Settings Loader for SDL2
Just loads settings from YAML file when needed.
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional


def load_sdl2_settings(settings_file: Path = None) -> Dict[str, Any]:
    """
    Load SDL2 settings from YAML file.
    
    Args:
        settings_file: Path to settings file (default: deck_sdl2_settings.yaml)
    
    Returns:
        Dictionary containing all settings
    """
    if settings_file is None:
        # Default to SDL2 implementation settings
        settings_file = Path(__file__).resolve().parents[2] / "implementations" / "SDL2" / "deck_sdl2_settings.yaml"
    
    try:
        with open(settings_file, 'r') as f:
            settings = yaml.safe_load(f)
        return settings or {}
    except Exception as e:
        print(f"Warning: Could not load settings from {settings_file}: {e}")
        return {}


def get_component_settings(component_name: str, settings_file: Path = None) -> Dict[str, Any]:
    """
    Get settings for a specific component.
    Supports nested keys like 'cameras.easymax'
    
    Args:
        component_name: Name of the component (e.g., 'robot', 'cameras.easymax')
        settings_file: Path to settings file
    
    Returns:
        Component settings dictionary
    """
    all_settings = load_sdl2_settings(settings_file)
    
    # Handle nested keys like 'cameras.easymax'
    if '.' in component_name:
        keys = component_name.split('.')
        result = all_settings
        for key in keys:
            result = result.get(key, {})
            if not isinstance(result, dict):
                return {}
        return result
    else:
        return all_settings.get(component_name, {})


def get_setting(component_name: str, setting_key: str, default: Any = None, settings_file: Path = None) -> Any:
    """
    Get a specific setting value.
    
    Args:
        component_name: Name of the component
        setting_key: Key of the setting
        default: Default value if not found
        settings_file: Path to settings file
    
    Returns:
        Setting value or default
    """
    component_settings = get_component_settings(component_name, settings_file)
    return component_settings.get(setting_key, default)


# Example usage:
if __name__ == "__main__":
    # Load all settings
    settings = load_sdl2_settings()
    print("All settings:", settings)
    
    # Get robot settings
    robot_settings = get_component_settings("robot")
    print("Robot settings:", robot_settings)
    
    # Get specific setting
    robot_ip = get_setting("robot", "rob_ip", "192.168.1.100")
    print("Robot IP:", robot_ip)
