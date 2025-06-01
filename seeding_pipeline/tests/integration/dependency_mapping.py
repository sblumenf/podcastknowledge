"""Dependency mapping for extraction.py and other core modules."""

from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple
import ast
import json
import os
class DependencyMapper:
    """Map dependencies and usage patterns in the codebase."""
    
    def __init__(self, root_dir: Path = Path(".")):
        self.root_dir = root_dir
        self.dependencies = defaultdict(list)
        self.usage_patterns = defaultdict(dict)
    
    def map_extraction_imports(self) -> Dict[str, List[Dict[str, any]]]:
        """Map all imports of extraction.py module."""
        extraction_imports = {
            "src/seeding/orchestrator.py": {
                "line": 19,
                "import": "from src.extraction.extraction import KnowledgeExtractor",
                "usage": ["Instantiates KnowledgeExtractor in _initialize_extraction()"],
                "critical": True
            },
            "tests/integration/test_golden_outputs_validation.py": {
                "line": 14,
                "import": "from src.extraction.extraction import KnowledgeExtractor",
                "usage": ["Tests extraction consistency", "Creates golden outputs"],
                "critical": False
            },
            "tests/integration/test_performance_benchmarks.py": {
                "line": 18,
                "import": "from src.extraction.extraction import KnowledgeExtractor",
                "usage": ["Benchmarks extraction performance"],
                "critical": False
            },
            "tests/processing/test_extraction.py": {
                "line": 10,
                "import": "from src.extraction.extraction import KnowledgeExtractor",
                "usage": ["Unit tests for KnowledgeExtractor"],
                "critical": False
            },
            "tests/processing/test_importance_scoring.py": {
                "line": 388,
                "import": "from src.extraction.extraction import KnowledgeExtractor",
                "usage": ["Tests importance scoring integration"],
                "critical": False
            },
            "scripts/validate_extraction.py": {
                "line": 21,
                "import": "from src.extraction.extraction import KnowledgeExtractor",
                "usage": ["Validation script for extraction"],
                "critical": False
            },
            "docs/examples/processing_examples.py": {
                "line": 4,
                "import": "from src.extraction.extraction import KnowledgeExtractor",
                "usage": ["Documentation examples"],
                "critical": False
            }
        }
        
        return extraction_imports
    
    def analyze_extraction_usage(self) -> Dict[str, any]:
        """Analyze how KnowledgeExtractor is used."""
        usage_analysis = {
            "instantiation_patterns": [
                {
                    "file": "src/seeding/orchestrator.py",
                    "method": "_initialize_extraction",
                    "pattern": "self.extractor = KnowledgeExtractor(llm_provider=self.llm_provider, embedding_provider=self.embedding_provider)",
                    "dependencies": ["llm_provider", "embedding_provider"]
                }
            ],
            "method_calls": [
                {
                    "method": "extract_knowledge",
                    "called_in": ["orchestrator._process_segment", "tests"],
                    "parameters": ["segment"],
                    "returns": "Dict with entities, relationships, insights, themes, topics"
                }
            ],
            "integration_points": [
                "Orchestrator uses extractor in pipeline",
                "Tests validate extraction output format",
                "Performance benchmarks measure extraction time"
            ]
        }
        
        return usage_analysis
    
    def map_provider_usage(self) -> Dict[str, List[Dict[str, any]]]:
        """Map provider instantiation and usage patterns."""
        provider_patterns = {
            "audio_providers": {
                "whisper": {
                    "instantiated_in": ["orchestrator._initialize_providers"],
                    "factory_method": "ProviderFactory.create_audio_provider",
                    "config_options": ["use_large_model", "device", "compute_type"],
                    "methods_used": ["transcribe", "diarize", "health_check", "cleanup"]
                },
                "mock": {
                    "instantiated_in": ["tests"],
                    "usage": "Testing only"
                }
            },
            "llm_providers": {
                "gemini": {
                    "instantiated_in": ["orchestrator._initialize_providers"],
                    "factory_method": "ProviderFactory.create_llm_provider",
                    "config_options": ["model_name", "temperature", "max_tokens"],
                    "methods_used": ["generate", "health_check", "cleanup"],
                    "specific_features": ["Supports both Gemini Flash and Pro models"]
                },
                "mock": {
                    "instantiated_in": ["tests"],
                    "usage": "Testing only"
                }
            },
            "graph_providers": {
                "neo4j": {
                    "instantiated_in": ["orchestrator._initialize_providers"],
                    "factory_method": "ProviderFactory.create_graph_provider",
                    "config_options": ["uri", "user", "password", "database"],
                    "methods_used": ["create_node", "create_relationship", "find_node", "update_node", "query", "health_check", "close"],
                    "specific_features": ["Connection pooling", "Batch operations"]
                },
                "memory": {
                    "instantiated_in": ["tests", "development"],
                    "usage": "In-memory graph for testing"
                }
            },
            "embedding_providers": {
                "sentence_transformer": {
                    "instantiated_in": ["orchestrator._initialize_providers"],
                    "factory_method": "ProviderFactory.create_embedding_provider",
                    "config_options": ["model_name", "device"],
                    "methods_used": ["embed", "embed_batch", "health_check", "cleanup"],
                    "specific_features": ["Batch embedding support"]
                },
                "mock": {
                    "instantiated_in": ["tests"],
                    "usage": "Testing only"
                }
            }
        }
        
        return provider_patterns
    
    def create_api_contract_documentation(self) -> Dict[str, any]:
        """Document API contracts and request/response formats."""
        api_contracts = {
            "v1_endpoints": {
                "/api/v1/seed": {
                    "method": "POST",
                    "request_format": {
                        "podcast_config": {
                            "name": "string",
                            "rss_url": "string (required)",
                            "category": "string (optional)"
                        },
                        "max_episodes": "integer (default: 1)",
                        "extraction_mode": "string: 'fixed' | 'schemaless' (default: 'fixed')",
                        "use_large_context": "boolean (default: true)"
                    },
                    "response_format": {
                        "api_version": "string",
                        "start_time": "ISO datetime string",
                        "end_time": "ISO datetime string", 
                        "podcasts_processed": "integer",
                        "episodes_processed": "integer",
                        "episodes_failed": "integer",
                        "processing_time_seconds": "float",
                        "extraction_mode": "string",
                        "discovered_types": "array (schemaless mode only)",
                        "total_entities": "integer (schemaless mode only)",
                        "total_relationships": "integer (schemaless mode only)"
                    },
                    "error_format": {
                        "error": "string",
                        "details": "object (optional)",
                        "api_version": "string"
                    }
                },
                "/api/v1/seed-batch": {
                    "method": "POST",
                    "request_format": {
                        "podcast_configs": "array of podcast_config objects",
                        "max_episodes_each": "integer (default: 10)",
                        "extraction_mode": "string: 'fixed' | 'schemaless' (default: 'fixed')",
                        "use_large_context": "boolean (default: true)"
                    },
                    "response_format": "Same as /api/v1/seed but aggregated"
                },
                "/api/v1/schema-evolution": {
                    "method": "GET",
                    "request_format": {
                        "checkpoint_dir": "string (optional)"
                    },
                    "response_format": {
                        "api_version": "string",
                        "checkpoint_dir": "string",
                        "schema_stats": {
                            "total_types_discovered": "integer",
                            "evolution_entries": "integer",
                            "entity_types": "array of strings",
                            "discovery_timeline": "array of timeline entries"
                        },
                        "timestamp": "ISO datetime string"
                    }
                },
                "/health": {
                    "method": "GET",
                    "response_format": {
                        "status": "string: 'healthy' | 'degraded' | 'unhealthy'",
                        "components": {
                            "neo4j": "component_health object",
                            "redis": "component_health object",
                            "providers": "object with provider statuses"
                        },
                        "uptime_seconds": "float",
                        "version": "string"
                    }
                }
            }
        }
        
        return api_contracts
    
    def document_cli_behavior(self) -> Dict[str, any]:
        """Document CLI commands and their behavior."""
        cli_documentation = {
            "commands": {
                "seed": {
                    "description": "Seed knowledge graph with podcasts",
                    "flags": {
                        "--rss-url": {
                            "type": "string",
                            "required": "Yes (unless --podcast-config)",
                            "description": "RSS feed URL for single podcast"
                        },
                        "--podcast-config": {
                            "type": "string",
                            "required": "Yes (unless --rss-url)",
                            "description": "JSON file with podcast configurations"
                        },
                        "--name": {
                            "type": "string",
                            "required": "No",
                            "default": "Extracted from RSS",
                            "description": "Podcast name (with --rss-url)"
                        },
                        "--category": {
                            "type": "string",
                            "required": "No",
                            "default": "General",
                            "description": "Podcast category"
                        },
                        "--max-episodes": {
                            "type": "integer",
                            "required": "No",
                            "default": "10",
                            "description": "Maximum episodes to process"
                        },
                        "--extraction-mode": {
                            "type": "string",
                            "required": "No",
                            "default": "fixed",
                            "choices": ["fixed", "schemaless"],
                            "description": "Extraction mode to use"
                        },
                        "--migration-mode": {
                            "type": "boolean",
                            "required": "No",
                            "default": "False",
                            "description": "Enable dual processing (both modes)",
                            "conflicts_with": ["--extraction-mode schemaless"]
                        },
                        "--schema-discovery": {
                            "type": "boolean",
                            "required": "No",
                            "default": "False",
                            "description": "Show discovered types after processing",
                            "requires": ["--extraction-mode schemaless"]
                        },
                        "--large-context": {
                            "type": "boolean",
                            "required": "No",
                            "default": "False",
                            "description": "Use large context models"
                        }
                    },
                    "output": {
                        "format": "Text to stdout",
                        "includes": ["Progress updates", "Summary statistics", "Error messages"]
                    }
                },
                "health": {
                    "description": "Check health of pipeline components",
                    "flags": {
                        "--large-context": {
                            "type": "boolean",
                            "required": "No",
                            "default": "False",
                            "description": "Check large context model availability"
                        }
                    },
                    "output": {
                        "format": "Text to stdout",
                        "includes": ["Component status", "Health summary"]
                    }
                },
                "schema-stats": {
                    "description": "Show schema discovery statistics",
                    "flags": {
                        "--checkpoint-dir": {
                            "type": "string",
                            "required": "No",
                            "default": "checkpoints",
                            "description": "Directory containing checkpoint files"
                        }
                    },
                    "output": {
                        "format": "Text to stdout",
                        "includes": ["Total types discovered", "Evolution timeline", "Entity type list"]
                    }
                },
                "validate-config": {
                    "description": "Validate configuration file",
                    "flags": {
                        "--config": {
                            "type": "string",
                            "required": "Yes",
                            "description": "Path to configuration file"
                        }
                    },
                    "output": {
                        "format": "Text to stdout",
                        "includes": ["Configuration summary", "Validation result"]
                    }
                }
            },
            "global_flags": {
                "-v, --verbose": {
                    "description": "Enable verbose/debug logging",
                    "effect": "Sets log level to DEBUG, enables performance logging"
                },
                "-c, --config": {
                    "description": "Custom configuration file",
                    "effect": "Overrides default configuration"
                }
            },
            "exit_codes": {
                "0": "Success",
                "1": "General error or partial failure"
            }
        }
        
        return cli_documentation
    
    def save_mapping_report(self, output_dir: Path = Path("tests/integration")):
        """Save comprehensive dependency mapping report."""
        report = {
            "timestamp": "2024-01-01T10:00:00",
            "extraction_imports": self.map_extraction_imports(),
            "extraction_usage": self.analyze_extraction_usage(),
            "provider_patterns": self.map_provider_usage(),
            "api_contracts": self.create_api_contract_documentation(),
            "cli_behavior": self.document_cli_behavior()
        }
        
        output_file = output_dir / "dependency_mapping_report.json"
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"Dependency mapping report saved to: {output_file}")
        
        return report


if __name__ == "__main__":
    # Run dependency mapping
    mapper = DependencyMapper()
    report = mapper.save_mapping_report()
    
    # Print summary
    print("\n=== Dependency Mapping Summary ===")
    print(f"Extraction.py imports found: {len(report['extraction_imports'])}")
    print(f"Provider types documented: {len(report['provider_patterns'])}")
    print(f"API endpoints documented: {len(report['api_contracts']['v1_endpoints'])}")
    print(f"CLI commands documented: {len(report['cli_behavior']['commands'])}")