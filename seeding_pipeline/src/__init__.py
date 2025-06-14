"""VTT Knowledge Extraction Pipeline - SimpleKGPipeline Implementation.

Main API:
    - EnhancedKnowledgePipeline: Main pipeline using SimpleKGPipeline for extraction
"""

from .__version__ import __version__, __version_info__, __api_version__

# Note: VTTKnowledgeExtractor has been removed
# Use EnhancedKnowledgePipeline from src.pipeline.enhanced_knowledge_pipeline instead

__all__ = [
    '__version__',
    '__version_info__',
    '__api_version__',
]