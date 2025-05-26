"""
Deprecation utilities for the podcast knowledge pipeline.

This module provides decorators and utilities for marking deprecated functionality.
"""

import warnings
import functools
from typing import Optional, Callable, Any
from datetime import datetime

from ..utils.logging import get_logger

logger = get_logger(__name__)


def deprecated(
    reason: str,
    version: str,
    removal_version: Optional[str] = None,
    alternative: Optional[str] = None
) -> Callable:
    """
    Decorator to mark functions or methods as deprecated.
    
    Args:
        reason: Reason for deprecation
        version: Version when deprecated
        removal_version: Version when it will be removed (optional)
        alternative: Alternative method/function to use (optional)
        
    Example:
        @deprecated(
            reason="Fixed schema extraction is being replaced by schemaless",
            version="1.1.0",
            removal_version="2.0.0",
            alternative="use schemaless extraction with ENABLE_SCHEMALESS_EXTRACTION=true"
        )
        def old_extraction_method():
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Build deprecation message
            message = f"{func.__name__} is deprecated since version {version}. {reason}"
            
            if alternative:
                message += f" Use {alternative} instead."
                
            if removal_version:
                message += f" It will be removed in version {removal_version}."
            
            # Issue warning
            warnings.warn(
                message,
                category=DeprecationWarning,
                stacklevel=2
            )
            
            # Log deprecation
            logger.warning(f"DEPRECATION: {message}")
            
            # Call original function
            return func(*args, **kwargs)
            
        # Add deprecation info to docstring
        if wrapper.__doc__ is None:
            wrapper.__doc__ = ""
            
        wrapper.__doc__ = (
            f".. deprecated:: {version}\n"
            f"   {reason}\n"
            + (f"   Use {alternative} instead.\n" if alternative else "")
            + (f"   Will be removed in version {removal_version}.\n" if removal_version else "")
            + "\n\n"
            + wrapper.__doc__
        )
        
        # Mark as deprecated
        wrapper.__deprecated__ = True
        wrapper.__deprecated_info__ = {
            "reason": reason,
            "version": version,
            "removal_version": removal_version,
            "alternative": alternative,
            "deprecated_at": datetime.utcnow().isoformat()
        }
        
        return wrapper
    return decorator


def deprecated_class(
    reason: str,
    version: str,
    removal_version: Optional[str] = None,
    alternative: Optional[str] = None
) -> Callable:
    """
    Decorator to mark classes as deprecated.
    
    Args:
        reason: Reason for deprecation
        version: Version when deprecated
        removal_version: Version when it will be removed (optional)
        alternative: Alternative class to use (optional)
    """
    def decorator(cls: type) -> type:
        # Store original __init__
        original_init = cls.__init__
        
        def new_init(self, *args, **kwargs):
            # Build deprecation message
            message = f"{cls.__name__} is deprecated since version {version}. {reason}"
            
            if alternative:
                message += f" Use {alternative} instead."
                
            if removal_version:
                message += f" It will be removed in version {removal_version}."
            
            # Issue warning
            warnings.warn(
                message,
                category=DeprecationWarning,
                stacklevel=2
            )
            
            # Log deprecation
            logger.warning(f"DEPRECATION: {message}")
            
            # Call original __init__
            original_init(self, *args, **kwargs)
        
        # Replace __init__
        cls.__init__ = new_init
        
        # Add deprecation info to docstring
        if cls.__doc__ is None:
            cls.__doc__ = ""
            
        cls.__doc__ = (
            f".. deprecated:: {version}\n"
            f"   {reason}\n"
            + (f"   Use {alternative} instead.\n" if alternative else "")
            + (f"   Will be removed in version {removal_version}.\n" if removal_version else "")
            + "\n\n"
            + cls.__doc__
        )
        
        # Mark as deprecated
        cls.__deprecated__ = True
        cls.__deprecated_info__ = {
            "reason": reason,
            "version": version,
            "removal_version": removal_version,
            "alternative": alternative,
            "deprecated_at": datetime.utcnow().isoformat()
        }
        
        return cls
    return decorator


def pending_deprecation(
    reason: str,
    deprecation_version: str,
    alternative: Optional[str] = None
) -> Callable:
    """
    Decorator to mark functions that will be deprecated in a future version.
    
    Args:
        reason: Reason for future deprecation
        deprecation_version: Version when it will be deprecated
        alternative: Alternative method/function to use (optional)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Build message
            message = (
                f"{func.__name__} will be deprecated in version {deprecation_version}. "
                f"{reason}"
            )
            
            if alternative:
                message += f" Consider using {alternative}."
            
            # Issue pending deprecation warning
            warnings.warn(
                message,
                category=PendingDeprecationWarning,
                stacklevel=2
            )
            
            # Call original function
            return func(*args, **kwargs)
            
        # Mark as pending deprecation
        wrapper.__pending_deprecation__ = True
        wrapper.__pending_deprecation_info__ = {
            "reason": reason,
            "deprecation_version": deprecation_version,
            "alternative": alternative
        }
        
        return wrapper
    return decorator


def check_deprecations(module) -> Dict[str, Any]:
    """
    Check a module for deprecated items.
    
    Args:
        module: Module to check
        
    Returns:
        Dictionary of deprecated items with their info
    """
    deprecated_items = {}
    
    for name in dir(module):
        item = getattr(module, name)
        
        # Check if item is deprecated
        if hasattr(item, "__deprecated__") and item.__deprecated__:
            deprecated_items[name] = {
                "type": "function" if callable(item) else "class",
                "info": item.__deprecated_info__
            }
        elif hasattr(item, "__pending_deprecation__") and item.__pending_deprecation__:
            deprecated_items[name] = {
                "type": "function" if callable(item) else "class",
                "pending": True,
                "info": item.__pending_deprecation_info__
            }
    
    return deprecated_items