#!/usr/bin/env python3
"""Real data test for VTT pipeline validation."""

import sys
import time
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.cli.cli import setup_logging_cli
from src.pipeline.enhanced_knowledge_pipeline import EnhancedKnowledgePipeline
from src.core.config import PipelineConfig
from src.monitoring import get_pipeline_metrics
from src.utils.health_check import get_health_checker
from src.storage import GraphStorageService
from src.utils.logging import get_logger, set_correlation_id, generate_correlation_id


class RealDataValidator:
    """Validates pipeline with real podcast data."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.metrics = get_pipeline_metrics()
        self.test_file = Path("test_data/hour_podcast_test.vtt")
        self.results = {
            'test_time': datetime.now().isoformat(),
            'file': str(self.test_file),
            'success': False,
            'performance': {},
            'extraction_quality': {},
            'errors': []
        }
        
    def validate_test_file(self) -> bool:
        """Ensure test file exists and is valid."""
        if not self.test_file.exists():
            self.results['errors'].append(f"Test file not found: {self.test_file}")
            return False
            
        # Check file size
        file_size = self.test_file.stat().st_size
        self.results['file_size_kb'] = file_size / 1024
        
        # Count lines to estimate duration
        with open(self.test_file, 'r') as f:
            lines = f.readlines()
            timestamp_lines = [l for l in lines if '-->' in l]
            self.results['caption_count'] = len(timestamp_lines)
            
        self.logger.info(f"Test file validated: {self.results['caption_count']} captions")
        return True
        
    def run_pipeline(self) -> Dict[str, Any]:
        """Run the pipeline on test data."""
        start_time = time.time()
        
        # Set correlation ID for tracking
        correlation_id = generate_correlation_id()
        set_correlation_id(correlation_id)
        
        try:
            # Initialize pipeline
            config = PipelineConfig()
            config.neo4j_uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
            config.neo4j_username = os.getenv('NEO4J_USER', 'neo4j')
            config.neo4j_password = os.getenv('NEO4J_PASSWORD', '')
            
            # Use real LLM for quality testing
            config.llm_provider = 'google'
            
            pipeline = EnhancedKnowledgePipeline(config)
            
            # Process the file
            self.logger.info("Starting pipeline processing")
            result = pipeline.process_vtt_file(str(self.test_file))
            
            processing_time = time.time() - start_time
            
            self.results['performance'] = {
                'total_time_seconds': processing_time,
                'time_per_caption': processing_time / self.results['caption_count'] if self.results['caption_count'] > 0 else 0,
                'correlation_id': correlation_id
            }
            
            self.results['pipeline_result'] = result
            self.results['success'] = True
            
            return result
            
        except Exception as e:
            self.logger.error(f"Pipeline processing failed: {e}", exc_info=True)
            self.results['errors'].append(f"Pipeline error: {str(e)}")
            self.results['success'] = False
            return {}
            
    def analyze_extraction_quality(self):
        """Analyze the quality of extracted entities and relationships."""
        if not self.results.get('success'):
            return
            
        # Expected entities based on transcript content
        expected_entities = {
            'people': ['Sarah Johnson', 'Dr. Michael Chen'],
            'organizations': ['TechCorp', 'Microsoft', 'Google', 'Netflix', 'Amazon', 'Facebook', 'Apple', 'IBM'],
            'technologies': ['LLM', 'AI', 'GPT-4', 'Claude', 'Gemini', 'GitHub Copilot', 'machine learning'],
            'concepts': ['prompt engineering', 'code generation', 'autonomous agents', 'technical debt']
        }
        
        # Query Neo4j for extracted entities
        try:
            storage = GraphStorageService(
                os.getenv('NEO4J_URI', 'bolt://localhost:7687'),
                os.getenv('NEO4J_USER', 'neo4j'),
                os.getenv('NEO4J_PASSWORD', '')
            )
            
            # Get all entities
            entities_query = """
            MATCH (e:Entity)
            RETURN e.name as name, e.type as type, count(*) as mentions
            ORDER BY mentions DESC
            """
            entities = storage.query(entities_query)
            
            # Get relationships
            relationships_query = """
            MATCH (e1:Entity)-[r]->(e2:Entity)
            RETURN e1.name as source, type(r) as rel_type, e2.name as target, count(*) as count
            ORDER BY count DESC
            LIMIT 20
            """
            relationships = storage.query(relationships_query)
            
            # Get quotes
            quotes_query = """
            MATCH (q:Quote)
            RETURN q.text as text, q.speaker as speaker
            LIMIT 10
            """
            quotes = storage.query(quotes_query)
            
            # Analyze results
            entity_names = {e['name'].lower() for e in entities}
            found_expected = {}
            
            for category, expected_list in expected_entities.items():
                found = [e for e in expected_list if e.lower() in entity_names]
                found_expected[category] = {
                    'expected': len(expected_list),
                    'found': len(found),
                    'accuracy': len(found) / len(expected_list) if expected_list else 0,
                    'found_entities': found
                }
            
            self.results['extraction_quality'] = {
                'total_entities': len(entities),
                'total_relationships': len(relationships),
                'total_quotes': len(quotes),
                'expected_entity_coverage': found_expected,
                'top_entities': entities[:10] if entities else [],
                'top_relationships': relationships[:10] if relationships else [],
                'sample_quotes': quotes[:5] if quotes else []
            }
            
            # Calculate overall accuracy
            total_expected = sum(len(v) for v in expected_entities.values())
            total_found = sum(f['found'] for f in found_expected.values())
            self.results['extraction_quality']['overall_accuracy'] = total_found / total_expected if total_expected > 0 else 0
            
        except Exception as e:
            self.logger.error(f"Failed to analyze extraction quality: {e}")
            self.results['errors'].append(f"Quality analysis error: {str(e)}")
            
    def check_performance_metrics(self):
        """Check if performance meets success criteria."""
        if not self.results.get('success'):
            return
            
        perf = self.results['performance']
        
        # Success criteria from plan
        criteria = {
            'processing_time_minutes': {
                'actual': perf['total_time_seconds'] / 60,
                'target': 10,  # Should process 1-hour podcast in <10 minutes
                'passed': perf['total_time_seconds'] / 60 < 10
            }
        }
        
        # Get memory usage from metrics
        current_metrics = self.metrics.get_current_metrics()
        memory_mb = current_metrics['memory']['max_mb']
        
        criteria['memory_usage_gb'] = {
            'actual': memory_mb / 1024,
            'target': 2,  # <2GB per file
            'passed': memory_mb < 2048
        }
        
        # Check database query time
        db_latency = current_metrics['database']['average_latency_ms']
        criteria['db_query_ms'] = {
            'actual': db_latency,
            'target': 100,  # <100ms average
            'passed': db_latency < 100
        }
        
        self.results['performance_criteria'] = criteria
        self.results['all_criteria_passed'] = all(c['passed'] for c in criteria.values())
        
    def generate_report(self) -> str:
        """Generate validation report."""
        report_lines = [
            "=" * 60,
            "Real Data Test Validation Report",
            "=" * 60,
            f"Test Date: {self.results['test_time']}",
            f"Test File: {self.results['file']}",
            f"File Size: {self.results.get('file_size_kb', 0):.1f} KB",
            f"Caption Count: {self.results.get('caption_count', 0)}",
            "",
            "Performance Results:",
            "-" * 40
        ]
        
        if self.results.get('performance'):
            perf = self.results['performance']
            report_lines.extend([
                f"Total Processing Time: {perf['total_time_seconds']:.2f} seconds",
                f"Time per Caption: {perf['time_per_caption']*1000:.1f} ms",
                f"Correlation ID: {perf['correlation_id']}"
            ])
        
        if self.results.get('performance_criteria'):
            report_lines.extend([
                "",
                "Performance Criteria:",
                "-" * 40
            ])
            for name, criteria in self.results['performance_criteria'].items():
                status = "✅" if criteria['passed'] else "❌"
                report_lines.append(
                    f"{status} {name}: {criteria['actual']:.2f} (target: <{criteria['target']})"
                )
        
        if self.results.get('extraction_quality'):
            quality = self.results['extraction_quality']
            report_lines.extend([
                "",
                "Extraction Quality:",
                "-" * 40,
                f"Total Entities: {quality['total_entities']}",
                f"Total Relationships: {quality['total_relationships']}",
                f"Total Quotes: {quality['total_quotes']}",
                f"Overall Accuracy: {quality['overall_accuracy']*100:.1f}%",
                "",
                "Entity Coverage:"
            ])
            
            for category, coverage in quality['expected_entity_coverage'].items():
                report_lines.append(
                    f"  {category}: {coverage['found']}/{coverage['expected']} "
                    f"({coverage['accuracy']*100:.0f}%)"
                )
            
            if quality.get('top_entities'):
                report_lines.extend([
                    "",
                    "Top Entities:",
                ])
                for entity in quality['top_entities'][:5]:
                    report_lines.append(f"  - {entity['name']} ({entity['type']}): {entity['mentions']} mentions")
            
            if quality.get('sample_quotes'):
                report_lines.extend([
                    "",
                    "Sample Quotes:",
                ])
                for quote in quality['sample_quotes'][:3]:
                    text = quote['text'][:100] + "..." if len(quote['text']) > 100 else quote['text']
                    report_lines.append(f"  - {quote['speaker']}: \"{text}\"")
        
        if self.results.get('errors'):
            report_lines.extend([
                "",
                "Errors:",
                "-" * 40
            ])
            for error in self.results['errors']:
                report_lines.append(f"  ❌ {error}")
        
        report_lines.extend([
            "",
            "Overall Result:",
            "-" * 40,
            f"Success: {'✅ YES' if self.results['success'] else '❌ NO'}",
            f"All Criteria Passed: {'✅ YES' if self.results.get('all_criteria_passed') else '❌ NO'}"
        ])
        
        return "\n".join(report_lines)
        
    def save_results(self):
        """Save detailed results to file."""
        output_file = Path("test_data/real_data_test_results.json")
        output_file.parent.mkdir(exist_ok=True)
        
        with open(output_file, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        
        self.logger.info(f"Detailed results saved to: {output_file}")
        

def main():
    """Run real data validation test."""
    # Set up logging
    setup_logging_cli(verbose=True, log_file="logs/real_data_test.log")
    
    print("\n" + "=" * 60)
    print("Starting Real Data Validation Test")
    print("=" * 60 + "\n")
    
    # Check system health first
    print("Checking system health...")
    health_checker = get_health_checker()
    health_data = health_checker.check_all()
    
    if health_data['status'] == 'unhealthy':
        print("❌ System health check failed. Please fix issues before running test.")
        print(health_checker.get_cli_summary())
        return 1
    
    print("✅ System health check passed\n")
    
    # Run validation
    validator = RealDataValidator()
    
    # Validate test file
    if not validator.validate_test_file():
        print("❌ Test file validation failed")
        return 1
    
    # Run pipeline
    print("Running pipeline on test data...")
    validator.run_pipeline()
    
    # Analyze results
    print("Analyzing extraction quality...")
    validator.analyze_extraction_quality()
    
    # Check performance
    print("Checking performance metrics...")
    validator.check_performance_metrics()
    
    # Generate and display report
    report = validator.generate_report()
    print("\n" + report)
    
    # Save results
    validator.save_results()
    
    # Export metrics
    metrics = get_pipeline_metrics()
    metrics_file = metrics.export_metrics("test_data/real_data_test_metrics.json")
    print(f"\nMetrics exported to: {metrics_file}")
    
    return 0 if validator.results['success'] and validator.results.get('all_criteria_passed') else 1


if __name__ == "__main__":
    sys.exit(main())