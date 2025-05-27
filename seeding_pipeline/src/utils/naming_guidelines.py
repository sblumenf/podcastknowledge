"""
Method naming guidelines and examples for the podcast knowledge pipeline.

This module provides guidelines for clear, descriptive method names
and includes examples of refactored methods with improved names.
"""

# Method Naming Guidelines
METHOD_NAMING_GUIDELINES = """
Method Naming Guidelines for Podcast Knowledge Pipeline
======================================================

1. Use Descriptive Verb-Noun Combinations
   - Bad: process(), handle(), do()
   - Good: extract_entities(), validate_episode_data(), calculate_similarity_score()

2. Be Specific About What the Method Does
   - Bad: work(), execute(), run()
   - Good: transcribe_audio(), resolve_entity_conflicts(), aggregate_metrics()

3. Include Context in the Name
   - Bad: save(), load(), update()
   - Good: save_checkpoint_to_disk(), load_episode_from_cache(), update_graph_relationships()

4. Use Consistent Prefixes for Common Operations
   - get_*: Returns a value without side effects (get_episode_metadata)
   - find_*: Searches for something (find_similar_entities)
   - create_*: Creates and returns a new object (create_extraction_result)
   - build_*: Constructs something complex (build_knowledge_graph)
   - calculate_*: Performs computation (calculate_importance_score)
   - validate_*: Checks validity (validate_audio_format)
   - parse_*: Parses input (parse_rss_feed)
   - extract_*: Extracts information (extract_key_insights)
   - transform_*: Transforms data (transform_to_graph_format)

5. Avoid Generic Single Words
   - Bad: process(), handle(), manage()
   - Good: process_audio_segment(), handle_extraction_error(), manage_provider_lifecycle()

6. Include Units or Types in Names When Relevant
   - Bad: get_duration(), set_timeout()
   - Good: get_duration_seconds(), set_timeout_milliseconds()

7. Use Boolean Prefixes for Boolean Methods
   - is_*: Check state (is_episode_completed)
   - has_*: Check existence (has_valid_audio)
   - can_*: Check capability (can_process_schemaless)
   - should_*: Check condition (should_retry_request)

8. Always Add Docstrings
   - Every public method should have a docstring
   - Include Args, Returns, and Raises sections
   - Add usage examples for complex methods
"""


# Example refactorings
class MethodNamingExamples:
    """Examples of method naming improvements."""
    
    # Before: Generic name
    def process(self, data):
        """Process data."""
        pass
    
    # After: Specific name
    def extract_entities_from_transcript(self, transcript_data):
        """
        Extract named entities from podcast transcript.
        
        Args:
            transcript_data: Dictionary containing transcript segments
            
        Returns:
            List of Entity objects with confidence scores
        """
        pass
    
    # Before: Unclear abbreviation
    def gen_viz_data(self, nodes):
        """Generate viz data."""
        pass
    
    # After: Clear full name
    def generate_visualization_data(self, graph_nodes):
        """
        Generate data structure for graph visualization.
        
        Args:
            graph_nodes: List of nodes from the knowledge graph
            
        Returns:
            Dictionary with nodes, edges, and layout information for visualization
        """
        pass
    
    # Before: Missing context
    def save(self, obj):
        """Save object."""
        pass
    
    # After: Context included
    def save_extraction_checkpoint(self, extraction_state):
        """
        Save extraction state to checkpoint file.
        
        Args:
            extraction_state: Current state of extraction process
            
        Returns:
            Path to saved checkpoint file
            
        Raises:
            IOError: If checkpoint cannot be saved
        """
        pass
    
    # Before: Non-descriptive
    def handle(self, error):
        """Handle error."""
        pass
    
    # After: Specific error handling
    def handle_rate_limit_error(self, rate_limit_error):
        """
        Handle API rate limit errors with exponential backoff.
        
        Args:
            rate_limit_error: RateLimitError exception from API
            
        Returns:
            True if request should be retried, False otherwise
        """
        pass
    
    # Before: Generic single word
    def execute(self):
        """Execute."""
        pass
    
    # After: Specific operation
    def execute_knowledge_extraction_pipeline(self):
        """
        Execute the complete knowledge extraction pipeline.
        
        Orchestrates audio processing, transcription, entity extraction,
        and graph construction for a podcast episode.
        
        Returns:
            PipelineResult with extraction metrics and status
        """
        pass


# Real examples from the codebase that could be improved
REFACTORING_SUGGESTIONS = {
    # From src/utils/retry.py
    "execute": "execute_with_retry",
    
    # From src/utils/logging.py
    "process": "process_log_record",
    
    # From src/processing/graph_analysis.py
    "path_score": "calculate_path_importance_score",
    "gap_id": "generate_knowledge_gap_identifier",
    
    # From src/migration/query_translator.py
    "replace_node": "replace_node_label_in_query",
    "replace_rel": "replace_relationship_type_in_query",
    
    # Generic timeout handlers
    "timeout_handler": "handle_operation_timeout",
    
    # Generic wrappers
    "async_wrapper": "wrap_with_async_tracing",
    "sync_wrapper": "wrap_with_sync_tracing",
    
    # From various files
    "run": "run_graph_query",  # Context: Neo4j session
    "on_llm_start": "handle_llm_request_start",
    "on_llm_end": "handle_llm_request_completion",
    "on_llm_error": "handle_llm_request_error",
}


def suggest_better_name(current_name: str, context: str = "") -> str:
    """
    Suggest a better name for a method based on context.
    
    Args:
        current_name: Current method name
        context: Optional context about what the method does
        
    Returns:
        Suggested improved name
    """
    # Check if we have a specific suggestion
    if current_name in REFACTORING_SUGGESTIONS:
        return REFACTORING_SUGGESTIONS[current_name]
    
    # Apply general rules
    if current_name in ['process', 'handle', 'do', 'run', 'execute']:
        return f"{current_name}_{context}" if context else f"{current_name}_operation"
    
    # Add verb if missing
    if not any(current_name.startswith(prefix) for prefix in 
               ['get_', 'set_', 'is_', 'has_', 'can_', 'should_',
                'create_', 'build_', 'find_', 'calculate_', 'validate_',
                'parse_', 'extract_', 'transform_']):
        return f"perform_{current_name}"
    
    return current_name


# Example of adding docstrings to methods that lack them
def add_docstring_example(func):
    """
    Decorator to add a template docstring to methods lacking one.
    
    This is just an example - in practice, docstrings should be
    written specifically for each method.
    """
    if not func.__doc__:
        func.__doc__ = f"""
        {func.__name__.replace('_', ' ').title()}.
        
        TODO: Add proper documentation including:
        - What this method does
        - Args with types and descriptions
        - Returns with type and description
        - Raises for any exceptions
        - Example usage if complex
        """
    return func


__all__ = [
    'METHOD_NAMING_GUIDELINES',
    'MethodNamingExamples',
    'REFACTORING_SUGGESTIONS',
    'suggest_better_name'
]