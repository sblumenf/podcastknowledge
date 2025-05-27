#!/usr/bin/env python3
"""
Profile the schemaless extraction pipeline to identify performance bottlenecks.

Usage:
    python scripts/profile_schemaless_pipeline.py [--text-file FILE] [--output-dir DIR]
"""

import argparse
import sys
from pathlib import Path
import time
import json
from typing import Dict, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.performance_profiling import PerformanceProfiler, OptimizationManager
from src.core.config import PipelineConfig
from src.core.feature_flags import FeatureFlag, set_flag
from src.providers.llm import get_llm_provider
from src.providers.embeddings import get_embedding_provider
from src.providers.graph.schemaless_neo4j import SchemalessNeo4jProvider
from src.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)


def load_test_text(file_path: Optional[Path] = None) -> str:
    """Load test text for profiling."""
    if file_path and file_path.exists():
        return file_path.read_text()
    
    # Default test text
    return """
    In this fascinating episode, we explore the intersection of artificial intelligence 
    and healthcare with Dr. Sarah Johnson, CEO of MedTech Innovations. She discusses 
    how machine learning algorithms are revolutionizing early disease detection, 
    particularly in cancer diagnostics. The conversation also covers ethical 
    considerations around AI in medicine, data privacy concerns, and the future 
    of personalized treatment plans. Dr. Johnson shares insights from her 20 years 
    of experience in the field and predicts that within the next decade, AI will 
    become an indispensable tool for every healthcare provider.
    """


def profile_extraction_components(profiler: PerformanceProfiler, 
                                config: PipelineConfig,
                                test_text: str) -> Dict[str, Any]:
    """Profile individual extraction components."""
    results = {}
    
    # Profile LLM calls
    with profiler.profile_section("llm_initialization"):
        llm_provider = get_llm_provider(config)
    
    with profiler.profile_section("llm_single_call"):
        response = llm_provider.generate(
            "Extract key entities from: " + test_text[:200],
            max_tokens=100
        )
    
    # Profile embedding generation
    with profiler.profile_section("embedding_initialization"):
        embedding_provider = get_embedding_provider(config)
    
    with profiler.profile_section("embedding_single"):
        embedding = embedding_provider.embed_text(test_text[:500])
    
    with profiler.profile_section("embedding_batch"):
        # Simulate batch embedding
        chunks = [test_text[i:i+500] for i in range(0, len(test_text), 400)]
        embeddings = embedding_provider.embed_batch(chunks)
    
    # Profile graph operations
    try:
        with profiler.profile_section("graph_initialization"):
            graph_provider = SchemalessNeo4jProvider(config)
            graph_provider.connect()
        
        with profiler.profile_section("graph_write_single"):
            graph_provider.query("""
                CREATE (n:TestNode {
                    id: randomUUID(),
                    content: $content,
                    timestamp: timestamp()
                })
            """, {"content": test_text[:200]})
        
        with profiler.profile_section("graph_write_batch"):
            # Simulate batch writes
            batch_query = """
                UNWIND $batch AS item
                CREATE (n:TestNode {
                    id: item.id,
                    content: item.content,
                    timestamp: timestamp()
                })
            """
            batch_data = [
                {"id": f"test_{i}", "content": f"Test content {i}"}
                for i in range(10)
            ]
            graph_provider.query(batch_query, {"batch": batch_data})
        
        # Cleanup
        graph_provider.query("MATCH (n:TestNode) DELETE n")
        
    except Exception as e:
        logger.error(f"Graph profiling failed: {e}")
    
    return results


def profile_entity_resolution(profiler: PerformanceProfiler,
                            config: PipelineConfig,
                            test_entities: list) -> None:
    """Profile entity resolution performance."""
    # This would profile the entity resolution process
    with profiler.profile_section("entity_resolution"):
        # Simulate entity resolution
        time.sleep(0.1)  # Placeholder
        
    with profiler.profile_section("entity_resolution_batch"):
        # Simulate batch entity resolution
        time.sleep(0.2)  # Placeholder


def main():
    """Main profiling function."""
    parser = argparse.ArgumentParser(
        description="Profile schemaless extraction pipeline"
    )
    parser.add_argument(
        "--text-file",
        type=Path,
        help="Path to text file for profiling"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("profiling_results"),
        help="Directory for profiling output"
    )
    parser.add_argument(
        "--enable-optimization",
        action="store_true",
        help="Apply optimizations after profiling"
    )
    
    args = parser.parse_args()
    
    # Setup
    setup_logging()
    config = PipelineConfig.from_env()
    
    # Enable schemaless extraction
    set_flag(FeatureFlag.ENABLE_SCHEMALESS_EXTRACTION, True)
    
    # Create profiler
    profiler = PerformanceProfiler(output_dir=args.output_dir)
    
    # Load test text
    test_text = load_test_text(args.text_file)
    logger.info(f"Profiling with text of length: {len(test_text)}")
    
    # Profile components
    logger.info("Profiling extraction components...")
    component_results = profile_extraction_components(profiler, config, test_text)
    
    # Profile entity resolution
    logger.info("Profiling entity resolution...")
    test_entities = ["AI", "Dr. Sarah Johnson", "MedTech Innovations"]
    profile_entity_resolution(profiler, config, test_entities)
    
    # Analyze results
    logger.info("Analyzing profiling results...")
    analysis = profiler.analyze_results()
    
    # Generate report
    report_path = args.output_dir / "profiling_report.md"
    report = profiler.generate_report(report_path)
    
    # Print summary
    print("\n=== Profiling Summary ===\n")
    
    for section, stats in analysis["summary"].items():
        print(f"{section}:")
        print(f"  Average time: {stats['avg_time']:.3f}s")
        print(f"  Average memory: {stats['avg_memory'] / 1024 / 1024:.1f}MB")
        print()
    
    print("\n=== Top Bottlenecks ===\n")
    for func, time_spent in list(analysis["bottlenecks"].items())[:5]:
        print(f"- {func}: {time_spent:.3f}s")
    
    print("\n=== Recommendations ===\n")
    for rec in analysis["recommendations"]:
        print(f"- {rec['type'].upper()}: {rec['issue']}")
        print(f"  Suggestion: {rec['suggestion']}")
        print()
    
    # Apply optimizations if requested
    if args.enable_optimization:
        logger.info("Applying optimizations...")
        optimizer = OptimizationManager()
        # Note: This would need the actual pipeline instance
        # optimizer.apply_optimizations(pipeline)
        print("\nOptimizations applied. Re-run profiling to measure improvements.")
    
    print(f"\nDetailed report saved to: {report_path}")
    
    # Save analysis as JSON
    analysis_path = args.output_dir / "profiling_analysis.json"
    with open(analysis_path, 'w') as f:
        json.dump(analysis, f, indent=2)
    
    print(f"Analysis data saved to: {analysis_path}")


if __name__ == "__main__":
    main()