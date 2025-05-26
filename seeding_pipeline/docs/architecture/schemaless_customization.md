# Schemaless System Customization Guide

This document provides common customization scenarios for the schemaless knowledge graph extraction system.

## Common Customization Scenarios

### 1. Domain-Specific Entity Recognition

**Scenario**: Enhance extraction for medical podcasts with specialized terminology.

```python
# Custom preprocessor for medical domain
class MedicalPreprocessor(SegmentPreprocessor):
    def __init__(self):
        super().__init__()
        self.medical_terms = load_medical_dictionary()
    
    def prepare_segment_text(self, segment, episode_metadata):
        # Standard preprocessing
        result = super().prepare_segment_text(segment, episode_metadata)
        
        # Add medical context
        enriched_text = result['enriched_text']
        
        # Highlight medical terms for better extraction
        for term in self.medical_terms:
            if term.lower() in enriched_text.lower():
                enriched_text = enriched_text.replace(
                    term,
                    f"[MEDICAL_TERM: {term}]"
                )
        
        result['enriched_text'] = enriched_text
        result['metrics']['medical_terms_found'] = len(found_terms)
        return result
```

### 2. Custom Entity Resolution Rules

**Scenario**: Handle company name variations and mergers.

```python
# Custom entity resolver for business podcasts
class BusinessEntityResolver(SchemalessEntityResolver):
    def __init__(self):
        super().__init__()
        self.company_aliases = {
            "Google": ["Alphabet", "Alphabet Inc.", "GOOGL"],
            "Facebook": ["Meta", "Meta Platforms", "FB"],
            "Amazon": ["AWS", "Amazon Web Services", "AMZN"]
        }
    
    def resolve_entities(self, entities):
        # Standard resolution
        resolved = super().resolve_entities(entities)
        
        # Apply business-specific rules
        for entity in resolved:
            if entity.get('type') == 'Organization':
                name = entity.get('name', '')
                
                # Check for known aliases
                for canonical, aliases in self.company_aliases.items():
                    if name in aliases:
                        entity['name'] = canonical
                        entity['aliases'] = entity.get('aliases', []) + [name]
                        break
        
        return resolved
```

### 3. Quote Extraction with Custom Scoring

**Scenario**: Prioritize quotes based on domain-specific importance.

```python
# Custom quote extractor for educational podcasts
class EducationalQuoteExtractor(SchemalessQuoteExtractor):
    def __init__(self):
        super().__init__()
        self.educational_keywords = [
            'learn', 'teach', 'understand', 'concept',
            'theory', 'practice', 'method', 'technique'
        ]
    
    def calculate_importance(self, quote_text, context):
        # Base importance score
        base_score = super().calculate_importance(quote_text, context)
        
        # Boost for educational content
        educational_boost = 0
        for keyword in self.educational_keywords:
            if keyword in quote_text.lower():
                educational_boost += 0.1
        
        # Boost for quotes from educators
        if context.get('speaker_role') == 'educator':
            educational_boost += 0.2
        
        return min(base_score + educational_boost, 1.0)
```

### 4. Property Constraints and Validation

**Scenario**: Enforce property constraints for data quality.

```python
# Property validation configuration
class PropertyValidator:
    def __init__(self):
        self.property_rules = {
            'Person': {
                'age': lambda x: isinstance(x, int) and 0 < x < 150,
                'email': lambda x: '@' in x and '.' in x,
                'twitter_handle': lambda x: x.startswith('@')
            },
            'Company': {
                'founded_year': lambda x: isinstance(x, int) and 1800 < x < 2030,
                'employee_count': lambda x: isinstance(x, int) and x > 0,
                'website': lambda x: x.startswith(('http://', 'https://'))
            }
        }
    
    def validate_entity(self, entity):
        entity_type = entity.get('type')
        if entity_type not in self.property_rules:
            return entity
        
        rules = self.property_rules[entity_type]
        for prop, validator in rules.items():
            if prop in entity:
                try:
                    if not validator(entity[prop]):
                        # Log invalid property
                        logger.warning(f"Invalid {prop} for {entity_type}: {entity[prop]}")
                        # Remove or fix invalid property
                        del entity[prop]
                except Exception:
                    del entity[prop]
        
        return entity
```

### 5. Multi-Language Support

**Scenario**: Process podcasts in multiple languages.

```python
# Multi-language preprocessor
class MultilingualPreprocessor(SegmentPreprocessor):
    def __init__(self):
        super().__init__()
        self.language_detector = LanguageDetector()
        self.translators = {
            'es': SpanishTranslator(),
            'fr': FrenchTranslator(),
            'de': GermanTranslator()
        }
    
    def prepare_segment_text(self, segment, episode_metadata):
        # Detect language
        language = self.language_detector.detect(segment.text)
        
        if language != 'en':
            # Translate to English for LLM processing
            translator = self.translators.get(language)
            if translator:
                translated_text = translator.translate(segment.text)
                # Keep original for reference
                segment.original_text = segment.text
                segment.text = translated_text
                segment.language = language
        
        # Continue with standard preprocessing
        return super().prepare_segment_text(segment, episode_metadata)
```

### 6. Streaming Processing for Live Podcasts

**Scenario**: Process live podcast streams in real-time.

```python
# Streaming processor
class StreamingSchemalessProcessor:
    def __init__(self, provider):
        self.provider = provider
        self.buffer = []
        self.buffer_duration = 60.0  # seconds
        
    async def process_audio_chunk(self, audio_chunk, timestamp):
        # Add to buffer
        self.buffer.append({
            'audio': audio_chunk,
            'timestamp': timestamp
        })
        
        # Check if buffer is ready
        if self._buffer_duration() >= self.buffer_duration:
            # Create segment from buffer
            segment = self._create_segment_from_buffer()
            
            # Process immediately
            result = await self.provider.process_segment_schemaless(
                segment,
                self.episode,
                self.podcast
            )
            
            # Clear processed buffer
            self._clear_buffer()
            
            return result
        
        return None
```

### 7. Schema Evolution Tracking

**Scenario**: Monitor how the schema evolves over time.

```python
# Schema evolution tracker
class SchemaEvolutionTracker:
    def __init__(self, neo4j_driver):
        self.driver = neo4j_driver
        self.baseline_schema = None
        
    def capture_baseline(self):
        """Capture current schema as baseline."""
        with self.driver.session() as session:
            # Get entity types
            entity_types = session.run(
                "MATCH (n) WHERE exists(n._type) "
                "RETURN DISTINCT n._type as type, count(n) as count"
            ).values()
            
            # Get relationship types
            rel_types = session.run(
                "MATCH ()-[r]->() WHERE exists(r._type) "
                "RETURN DISTINCT r._type as type, count(r) as count"
            ).values()
            
            self.baseline_schema = {
                'entities': dict(entity_types),
                'relationships': dict(rel_types),
                'captured_at': datetime.now()
            }
    
    def detect_changes(self):
        """Detect schema changes since baseline."""
        current = self.capture_current_schema()
        
        changes = {
            'new_entity_types': set(current['entities']) - set(self.baseline_schema['entities']),
            'new_relationship_types': set(current['relationships']) - set(self.baseline_schema['relationships']),
            'removed_entity_types': set(self.baseline_schema['entities']) - set(current['entities']),
            'removed_relationship_types': set(self.baseline_schema['relationships']) - set(current['relationships'])
        }
        
        return changes
```

### 8. Component Performance Tuning

**Scenario**: Optimize component configuration based on performance metrics.

```python
# Auto-tuning configuration
class ComponentAutoTuner:
    def __init__(self):
        self.performance_history = []
        self.config_variations = {
            'batch_size': [5, 10, 20, 50],
            'confidence_threshold': [0.5, 0.6, 0.7, 0.8, 0.9],
            'max_properties': [20, 50, 100]
        }
    
    def tune_configuration(self, component_name):
        """Find optimal configuration for component."""
        best_config = None
        best_performance = float('inf')
        
        for batch_size in self.config_variations['batch_size']:
            for threshold in self.config_variations['confidence_threshold']:
                for max_props in self.config_variations['max_properties']:
                    config = {
                        'batch_size': batch_size,
                        'confidence_threshold': threshold,
                        'max_properties_per_node': max_props
                    }
                    
                    # Run benchmark
                    performance = self.benchmark_component(component_name, config)
                    
                    if performance['avg_time'] < best_performance:
                        best_performance = performance['avg_time']
                        best_config = config
        
        return best_config
```

## Integration Examples

### Using Custom Components

```python
# Initialize custom components
medical_preprocessor = MedicalPreprocessor()
business_resolver = BusinessEntityResolver()
edu_quote_extractor = EducationalQuoteExtractor()

# Create custom provider
provider = SchemalessNeo4jProvider(config)
provider.preprocessor = medical_preprocessor
provider.entity_resolver = business_resolver
provider.quote_extractor = edu_quote_extractor

# Process with customizations
result = provider.process_segment_schemaless(segment, episode, podcast)
```

### Configuration-Based Customization

```yaml
# config/custom_schemaless.yml
schemaless:
  components:
    preprocessor:
      class: "MedicalPreprocessor"
      config:
        dictionary_path: "data/medical_terms.txt"
        highlight_format: "[MEDICAL: {term}]"
    
    entity_resolver:
      class: "BusinessEntityResolver"
      config:
        alias_file: "data/company_aliases.json"
        fuzzy_threshold: 0.85
    
    quote_extractor:
      class: "EducationalQuoteExtractor"
      config:
        keyword_boost: 0.1
        speaker_role_boost: 0.2
```

## Best Practices

1. **Test Custom Components**: Always test with sample data before production
2. **Monitor Impact**: Use component tracking to verify improvements
3. **Document Rules**: Keep clear documentation of custom logic
4. **Version Components**: Track component versions for reproducibility
5. **Gradual Rollout**: Use feature flags to enable/disable customizations