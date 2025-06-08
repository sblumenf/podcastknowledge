"""Optional dependency management for the VTT pipeline.

This module provides optional dependency handling with fallback implementations
to reduce memory footprint and startup time.
"""

import warnings
from functools import lru_cache
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

# Check for optional dependencies
try:
    import networkx as nx
    HAS_NETWORKX = True
    _networkx_version = getattr(nx, '__version__', 'unknown')
    logger.debug(f"NetworkX {_networkx_version} available")
except ImportError:
    HAS_NETWORKX = False
    nx = None
    logger.debug("NetworkX not available - using fallback implementations")

try:
    import numpy as np
    HAS_NUMPY = True
    _numpy_version = getattr(np, '__version__', 'unknown')
    logger.debug(f"NumPy {_numpy_version} available")
except ImportError:
    HAS_NUMPY = False
    np = None
    logger.debug("NumPy not available - using fallback implementations")

try:
    from scipy.spatial.distance import cosine as scipy_cosine
    HAS_SCIPY = True
    logger.debug("SciPy available")
except ImportError:
    HAS_SCIPY = False
    scipy_cosine = None
    logger.debug("SciPy not available - using fallback implementations")


@lru_cache(maxsize=None)
def _warn_once(message: str):
    """Warn only once per message to avoid spam."""
    warnings.warn(message, ImportWarning, stacklevel=3)


def require_networkx():
    """Raise error if NetworkX is required but not available."""
    if not HAS_NETWORKX:
        raise ImportError(
            "NetworkX is required for advanced graph analysis features. "
            "Install with: pip install networkx"
        )


def require_numpy():
    """Raise error if NumPy is required but not available."""
    if not HAS_NUMPY:
        raise ImportError(
            "NumPy is required for numerical operations. "
            "Install with: pip install numpy"
        )


def require_scipy():
    """Raise error if SciPy is required but not available."""
    if not HAS_SCIPY:
        raise ImportError(
            "SciPy is required for advanced mathematical operations. "
            "Install with: pip install scipy"
        )


# Fallback implementations

def fallback_degree_centrality(graph_dict: Dict[str, List[str]]) -> Dict[str, float]:
    """Pure Python degree centrality fallback for NetworkX."""
    centrality = {}
    total_nodes = len(graph_dict)
    
    if total_nodes <= 1:
        return {node: 0.0 for node in graph_dict}
    
    # Calculate degree for each node
    for node in graph_dict:
        degree = len(graph_dict.get(node, []))
        # Add incoming edges
        for other_node, neighbors in graph_dict.items():
            if node in neighbors:
                degree += 1
        
        # Normalize by (n-1) where n is number of nodes
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


def fallback_cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Pure Python cosine similarity fallback for SciPy."""
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


def cosine_distance(vec1: List[float], vec2: List[float]) -> float:
    """Compute cosine distance with scipy fallback to pure Python."""
    if HAS_SCIPY and HAS_NUMPY:
        try:
            import numpy as np
            arr1 = np.array(vec1)
            arr2 = np.array(vec2)
            return float(scipy_cosine(arr1, arr2))
        except Exception:
            # Fallback if numpy arrays fail
            pass
    
    # Pure Python fallback
    similarity = fallback_cosine_similarity(vec1, vec2)
    return 1.0 - similarity


def get_available_features() -> Dict[str, bool]:
    """Get a dictionary of available optional features."""
    return {
        'networkx_graph_analysis': HAS_NETWORKX,
        'numpy_acceleration': HAS_NUMPY,
        'scipy_math': HAS_SCIPY,
        'fast_centrality': HAS_NETWORKX,
        'fast_cosine': HAS_SCIPY and HAS_NUMPY,
    }


def print_available_features():
    """Print which optional features are available."""
    features = get_available_features()
    
    print("VTT Pipeline - Available Features:")
    print("="*40)
    print(f"  NetworkX graph analysis: {'✓' if features['networkx_graph_analysis'] else '✗ (fallback active)'}")
    print(f"  NumPy acceleration:      {'✓' if features['numpy_acceleration'] else '✗ (pure Python)'}")
    print(f"  SciPy mathematics:       {'✓' if features['scipy_math'] else '✗ (fallback active)'}")
    print()
    
    missing = []
    if not HAS_NETWORKX:
        missing.append('networkx')
    if not HAS_NUMPY:
        missing.append('numpy')
    if not HAS_SCIPY:
        missing.append('scipy')
    
    if missing:
        print("To enable all features:")
        print(f"  pip install {' '.join(missing)}")
        print()
        print("Or install with scientific computing bundle:")
        print("  pip install numpy scipy networkx")
    else:
        print("All optional features are available! ✓")


# Module-level feature documentation
FEATURE_DEPENDENCIES = {
    'basic_vtt_processing': [],  # Core functionality - no extra deps
    'entity_extraction': [],     # Core functionality - no extra deps  
    'neo4j_storage': ['neo4j'],  # Required dependency
    'importance_scoring_basic': [],  # Fallback implementations
    'importance_scoring_advanced': ['networkx'],  # Full graph analysis
    'semantic_similarity_basic': [],  # Pure Python cosine
    'semantic_similarity_fast': ['scipy', 'numpy'],  # Optimized cosine
    'episode_flow_analysis': ['scipy', 'numpy'],  # Requires cosine distance
}


def check_feature_requirements(feature: str) -> tuple[bool, List[str]]:
    """Check if a feature's requirements are met.
    
    Returns:
        (is_available, missing_dependencies)
    """
    if feature not in FEATURE_DEPENDENCIES:
        return False, [f"Unknown feature: {feature}"]
    
    required_deps = FEATURE_DEPENDENCIES[feature]
    missing = []
    
    for dep in required_deps:
        if dep == 'networkx' and not HAS_NETWORKX:
            missing.append('networkx')
        elif dep == 'numpy' and not HAS_NUMPY:
            missing.append('numpy')
        elif dep == 'scipy' and not HAS_SCIPY:
            missing.append('scipy')
        elif dep == 'neo4j':
            # neo4j is always required, checked elsewhere
            pass
    
    return len(missing) == 0, missing