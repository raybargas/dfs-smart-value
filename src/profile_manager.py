"""
Personal Weight Profile Manager

Manages personal weight profiles for Ray and Chris with persistent storage.
"""

import json
import os
from typing import Dict, Any, Optional
from pathlib import Path


# Profile names for Ray and Chris
RAY_PROFILES = ['Ray_Default', 'Ray_Tournament', 'Ray_Cash']
CHRIS_PROFILES = ['Chris_Default', 'Chris_Tournament', 'Chris_Cash']
ALL_PROFILES = RAY_PROFILES + CHRIS_PROFILES

# Default balanced weights (current configuration)
DEFAULT_WEIGHTS = {
    'base': 0.15,
    'opportunity': 0.22,
    'trends': 0.13,
    'risk': 0.05,
    'matchup': 0.19,
    'leverage': 0.13,
    'regression': 0.13
}

# Default sub-weights for fine-grained control
DEFAULT_SUB_WEIGHTS = {
    'opp_target_share': 0.40,
    'opp_snap_pct': 0.30,
    'opp_rz_targets': 0.20,  # Changed from 'opp_redzone' to match smart_value_calculator.py
    'opp_air_yards': 0.10,
    'trend_momentum': 0.40,
    'trend_role_growth': 0.35,
    'trend_recent_fp': 0.25,
    'risk_variance': 0.60,
    'risk_consistency': 0.40
}

# Default position-specific weights (empty by default)
DEFAULT_POSITION_WEIGHTS = {}

# Default thresholds and settings
DEFAULT_THRESHOLDS = {
    'smart_threshold': 60,
    'ownership_threshold': 25,
    'salary_threshold': 8000,
    'projection_threshold': 15
}


def get_profiles_file_path() -> Path:
    """Get the path to the profiles.json file."""
    return Path(__file__).parent.parent / "profiles.json"


def load_profiles() -> Dict[str, Dict[str, float]]:
    """
    Load profiles from file or return defaults.
    
    Returns:
        Dictionary mapping profile names to weight configurations
    """
    profiles_file = get_profiles_file_path()
    
    if not profiles_file.exists():
        return _create_default_profiles()
    
    try:
        with open(profiles_file, 'r') as f:
            profiles = json.load(f)
        
        # Ensure all required profiles exist
        all_profiles = _create_default_profiles()
        all_profiles.update(profiles)
        
        return all_profiles
        
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error loading profiles: {e}")
        return _create_default_profiles()


def save_profiles(profiles: Dict[str, Dict[str, float]]) -> bool:
    """
    Save profiles to file.
    
    Args:
        profiles: Dictionary mapping profile names to weight configurations
    
    Returns:
        True if successful, False otherwise
    """
    profiles_file = get_profiles_file_path()
    
    try:
        with open(profiles_file, 'w') as f:
            json.dump(profiles, f, indent=2)
        return True
        
    except IOError as e:
        print(f"Error saving profiles: {e}")
        return False


def _create_default_profiles() -> Dict[str, Dict[str, Any]]:
    """Create default profiles for Ray and Chris with complete configuration."""
    profiles = {}
    
    # Complete default configuration
    default_config = {
        'main_weights': DEFAULT_WEIGHTS.copy(),
        'sub_weights': DEFAULT_SUB_WEIGHTS.copy(),
        'position_weights': DEFAULT_POSITION_WEIGHTS.copy(),
        'thresholds': DEFAULT_THRESHOLDS.copy()
    }
    
    # Ray profiles (all start with current balanced configuration)
    for profile_name in RAY_PROFILES:
        profiles[profile_name] = {
            'main_weights': DEFAULT_WEIGHTS.copy(),
            'sub_weights': DEFAULT_SUB_WEIGHTS.copy(),
            'position_weights': DEFAULT_POSITION_WEIGHTS.copy(),
            'thresholds': DEFAULT_THRESHOLDS.copy()
        }
    
    # Chris profiles (all start with current balanced configuration)
    for profile_name in CHRIS_PROFILES:
        profiles[profile_name] = {
            'main_weights': DEFAULT_WEIGHTS.copy(),
            'sub_weights': DEFAULT_SUB_WEIGHTS.copy(),
            'position_weights': DEFAULT_POSITION_WEIGHTS.copy(),
            'thresholds': DEFAULT_THRESHOLDS.copy()
        }
    
    return profiles


def get_profile_config(profile_name: str) -> Optional[Dict[str, Any]]:
    """
    Get complete configuration for a specific profile.
    
    Args:
        profile_name: Name of the profile
    
    Returns:
        Dictionary with main_weights, sub_weights, position_weights, thresholds or None if profile not found
    """
    profiles = load_profiles()
    return profiles.get(profile_name)


def save_profile_config(profile_name: str, config: Dict[str, Any]) -> bool:
    """
    Save complete configuration for a specific profile.
    
    Args:
        profile_name: Name of the profile
        config: Dictionary with main_weights, sub_weights, position_weights, thresholds
    
    Returns:
        True if successful, False otherwise
    """
    profiles = load_profiles()
    
    # Ensure all required sections exist
    full_config = {
        'main_weights': config.get('main_weights', DEFAULT_WEIGHTS.copy()),
        'sub_weights': config.get('sub_weights', DEFAULT_SUB_WEIGHTS.copy()),
        'position_weights': config.get('position_weights', DEFAULT_POSITION_WEIGHTS.copy()),
        'thresholds': config.get('thresholds', DEFAULT_THRESHOLDS.copy())
    }
    
    profiles[profile_name] = full_config
    return save_profiles(profiles)


# Backward compatibility functions
def get_profile_weights(profile_name: str) -> Optional[Dict[str, float]]:
    """Get main weights for a specific profile (backward compatibility)."""
    config = get_profile_config(profile_name)
    return config.get('main_weights') if config else None


def save_profile_weights(profile_name: str, weights: Dict[str, float]) -> bool:
    """Save main weights for a specific profile (backward compatibility)."""
    config = get_profile_config(profile_name) or {}
    config['main_weights'] = weights.copy()
    return save_profile_config(profile_name, config)


def get_ray_profiles() -> Dict[str, Dict[str, float]]:
    """Get all Ray profiles."""
    profiles = load_profiles()
    return {name: weights for name, weights in profiles.items() if name in RAY_PROFILES}


def get_chris_profiles() -> Dict[str, Dict[str, float]]:
    """Get all Chris profiles."""
    profiles = load_profiles()
    return {name: weights for name, weights in profiles.items() if name in CHRIS_PROFILES}


def validate_weights(weights: Dict[str, float]) -> bool:
    """
    Validate that weights sum to 1.0 (100%).
    
    Args:
        weights: Dictionary of weights
    
    Returns:
        True if valid, False otherwise
    """
    total = sum(weights.values())
    return abs(total - 1.0) < 0.001


def validate_config(config: Dict[str, Any]) -> bool:
    """
    Validate complete configuration.
    
    Args:
        config: Dictionary with main_weights, sub_weights, position_weights, thresholds
    
    Returns:
        True if valid, False otherwise
    """
    # Validate main weights
    main_weights = config.get('main_weights', {})
    if not validate_weights(main_weights):
        return False
    
    # Validate sub-weights (should sum to 1.0 for each category)
    sub_weights = config.get('sub_weights', {})
    
    # Opportunity sub-weights
    opp_weights = [sub_weights.get('opp_target_share', 0), sub_weights.get('opp_snap_pct', 0), 
                   sub_weights.get('opp_redzone', 0), sub_weights.get('opp_air_yards', 0)]
    if abs(sum(opp_weights) - 1.0) > 0.001:
        return False
    
    # Trend sub-weights
    trend_weights = [sub_weights.get('trend_momentum', 0), sub_weights.get('trend_role_growth', 0), 
                     sub_weights.get('trend_recent_fp', 0)]
    if abs(sum(trend_weights) - 1.0) > 0.001:
        return False
    
    # Risk sub-weights
    risk_weights = [sub_weights.get('risk_variance', 0), sub_weights.get('risk_consistency', 0)]
    if abs(sum(risk_weights) - 1.0) > 0.001:
        return False
    
    return True


def get_profile_display_name(profile_name: str) -> str:
    """
    Get a display-friendly name for a profile.
    
    Args:
        profile_name: Internal profile name
    
    Returns:
        Display name
    """
    if profile_name.startswith('Ray_'):
        return f"Ray - {profile_name[4:]}"
    elif profile_name.startswith('Chris_'):
        return f"Chris - {profile_name[6:]}"
    else:
        return profile_name


def get_user_from_profile(profile_name: str) -> str:
    """
    Get the user (Ray or Chris) from a profile name.
    
    Args:
        profile_name: Profile name
    
    Returns:
        'Ray' or 'Chris'
    """
    if profile_name.startswith('Ray_'):
        return 'Ray'
    elif profile_name.startswith('Chris_'):
        return 'Chris'
    else:
        return 'Unknown'
