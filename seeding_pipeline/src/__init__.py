"""VTT Knowledge Extraction Pipeline - Streamlined Implementation.

Main API:
    - VTTKnowledgeExtractor: Main pipeline orchestrator for VTT processing
    - extract_vtt_knowledge: Extract knowledge from a single VTT file
    - extract_vtt_directory: Extract knowledge from directory of VTT files
"""

from .__version__ import __version__, __version_info__, __api_version__
from .seeding import VTTKnowledgeExtractor
# Convenience functions
def extract_vtt_knowledge(vtt_file_path, use_large_context=True, config=None):
    """Extract knowledge from a single VTT file.
    
    Args:
        vtt_file_path: Path to VTT file
        use_large_context: Whether to use large context models
        config: Optional configuration object
    
    Returns:
        Processing summary dict
    """
    from .core.config import Config
    from pathlib import Path
    
    if config is None:
        config = Config()
    
    pipeline = VTTKnowledgeExtractor(config)
    try:
        return pipeline.process_vtt_files([Path(vtt_file_path)], use_large_context)
    finally:
        pipeline.cleanup()


def extract_vtt_directory(directory_path, pattern="*.vtt", recursive=False, 
                         use_large_context=True, config=None):
    """Extract knowledge from VTT files in a directory.
    
    Args:
        directory_path: Path to directory containing VTT files
        pattern: File pattern to match (default: *.vtt)
        recursive: Whether to search subdirectories
        use_large_context: Whether to use large context models
        config: Optional configuration object
    
    Returns:
        Summary dict with processing statistics
    """
    from .core.config import Config
    
    if config is None:
        config = Config()
    
    pipeline = VTTKnowledgeExtractor(config)
    try:
        return pipeline.process_vtt_directory(
            directory_path, pattern, recursive, use_large_context
        )
    finally:
        pipeline.cleanup()


__all__ = [
    '__version__',
    '__version_info__',
    '__api_version__',
    'VTTKnowledgeExtractor',
    'extract_vtt_knowledge',
    'extract_vtt_directory',
]