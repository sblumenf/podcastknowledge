"""Unified optional dependency management for the seeding pipeline.

This module consolidates all optional dependency handling into a single,
consistent interface. It provides fallbacks for missing dependencies to
ensure the application can run in resource-constrained environments.
"""

import os
import logging
import warnings
from typing import Any, Dict, Optional, List, Callable, Union
from functools import lru_cache
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DependencyInfo:
    """Information about an optional dependency."""
    name: str
    import_name: str
    available: bool
    module: Optional[Any] = None
    mock_class: Optional[type] = None
    fallback_functions: Optional[Dict[str, Callable]] = None
    install_message: str = ""
    description: str = ""


class OptionalDependency:
    """Manages a single optional dependency with lazy loading."""
    
    def __init__(self, 
                 name: str,
                 import_name: Optional[str] = None,
                 mock_class: Optional[type] = None,
                 fallback_functions: Optional[Dict[str, Callable]] = None,
                 install_message: Optional[str] = None,
                 description: str = ""):
        """Initialize optional dependency.
        
        Args:
            name: Display name for the dependency
            import_name: Import path (defaults to name)
            mock_class: Mock class to use when dependency unavailable
            fallback_functions: Dictionary of fallback function implementations
            install_message: Custom install message
            description: Description of what this dependency provides
        """
        self.name = name
        self.import_name = import_name or name
        self.mock_class = mock_class
        self.fallback_functions = fallback_functions or {}
        self.description = description
        
        # Default install message
        if install_message is None:
            self.install_message = f"Install with: pip install {self.name}"
        else:
            self.install_message = install_message
        
        # Lazy loading state
        self._module = None
        self._available = None
        self._import_attempted = False
    
    @property
    def available(self) -> bool:
        """Check if dependency is available (lazy load)."""
        if not self._import_attempted:
            self._try_import()
        return self._available
    
    @property
    def module(self) -> Any:
        """Get the module (real or mock)."""
        if not self._import_attempted:
            self._try_import()
        
        if self._available:
            return self._module
        elif self.mock_class:
            return self.mock_class()
        else:
            return None
    
    def _try_import(self):
        """Attempt to import the dependency."""
        try:
            # Handle nested imports like google.generativeai
            parts = self.import_name.split('.')
            module = __import__(self.import_name)
            
            # Navigate to nested module
            for part in parts[1:]:
                module = getattr(module, part)
            
            self._module = module
            self._available = True
            
            # Log version if available
            version = getattr(module, '__version__', 'unknown')
            logger.debug(f"{self.name} {version} available")
            
        except ImportError:
            self._module = None
            self._available = False
            logger.debug(f"{self.name} not available - using fallback")
        
        self._import_attempted = True
    
    def require(self):
        """Raise ImportError if dependency not available."""
        if not self.available:
            raise ImportError(
                f"{self.name} is required for this feature. {self.install_message}"
            )
    
    def get_fallback(self, function_name: str) -> Optional[Callable]:
        """Get a fallback function by name."""
        return self.fallback_functions.get(function_name)


# Create mock classes for dependencies

class MockPsutilProcess:
    """Mock psutil.Process for when psutil is not available."""
    
    def __init__(self, pid=None):
        self.pid = pid or os.getpid()
    
    def memory_info(self):
        """Return mock memory info."""
        class MemInfo:
            rss = 100 * 1024 * 1024  # Mock 100MB
        return MemInfo()
    
    def memory_percent(self):
        """Return mock memory percentage."""
        return 10.0
    
    def cpu_percent(self, interval=None):
        """Return mock CPU percentage."""
        return 5.0


class MockPsutil:
    """Mock psutil module for when it's not available."""
    
    Process = MockPsutilProcess
    
    @staticmethod
    def cpu_count(logical=True):
        """Return CPU count from os module."""
        try:
            return os.cpu_count() or 1
        except:
            return 1
    
    @staticmethod
    def virtual_memory():
        """Return mock memory stats."""
        class VirtMem:
            total = 4 * 1024 * 1024 * 1024  # Mock 4GB
            available = 2 * 1024 * 1024 * 1024  # Mock 2GB
            percent = 50.0
            used = total - available
            free = available
        return VirtMem()
    
    @staticmethod
    def swap_memory():
        """Return mock swap stats."""
        class SwapMem:
            total = 0
            used = 0
            free = 0
            percent = 0.0
        return SwapMem()


class MockGenAI:
    """Mock google.generativeai module."""
    
    @staticmethod
    def configure(api_key: str):
        """Mock configure method."""
        logger.debug(f"Mock Gemini configuration")
    
    class GenerativeModel:
        """Mock GenerativeModel class."""
        def __init__(self, model_name: str):
            self.model_name = model_name
        
        def embed_content(self, content: Any, task_type: Optional[str] = None) -> Dict[str, Any]:
            """Return mock embedding."""
            return {'embedding': [0.0] * 768}
    
    @staticmethod
    def embed_content(model: str, content: Any, task_type: Optional[str] = None) -> Dict[str, Any]:
        """Mock embed_content matching Gemini API."""
        if isinstance(content, list):
            # Batch embedding
            return {'embedding': [[0.0] * 768 for _ in content]}
        else:
            # Single embedding
            return {'embedding': [0.0] * 768}


# Fallback functions for scientific computing

def fallback_cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Pure Python cosine similarity."""
    if len(vec1) != len(vec2):
        return 0.0
    
    # Compute dot product
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    
    # Compute magnitudes
    mag1 = sum(a * a for a in vec1) ** 0.5
    mag2 = sum(b * b for b in vec2) ** 0.5
    
    if mag1 == 0 or mag2 == 0:
        return 0.0
    
    return dot_product / (mag1 * mag2)


def fallback_degree_centrality(graph_dict: Dict[str, List[str]]) -> Dict[str, float]:
    """Pure Python degree centrality."""
    centrality = {}
    total_nodes = len(graph_dict)
    
    if total_nodes <= 1:
        return {node: 0.0 for node in graph_dict}
    
    for node in graph_dict:
        degree = len(graph_dict.get(node, []))
        # Add incoming edges
        for other_node, neighbors in graph_dict.items():
            if node != other_node and node in neighbors:
                degree += 1
        
        # Normalize
        centrality[node] = degree / (total_nodes - 1)
    
    return centrality


def fallback_betweenness_centrality(graph_dict: Dict[str, List[str]]) -> Dict[str, float]:
    """Simplified betweenness centrality fallback (basic connectivity measure)."""
    centrality = {}
    total_nodes = len(graph_dict)
    
    if total_nodes <= 2:
        return {node: 0.0 for node in graph_dict}
    
    # For large graphs, this would be computationally expensive
    # Use a simplified heuristic based on neighborhood connectivity
    for node in graph_dict:
        neighbors = set(graph_dict.get(node, []))
        
        # Count nodes that can reach this node
        incoming = 0
        for other_node, other_neighbors in graph_dict.items():
            if node in other_neighbors:
                incoming += 1
        
        # Simple heuristic: nodes with more diverse connections
        connectivity_score = (len(neighbors) + incoming) / (2 * total_nodes)
        centrality[node] = min(connectivity_score, 1.0)
    
    return centrality


def fallback_eigenvector_centrality(graph_dict: Dict[str, List[str]]) -> Dict[str, float]:
    """Simplified eigenvector centrality fallback using iterative method."""
    nodes = list(graph_dict.keys())
    n = len(nodes)
    
    if n == 0:
        return {}
    
    # Initialize with equal values
    centrality = {node: 1.0 / n for node in nodes}
    
    # Simple power iteration (limited iterations for performance)
    for iteration in range(10):  # Limited iterations for fallback
        new_centrality = {}
        
        for node in nodes:
            score = 0.0
            # Score based on neighbors' current centrality
            for neighbor in graph_dict.get(node, []):
                score += centrality.get(neighbor, 0.0)
            
            # Include incoming connections
            for other_node, neighbors in graph_dict.items():
                if node in neighbors:
                    score += centrality.get(other_node, 0.0)
            
            new_centrality[node] = score
        
        # Normalize
        total_score = sum(new_centrality.values())
        if total_score > 0:
            for node in nodes:
                new_centrality[node] /= total_score
        
        centrality = new_centrality
    
    return centrality


# Initialize dependency registry

DEPENDENCIES = {
    'psutil': OptionalDependency(
        name='psutil',
        mock_class=MockPsutil,
        description='System and process monitoring',
        install_message='Install with: pip install psutil'
    ),
    
    'networkx': OptionalDependency(
        name='networkx',
        fallback_functions={
            'degree_centrality': fallback_degree_centrality,
            'betweenness_centrality': fallback_betweenness_centrality,
            'eigenvector_centrality': fallback_eigenvector_centrality,
        },
        description='Graph analysis algorithms',
        install_message='Install with: pip install networkx'
    ),
    
    'numpy': OptionalDependency(
        name='numpy',
        description='Numerical computing',
        install_message='Install with: pip install numpy'
    ),
    
    'scipy': OptionalDependency(
        name='scipy',
        fallback_functions={
            'cosine_similarity': fallback_cosine_similarity,
        },
        description='Scientific computing',
        install_message='Install with: pip install scipy'
    ),
    
    'google.generativeai': OptionalDependency(
        name='google-generativeai',
        import_name='google.generativeai',
        mock_class=MockGenAI,
        description='Google Gemini AI API',
        install_message='Install with: pip install google-generativeai'
    ),
}


# Public API functions

def get_dependency(name: str) -> Any:
    """Get a dependency module (real or mock).
    
    Args:
        name: Dependency name
        
    Returns:
        Module object (real or mock)
        
    Raises:
        KeyError: If dependency name not recognized
    """
    if name not in DEPENDENCIES:
        raise KeyError(f"Unknown dependency: {name}")
    
    return DEPENDENCIES[name].module


def is_available(name: str) -> bool:
    """Check if a dependency is available.
    
    Args:
        name: Dependency name
        
    Returns:
        True if available, False otherwise
    """
    if name not in DEPENDENCIES:
        return False
    
    return DEPENDENCIES[name].available


def require(name: str):
    """Require a dependency, raising ImportError if not available.
    
    Args:
        name: Dependency name
        
    Raises:
        ImportError: If dependency not available
        KeyError: If dependency name not recognized
    """
    if name not in DEPENDENCIES:
        raise KeyError(f"Unknown dependency: {name}")
    
    DEPENDENCIES[name].require()


def get_fallback(name: str, function: str) -> Optional[Callable]:
    """Get a fallback function for a dependency.
    
    Args:
        name: Dependency name
        function: Function name
        
    Returns:
        Fallback function or None
    """
    if name not in DEPENDENCIES:
        return None
    
    return DEPENDENCIES[name].get_fallback(function)


# Convenience functions for backward compatibility

def get_psutil():
    """Get psutil module or mock if not available."""
    return get_dependency('psutil')


def get_memory_info() -> Dict[str, Any]:
    """Get memory information with fallback for missing psutil."""
    ps = get_psutil()
    
    try:
        process = ps.Process()
        vm = ps.virtual_memory()
        
        return {
            'process_memory_mb': process.memory_info().rss / 1024 / 1024,
            'process_memory_percent': process.memory_percent() if hasattr(process, 'memory_percent') else 0,
            'system_memory_mb': vm.total / 1024 / 1024,
            'system_memory_percent': vm.percent,
            'memory_percent': vm.percent,
            'available': is_available('psutil')
        }
    except Exception as e:
        logger.debug(f"Error getting memory info: {e}")
        return {
            'process_memory_mb': 0,
            'process_memory_percent': 0,
            'system_memory_mb': 0,
            'system_memory_percent': 0,
            'memory_percent': 0,
            'available': False,
            'error': str(e)
        }


def get_cpu_info() -> Dict[str, Any]:
    """Get CPU information with fallback for missing psutil."""
    ps = get_psutil()
    
    try:
        process = ps.Process()
        
        return {
            'cpu_count': ps.cpu_count(logical=True),
            'process_cpu_percent': process.cpu_percent(interval=0.1),
            'system_cpu_percent': process.cpu_percent(interval=0.1),  # Simplified
            'available': is_available('psutil')
        }
    except Exception as e:
        logger.debug(f"Error getting CPU info: {e}")
        return {
            'cpu_count': os.cpu_count() or 1,
            'process_cpu_percent': 0,
            'system_cpu_percent': 0,
            'available': False,
            'error': str(e)
        }


# Export availability flags for backward compatibility
PSUTIL_AVAILABLE = is_available('psutil')
HAS_NETWORKX = is_available('networkx')
HAS_NUMPY = is_available('numpy')
HAS_SCIPY = is_available('scipy')
GOOGLE_AI_AVAILABLE = is_available('google.generativeai')


@lru_cache(maxsize=None)
def _warn_once(message: str):
    """Warn only once per message to avoid spam."""
    warnings.warn(message, ImportWarning, stacklevel=3)


def get_available_features() -> Dict[str, bool]:
    """Get a dictionary of available optional features."""
    return {
        'psutil_monitoring': PSUTIL_AVAILABLE,
        'networkx_graph_analysis': HAS_NETWORKX,
        'numpy_acceleration': HAS_NUMPY,
        'scipy_math': HAS_SCIPY,
        'google_ai_embeddings': GOOGLE_AI_AVAILABLE,
    }


def print_dependency_status():
    """Print status of all optional dependencies."""
    print("Seeding Pipeline - Dependency Status:")
    print("=" * 50)
    
    for name, dep in DEPENDENCIES.items():
        status = "✓" if dep.available else "✗"
        print(f"  {status} {dep.name:<20} - {dep.description}")
    
    print()
    
    # List missing dependencies
    missing = [dep for dep in DEPENDENCIES.values() if not dep.available]
    if missing:
        print("To install missing dependencies:")
        for dep in missing:
            print(f"  {dep.install_message}")
    else:
        print("All optional dependencies are available! ✓")