"""Performance benchmarks for schemaless vs fixed schema processing."""

from dataclasses import dataclass
from typing import Dict, List, Any
from unittest.mock import MagicMock, AsyncMock
import asyncio
import time

import pytest
import statistics

from src.core.extraction_interface import Segment, Episode, Podcast
from src.providers.embeddings.mock import MockEmbeddingProvider
from src.providers.graph.neo4j import Neo4jProvider
from src.providers.graph.schemaless_neo4j import SchemalessNeo4jProvider
from src.providers.llm.mock import MockLLMProvider
@dataclass
class BenchmarkResult:
    """Container for benchmark results."""
    operation: str
    schema_type: str
    avg_time: float
    min_time: float
    max_time: float
    std_dev: float
    memory_usage_mb: float
    token_count: int
    iterations: int


class SchemalessPerformanceBenchmark:
    """Performance benchmark suite for schemaless implementation."""

    def __init__(self):
        self.results: List[BenchmarkResult] = []
        self.mock_llm = MockLLMProvider({"response_mode": "json"})
        self.mock_embeddings = MockEmbeddingProvider({"dimension": 384})

    def setup_providers(self) -> tuple:
        """Set up both fixed and schemaless providers for comparison."""
        # Mock Neo4j driver
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session
        
        # Create providers
        config = {
            "uri": "bolt://localhost:7687",
            "username": "neo4j",
            "password": "test"
        }
        
        fixed_provider = Neo4jProvider(config)
        fixed_provider.driver = mock_driver
        
        schemaless_provider = SchemalessNeo4jProvider(config)
        schemaless_provider.driver = mock_driver
        schemaless_provider.llm_adapter = MagicMock()
        schemaless_provider.embedding_adapter = MagicMock()
        schemaless_provider.pipeline = MagicMock()
        schemaless_provider.pipeline.run_async = AsyncMock(return_value={"entities": [], "relationships": []})
        
        return fixed_provider, schemaless_provider

    def measure_memory_usage(self) -> float:
        """Measure current memory usage in MB."""
        import psutil
        import os
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / 1024 / 1024

    async def benchmark_operation(
        self, 
        operation_name: str,
        schema_type: str,
        operation_func,
        iterations: int = 10
    ) -> BenchmarkResult:
        """Benchmark a specific operation."""
        times = []
        memory_before = self.measure_memory_usage()
        token_count = 0
        
        for _ in range(iterations):
            start_time = time.perf_counter()
            result = await operation_func()
            end_time = time.perf_counter()
            times.append(end_time - start_time)
            
            # Track token usage if available
            if hasattr(result, 'token_count'):
                token_count += result.get("token_count", 0)
        
        memory_after = self.measure_memory_usage()
        memory_usage = memory_after - memory_before
        
        return BenchmarkResult(
            operation=operation_name,
            schema_type=schema_type,
            avg_time=statistics.mean(times),
            min_time=min(times),
            max_time=max(times),
            std_dev=statistics.stdev(times) if len(times) > 1 else 0,
            memory_usage_mb=memory_usage,
            token_count=token_count,
            iterations=iterations
        )

    async def benchmark_segment_processing(self):
        """Benchmark processing time per segment."""
        fixed_provider, schemaless_provider = self.setup_providers()
        
        # Create test segment
        segment = Segment(
            id="seg1",
            episode_id="ep1",
            start_time=0.0,
            end_time=60.0,
            text="This is a test segment about artificial intelligence, machine learning, and neural networks. "
                 "Companies like Google, OpenAI, and Microsoft are leading the AI revolution.",
            speaker="Host"
        )
        
        # Benchmark fixed schema
        async def fixed_operation():
            return await fixed_provider.store_segments([segment])
        
        fixed_result = await self.benchmark_operation(
            "segment_processing",
            "fixed",
            fixed_operation,
            iterations=20
        )
        self.results.append(fixed_result)
        
        # Benchmark schemaless
        from src.core.models import Episode, Podcast
        from datetime import datetime
        
        episode = Episode(id="ep1", podcast_id="pod1", title="Test Episode", publication_date=datetime.now())
        podcast = Podcast(id="pod1", title="Test Podcast")
        
        async def schemaless_operation():
            return schemaless_provider.process_segment_schemaless(segment, episode, podcast)
        
        schemaless_result = await self.benchmark_operation(
            "segment_processing",
            "schemaless",
            schemaless_operation,
            iterations=20
        )
        self.results.append(schemaless_result)

    async def benchmark_memory_usage(self):
        """Benchmark memory usage for batch processing."""
        fixed_provider, schemaless_provider = self.setup_providers()
        
        # Create batch of segments
        segments = []
        for i in range(100):
            segments.append(Segment(
                id=f"seg{i}",
                episode_id="ep1",
                start_time=i * 60.0,
                end_time=(i + 1) * 60.0,
                text=f"Segment {i} discussing various topics including technology, science, and innovation.",
                speaker="Host" if i % 2 == 0 else "Guest"
            ))
        
        # Measure fixed schema memory
        memory_before = self.measure_memory_usage()
        await fixed_provider.store_segments(segments)
        memory_fixed = self.measure_memory_usage() - memory_before
        
        # Measure schemaless memory
        memory_before = self.measure_memory_usage()
        for segment in segments:
            from src.core.models import Episode, Podcast
            from datetime import datetime
            episode = Episode(id="ep1", podcast_id="pod1", title="Test Episode", publication_date=datetime.now())
            podcast = Podcast(id="pod1", title="Test Podcast")
            schemaless_provider.process_segment_schemaless(segment, episode, podcast)
        memory_schemaless = self.measure_memory_usage() - memory_before
        
        # Store results
        self.results.append(BenchmarkResult(
            operation="batch_memory_usage",
            schema_type="fixed",
            avg_time=0,
            min_time=0,
            max_time=0,
            std_dev=0,
            memory_usage_mb=memory_fixed,
            token_count=0,
            iterations=len(segments)
        ))
        
        self.results.append(BenchmarkResult(
            operation="batch_memory_usage",
            schema_type="schemaless",
            avg_time=0,
            min_time=0,
            max_time=0,
            std_dev=0,
            memory_usage_mb=memory_schemaless,
            token_count=0,
            iterations=len(segments)
        ))

    async def benchmark_llm_token_consumption(self):
        """Benchmark LLM token consumption."""
        _, schemaless_provider = self.setup_providers()
        
        # Different segment complexities
        segments = [
            # Simple segment
            Segment(
                id="simple",
                episode_id="ep1",
                start_time=0.0,
                end_time=30.0,
                text="AI is changing the world.",
                speaker="Host"
            ),
            # Medium complexity
            Segment(
                id="medium",
                episode_id="ep1",
                start_time=30.0,
                end_time=60.0,
                text="OpenAI's GPT-4 and Google's Gemini are competing in the large language model space. "
                     "Both companies are investing billions in AI research.",
                speaker="Host"
            ),
            # High complexity
            Segment(
                id="complex",
                episode_id="ep1",
                start_time=60.0,
                end_time=90.0,
                text="The intersection of quantum computing and artificial intelligence presents unique opportunities. "
                     "Companies like IBM, Google, and Microsoft are developing quantum algorithms that could "
                     "revolutionize machine learning. Dr. John Preskill from Caltech says, 'Quantum supremacy "
                     "in practical AI applications is still years away, but the potential is enormous.'",
                speaker="Guest"
            )
        ]
        
        for segment in segments:
            # Mock token counting
            self.mock_llm.token_count = len(segment.text.split()) * 2  # Rough estimate
            
            from src.core.models import Episode, Podcast
            from datetime import datetime
            episode = Episode(id="ep1", podcast_id="pod1", title="Test Episode", publication_date=datetime.now())
            podcast = Podcast(id="pod1", title="Test Podcast")
            
            result = await self.benchmark_operation(
                f"token_consumption_{segment.id}",
                "schemaless",
                lambda: schemaless_provider.process_segment_schemaless(segment, episode, podcast),
                iterations=5
            )
            self.results.append(result)

    async def benchmark_database_write_performance(self):
        """Benchmark database write performance."""
        fixed_provider, schemaless_provider = self.setup_providers()
        
        # Create test data
        nodes = [
            {"name": f"Entity{i}", "type": "TestType", "properties": {"prop1": f"value{i}"}}
            for i in range(100)
        ]
        
        relationships = [
            {"start": f"Entity{i}", "end": f"Entity{i+1}", "type": "RELATES_TO"}
            for i in range(99)
        ]
        
        # Benchmark fixed schema writes
        async def fixed_write():
            with fixed_provider.driver.session() as session:
                for node in nodes:
                    session.run("CREATE (n:Entity {name: $name})", name=node["name"])
        
        fixed_result = await self.benchmark_operation(
            "database_writes",
            "fixed",
            fixed_write,
            iterations=5
        )
        self.results.append(fixed_result)
        
        # Benchmark schemaless writes
        async def schemaless_write():
            for node in nodes:
                schemaless_provider.create_node(node["type"], node)
        
        schemaless_result = await self.benchmark_operation(
            "database_writes",
            "schemaless",
            schemaless_write,
            iterations=5
        )
        self.results.append(schemaless_result)

    async def benchmark_entity_resolution_speed(self):
        """Benchmark entity resolution performance."""
        _, schemaless_provider = self.setup_providers()
        
        # Create entities with variations
        entities = []
        for i in range(50):
            entities.extend([
                {"name": f"Entity {i}", "type": "Type1"},
                {"name": f"entity {i}", "type": "Type1"},  # Case variation
                {"name": f"Entity{i}", "type": "Type1"},   # Space variation
            ])
        
        async def resolution_operation():
            return schemaless_provider.entity_resolver.resolve_entities(entities)
        
        result = await self.benchmark_operation(
            "entity_resolution",
            "schemaless",
            resolution_operation,
            iterations=10
        )
        self.results.append(result)

    def create_performance_regression_tests(self):
        """Create regression tests based on benchmarks."""
        regression_tests = []
        
        for result in self.results:
            # Define performance thresholds (20% tolerance)
            threshold = result.avg_time * 1.2
            
            regression_tests.append({
                "operation": result.operation,
                "schema_type": result.schema_type,
                "max_allowed_time": threshold,
                "baseline_time": result.avg_time,
                "baseline_memory": result.memory_usage_mb
            })
        
        return regression_tests

    def generate_report(self) -> str:
        """Generate performance comparison report."""
        report = "# Schemaless Performance Benchmark Report\n\n"
        
        # Group results by operation
        operations = {}
        for result in self.results:
            if result.operation not in operations:
                operations[result.operation] = {}
            operations[result.operation][result.schema_type] = result
        
        # Compare performance
        for operation, schemas in operations.items():
            report += f"\n## {operation.replace('_', ' ').title()}\n"
            
            if "fixed" in schemas and "schemaless" in schemas:
                fixed = schemas["fixed"]
                schemaless = schemas["schemaless"]
                
                performance_diff = ((schemaless.avg_time - fixed.avg_time) / fixed.avg_time) * 100
                memory_diff = ((schemaless.memory_usage_mb - fixed.memory_usage_mb) / fixed.memory_usage_mb) * 100 if fixed.memory_usage_mb > 0 else 0
                
                report += f"- Fixed Schema: {fixed.avg_time:.3f}s (±{fixed.std_dev:.3f}s)\n"
                report += f"- Schemaless: {schemaless.avg_time:.3f}s (±{schemaless.std_dev:.3f}s)\n"
                report += f"- Performance Difference: {performance_diff:+.1f}%\n"
                report += f"- Memory Difference: {memory_diff:+.1f}%\n"
                
                if schemaless.token_count > 0:
                    report += f"- Token Usage: {schemaless.token_count} tokens\n"
            else:
                # Single schema type result
                for schema_type, result in schemas.items():
                    report += f"- {schema_type.title()}: {result.avg_time:.3f}s (±{result.std_dev:.3f}s)\n"
                    if result.memory_usage_mb > 0:
                        report += f"- Memory Usage: {result.memory_usage_mb:.2f} MB\n"
                    if result.token_count > 0:
                        report += f"- Token Usage: {result.token_count} tokens\n"
        
        # Optimization opportunities
        report += "\n## Optimization Opportunities\n"
        
        slow_operations = [r for r in self.results if r.avg_time > 1.0]
        if slow_operations:
            report += "\n### Slow Operations (>1s):\n"
            for op in sorted(slow_operations, key=lambda x: x.avg_time, reverse=True):
                report += f"- {op.operation} ({op.schema_type}): {op.avg_time:.3f}s\n"
        
        high_memory = [r for r in self.results if r.memory_usage_mb > 50]
        if high_memory:
            report += "\n### High Memory Usage (>50MB):\n"
            for op in sorted(high_memory, key=lambda x: x.memory_usage_mb, reverse=True):
                report += f"- {op.operation} ({op.schema_type}): {op.memory_usage_mb:.2f} MB\n"
        
        return report


async def run_benchmarks():
    """Run all performance benchmarks."""
    benchmark = SchemalessPerformanceBenchmark()
    
    print("Running performance benchmarks...")
    
    # Run all benchmarks
    await benchmark.benchmark_segment_processing()
    await benchmark.benchmark_memory_usage()
    await benchmark.benchmark_llm_token_consumption()
    await benchmark.benchmark_database_write_performance()
    await benchmark.benchmark_entity_resolution_speed()
    
    # Generate report
    report = benchmark.generate_report()
    print(report)
    
    # Save report
    with open("benchmark_results.md", "w") as f:
        f.write(report)
    
    # Create regression tests
    regression_tests = benchmark.create_performance_regression_tests()
    print(f"\nCreated {len(regression_tests)} regression tests")
    
    return benchmark.results


if __name__ == "__main__":
    asyncio.run(run_benchmarks())