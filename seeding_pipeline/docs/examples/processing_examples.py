"""Examples for using processing modules in the Podcast Knowledge Graph Pipeline."""

from src.processing.segmentation import EnhancedPodcastSegmenter
from src.processing.extraction import KnowledgeExtractor
from src.processing.entity_resolution import EntityResolver, VectorEntityMatcher
from src.processing.metrics import MetricsCalculator
from src.processing.graph_analysis import GraphAnalyzer
from src.processing.complexity_analysis import ComplexityAnalyzer


def example_segmentation():
    """Example: Segmenting podcast transcripts."""
    print("=== Segmentation Example ===")
    
    # Initialize segmenter
    segmenter = EnhancedPodcastSegmenter(
        min_segment_length=100,
        max_segment_length=1000,
        similarity_threshold=0.7
    )
    
    # Example transcript
    transcript = """
    Host: Welcome to Tech Talks. Today we're discussing artificial intelligence.
    
    Guest: Thanks for having me. AI is truly transforming every industry.
    
    Host: Let's start with healthcare. How is AI impacting medical diagnosis?
    
    Guest: AI can analyze medical images faster than human doctors. It's detecting 
    cancers earlier and more accurately. Machine learning models are trained on 
    millions of X-rays and MRIs.
    
    Host: That's fascinating. What about the ethical concerns?
    
    Guest: Great question. We need to ensure AI systems are transparent and unbiased.
    Patient privacy is also crucial when handling medical data.
    
    Host: Moving on to education, how is AI changing the way we learn?
    
    Guest: Personalized learning is the key. AI can adapt to each student's pace
    and learning style, providing customized content and exercises.
    """
    
    # Segment the transcript
    segments = segmenter.segment_transcript(transcript)
    
    print(f"Created {len(segments)} segments:")
    for i, segment in enumerate(segments):
        print(f"\nSegment {i+1}:")
        print(f"  Text: {segment['text'][:100]}...")
        print(f"  Start: {segment['start_time']}")
        print(f"  End: {segment['end_time']}")
        print(f"  Speaker: {segment.get('speaker', 'Unknown')}")
        print(f"  Topic: {segment.get('topic', 'General')}")
    
    # With speaker diarization
    diarization_segments = [
        {"speaker": "Host", "start": 0, "end": 5},
        {"speaker": "Guest", "start": 5, "end": 10},
        {"speaker": "Host", "start": 10, "end": 15},
        {"speaker": "Guest", "start": 15, "end": 30},
    ]
    
    aligned_segments = segmenter.align_with_diarization(
        segments, diarization_segments
    )
    
    return aligned_segments


def example_knowledge_extraction():
    """Example: Extracting knowledge from segments."""
    print("\n=== Knowledge Extraction Example ===")
    
    from src.providers.llm.gemini import GeminiProvider
    
    # Initialize extractor with LLM provider
    llm_provider = GeminiProvider(api_key="your-key", model_name="gemini-1.5-pro")
    extractor = KnowledgeExtractor(llm_provider)
    
    # Example segment
    segment_text = """
    AI is revolutionizing healthcare through several key applications:
    1. Medical imaging analysis - detecting diseases earlier
    2. Drug discovery - reducing development time from 10 years to 2-3 years
    3. Personalized treatment plans based on genetic data
    
    Companies like DeepMind and IBM Watson are leading this transformation.
    However, we must address privacy concerns and ensure equitable access.
    """
    
    # Extract insights
    insights = extractor.extract_insights(segment_text)
    print(f"Extracted {len(insights)} insights:")
    for insight in insights:
        print(f"  - {insight['text']} (confidence: {insight['confidence']:.2f})")
    
    # Extract entities
    entities = extractor.extract_entities(segment_text)
    print(f"\nExtracted {len(entities)} entities:")
    for entity in entities:
        print(f"  - {entity['name']} ({entity['type']})")
    
    # Extract quotes
    quotes = extractor.extract_quotes(segment_text)
    print(f"\nExtracted {len(quotes)} quotes:")
    for quote in quotes:
        print(f"  - \"{quote['text'][:50]}...\" - {quote.get('speaker', 'Unknown')}")
    
    # Extract relationships
    relationships = extractor.extract_relationships(segment_text)
    print(f"\nExtracted {len(relationships)} relationships:")
    for rel in relationships:
        print(f"  - {rel['source']} --[{rel['type']}]--> {rel['target']}")
    
    return {
        "insights": insights,
        "entities": entities,
        "quotes": quotes,
        "relationships": relationships
    }


def example_entity_resolution():
    """Example: Resolving and matching entities."""
    print("\n=== Entity Resolution Example ===")
    
    from src.providers.embeddings.sentence_transformer import SentenceTransformerEmbeddingProvider
    
    # Initialize entity resolver
    embedding_provider = SentenceTransformerEmbeddingProvider()
    entity_resolver = EntityResolver(embedding_provider)
    
    # Example entities from different segments
    entities_batch_1 = [
        {"name": "AI", "type": "TECHNOLOGY"},
        {"name": "DeepMind", "type": "ORGANIZATION"},
        {"name": "Dr. Smith", "type": "PERSON"}
    ]
    
    entities_batch_2 = [
        {"name": "Artificial Intelligence", "type": "TECHNOLOGY"},
        {"name": "Deep Mind", "type": "ORGANIZATION"},
        {"name": "Doctor Smith", "type": "PERSON"},
        {"name": "IBM Watson", "type": "ORGANIZATION"}
    ]
    
    # Resolve entities
    resolved_entities = entity_resolver.resolve_entities(
        entities_batch_1 + entities_batch_2
    )
    
    print(f"Resolved {len(resolved_entities)} unique entities:")
    for entity in resolved_entities:
        print(f"  - {entity['canonical_name']} ({entity['type']})")
        if len(entity.get('aliases', [])) > 1:
            print(f"    Aliases: {', '.join(entity['aliases'])}")
    
    # Find similar entities
    vector_matcher = VectorEntityMatcher(embedding_provider)
    
    query_entity = "Artificial Intel"
    matches = vector_matcher.find_similar(
        query_entity,
        [e['canonical_name'] for e in resolved_entities],
        threshold=0.7
    )
    
    print(f"\nEntities similar to '{query_entity}':")
    for match, score in matches:
        print(f"  - {match} (similarity: {score:.3f})")
    
    return resolved_entities


def example_metrics_calculation():
    """Example: Calculating various metrics."""
    print("\n=== Metrics Calculation Example ===")
    
    # Initialize metrics calculator
    calculator = MetricsCalculator()
    
    # Example episode data
    episode_data = {
        "duration": 3600,  # 1 hour
        "segments": [
            {"text": "Introduction to AI..." * 50, "duration": 300},
            {"text": "Healthcare applications..." * 100, "duration": 600},
            {"text": "Education and AI..." * 80, "duration": 500},
        ],
        "insights": [
            {"text": "AI improves diagnosis", "confidence": 0.9},
            {"text": "Privacy is a concern", "confidence": 0.85},
            {"text": "Personalized learning", "confidence": 0.8},
        ],
        "entities": [
            {"name": "AI", "type": "TECHNOLOGY", "mentions": 15},
            {"name": "Healthcare", "type": "DOMAIN", "mentions": 8},
            {"name": "DeepMind", "type": "ORGANIZATION", "mentions": 3},
        ]
    }
    
    # Calculate information density
    density = calculator.calculate_information_density(episode_data)
    print(f"Information density: {density:.2f} insights/minute")
    
    # Calculate topic diversity
    topics = ["AI", "Healthcare", "Education", "Ethics", "Technology"]
    diversity = calculator.calculate_topic_diversity(topics)
    print(f"Topic diversity: {diversity:.2f}")
    
    # Calculate engagement score
    engagement_factors = {
        "quote_count": 5,
        "question_count": 8,
        "story_count": 3,
        "technical_depth": 0.7
    }
    engagement = calculator.calculate_engagement_score(engagement_factors)
    print(f"Engagement score: {engagement:.2f}")
    
    # Calculate complexity
    complexity = calculator.calculate_complexity_score(
        episode_data["segments"][0]["text"]
    )
    print(f"Content complexity: {complexity:.2f}")
    
    # Generate summary metrics
    summary = calculator.generate_episode_summary(episode_data)
    print("\nEpisode Summary:")
    for key, value in summary.items():
        print(f"  {key}: {value}")
    
    return summary


def example_graph_analysis():
    """Example: Analyzing the knowledge graph."""
    print("\n=== Graph Analysis Example ===")
    
    from src.providers.graph.neo4j import Neo4jGraphProvider
    
    # Initialize graph analyzer
    graph_provider = Neo4jGraphProvider(
        uri="bolt://localhost:7687",
        user="neo4j",
        password="password"
    )
    graph_analyzer = GraphAnalyzer(graph_provider)
    
    # Analyze graph structure
    structure = graph_analyzer.analyze_structure()
    print("Graph Structure:")
    print(f"  Total nodes: {structure['total_nodes']}")
    print(f"  Total relationships: {structure['total_relationships']}")
    print(f"  Node types: {', '.join(structure['node_types'])}")
    
    # Find central entities
    central_entities = graph_analyzer.find_central_entities(limit=5)
    print("\nMost Central Entities:")
    for entity in central_entities:
        print(f"  - {entity['name']} (centrality: {entity['centrality']:.3f})")
    
    # Detect communities
    communities = graph_analyzer.detect_communities()
    print(f"\nDetected {len(communities)} communities:")
    for i, community in enumerate(communities[:3]):
        print(f"  Community {i+1}: {len(community['nodes'])} nodes")
        print(f"    Topics: {', '.join(community['topics'][:3])}")
    
    # Find knowledge gaps
    gaps = graph_analyzer.find_knowledge_gaps()
    print("\nKnowledge Gaps:")
    for gap in gaps[:5]:
        print(f"  - {gap['description']} (score: {gap['importance']:.2f})")
    
    # Analyze temporal patterns
    temporal = graph_analyzer.analyze_temporal_patterns()
    print("\nTemporal Patterns:")
    print(f"  Peak activity: {temporal['peak_period']}")
    print(f"  Trend: {temporal['trend']}")
    
    return {
        "structure": structure,
        "central_entities": central_entities,
        "communities": communities,
        "gaps": gaps
    }


def example_complexity_analysis():
    """Example: Analyzing content complexity."""
    print("\n=== Complexity Analysis Example ===")
    
    # Initialize complexity analyzer
    analyzer = ComplexityAnalyzer()
    
    # Example texts of varying complexity
    simple_text = """
    AI helps computers learn. It can recognize pictures and understand speech.
    Many people use AI every day on their phones.
    """
    
    moderate_text = """
    Artificial intelligence encompasses machine learning algorithms that process
    vast datasets to identify patterns. These systems can perform tasks like
    natural language processing and computer vision with increasing accuracy.
    """
    
    complex_text = """
    The paradigm shift towards transformer-based architectures has revolutionized
    natural language processing through self-attention mechanisms. These models
    leverage multi-head attention to capture long-range dependencies and contextual
    representations, enabling unprecedented performance on downstream tasks.
    """
    
    # Analyze each text
    for i, (label, text) in enumerate([
        ("Simple", simple_text),
        ("Moderate", moderate_text),
        ("Complex", complex_text)
    ]):
        print(f"\n{label} Text Analysis:")
        
        # Vocabulary complexity
        vocab_score = analyzer.analyze_vocabulary_complexity(text)
        print(f"  Vocabulary complexity: {vocab_score:.2f}")
        
        # Sentence complexity
        sentence_score = analyzer.analyze_sentence_complexity(text)
        print(f"  Sentence complexity: {sentence_score:.2f}")
        
        # Technical density
        technical_score = analyzer.calculate_technical_density(text)
        print(f"  Technical density: {technical_score:.2f}")
        
        # Overall complexity
        overall = analyzer.calculate_overall_complexity(text)
        print(f"  Overall complexity: {overall:.2f}")
        
        # Accessibility
        accessibility = analyzer.calculate_accessibility_score(text)
        print(f"  Accessibility score: {accessibility:.2f}")
    
    # Segment classification
    segment = {
        "text": moderate_text,
        "duration": 120,
        "speaker": "Expert"
    }
    
    classification = analyzer.classify_segment_complexity(segment)
    print(f"\nSegment classified as: {classification}")
    
    return analyzer


def example_pipeline_integration():
    """Example: Integrating all processing modules."""
    print("\n=== Pipeline Integration Example ===")
    
    # This example shows how processing modules work together
    
    # 1. Start with raw transcript
    transcript = """
    Welcome to our podcast on artificial intelligence. Today, we have 
    Dr. Sarah Johnson from MIT to discuss how AI is transforming healthcare.
    
    Dr. Johnson explains that machine learning algorithms can now detect 
    certain cancers with 95% accuracy, surpassing human radiologists.
    Companies like DeepMind and IBM Watson are pioneering these technologies.
    
    However, there are concerns about data privacy and algorithmic bias
    that we need to address as we deploy these systems more widely.
    """
    
    # 2. Segment the transcript
    segmenter = EnhancedPodcastSegmenter()
    segments = segmenter.segment_transcript(transcript)
    print(f"Step 1: Created {len(segments)} segments")
    
    # 3. Extract knowledge from each segment
    # (In practice, you'd use actual providers)
    extracted_data = {
        "insights": [
            {"text": "AI can detect cancers with 95% accuracy", "confidence": 0.9},
            {"text": "AI surpasses human radiologists in some tasks", "confidence": 0.85}
        ],
        "entities": [
            {"name": "Dr. Sarah Johnson", "type": "PERSON"},
            {"name": "MIT", "type": "ORGANIZATION"},
            {"name": "DeepMind", "type": "ORGANIZATION"},
            {"name": "IBM Watson", "type": "ORGANIZATION"}
        ],
        "topics": ["AI", "Healthcare", "Cancer Detection", "Privacy", "Bias"]
    }
    print(f"Step 2: Extracted {len(extracted_data['insights'])} insights")
    
    # 4. Resolve entities
    # (Simplified - normally uses embedding provider)
    resolved_entities = [
        {"canonical_name": "Dr. Sarah Johnson", "type": "PERSON", "aliases": []},
        {"canonical_name": "Massachusetts Institute of Technology", "type": "ORGANIZATION", "aliases": ["MIT"]},
        {"canonical_name": "DeepMind", "type": "ORGANIZATION", "aliases": ["Deep Mind"]},
        {"canonical_name": "IBM Watson", "type": "ORGANIZATION", "aliases": ["Watson"]}
    ]
    print(f"Step 3: Resolved to {len(resolved_entities)} unique entities")
    
    # 5. Calculate metrics
    calculator = MetricsCalculator()
    metrics = {
        "information_density": 2.5,  # insights per minute
        "topic_diversity": 0.8,
        "complexity_score": 0.6,
        "engagement_score": 0.75
    }
    print(f"Step 4: Calculated metrics - complexity: {metrics['complexity_score']}")
    
    # 6. Analyze complexity
    analyzer = ComplexityAnalyzer()
    complexity_report = {
        "vocabulary_complexity": 0.7,
        "technical_density": 0.6,
        "accessibility_score": 0.65,
        "recommended_audience": "Intermediate"
    }
    print(f"Step 5: Complexity analysis - audience: {complexity_report['recommended_audience']}")
    
    # Final integrated result
    processed_episode = {
        "segments": segments,
        "insights": extracted_data["insights"],
        "entities": resolved_entities,
        "metrics": metrics,
        "complexity": complexity_report,
        "topics": extracted_data["topics"]
    }
    
    print("\nProcessing complete!")
    print(f"  Total segments: {len(processed_episode['segments'])}")
    print(f"  Total insights: {len(processed_episode['insights'])}")
    print(f"  Unique entities: {len(processed_episode['entities'])}")
    print(f"  Topics covered: {', '.join(processed_episode['topics'])}")
    
    return processed_episode


if __name__ == "__main__":
    """Run all processing examples."""
    
    print("Processing Module Examples")
    print("=" * 60)
    
    # Run examples
    example_segmentation()
    example_knowledge_extraction()
    example_entity_resolution()
    example_metrics_calculation()
    example_graph_analysis()
    example_complexity_analysis()
    example_pipeline_integration()
    
    print("\n" + "=" * 60)
    print("Examples completed - see code for implementation details")