"""Examples for using different providers in the Podcast Knowledge Graph Pipeline."""

from src.providers.llm.gemini import GeminiProvider
from src.providers.graph.neo4j import Neo4jGraphProvider
from src.providers.embeddings.sentence_transformer import SentenceTransformerEmbeddingProvider
from src.core.models import Podcast, Episode, Segment, Insight
from src.processing.vtt_parser import VTTParser
from src.seeding.transcript_ingestion import TranscriptIngestion


def example_vtt_processing():
    """Example: Processing VTT transcript files."""
    print("=== VTT Processing Example ===")
    
    # Initialize VTT parser
    parser = VTTParser()
    
    # Parse a VTT file
    vtt_file = "path/to/transcript.vtt"
    segments = parser.parse_file(vtt_file)
    print(f"Parsed {len(segments)} segments from VTT file")
    
    # Show first few segments
    for i, segment in enumerate(segments[:3]):
        print(f"  Segment {i}: {segment.speaker} at {segment.start:.1f}s: {segment.text[:50]}...")
    
    # Process entire directory
    ingestion = TranscriptIngestion()
    results = ingestion.process_directory(
        directory="path/to/vtt/files",
        pattern="*.vtt",
        recursive=True
    )
    
    print(f"Processed {results['processed_count']} VTT files")
    print(f"Total segments: {results['total_segments']}")
    
    return segments


def example_llm_provider():
    """Example: Using the Gemini LLM provider."""
    print("\n=== LLM Provider Example ===")
    
    # Initialize provider
    llm_provider = GeminiProvider(
        api_key="your-api-key",
        model_name="gemini-1.5-pro",
        temperature=0.7,
        max_output_tokens=2000
    )
    
    # Generate text
    prompt = """
    Extract key insights from this podcast transcript:
    
    "Today we're discussing artificial intelligence and its impact on society.
    AI is transforming healthcare, education, and transportation..."
    """
    
    response = llm_provider.generate(prompt)
    print(f"Generated response: {response[:200]}...")
    
    # Generate structured output
    schema = {
        "insights": [
            {
                "text": "string",
                "confidence": "float",
                "category": "string"
            }
        ],
        "entities": ["string"],
        "summary": "string"
    }
    
    structured_response = llm_provider.generate_structured(prompt, schema)
    print(f"Extracted {len(structured_response.get('insights', []))} insights")
    
    # Count tokens
    token_count = llm_provider.count_tokens(prompt)
    print(f"Prompt uses {token_count} tokens")
    
    return structured_response


def example_graph_provider():
    """Example: Using the Neo4j graph provider."""
    print("\n=== Graph Provider Example ===")
    
    # Initialize provider
    graph_provider = Neo4jGraphProvider(
        uri="bolt://localhost:7687",
        user="neo4j",
        password="your-password"
    )
    
    # Create a podcast node
    podcast_data = {
        "name": "Tech Talks",
        "description": "Weekly technology discussions",
        "category": "Technology",
        "url": "https://example.com/podcast"
    }
    
    podcast_id = graph_provider.create_podcast(
        Podcast(**podcast_data)
    )
    print(f"Created podcast with ID: {podcast_id}")
    
    # Create an episode
    episode_data = {
        "title": "AI Revolution",
        "description": "Exploring the AI transformation",
        "url": "https://example.com/episode1",
        "publication_date": "2024-01-01",
        "duration": 3600
    }
    
    episode_id = graph_provider.create_episode(
        Episode(**episode_data),
        podcast_id
    )
    print(f"Created episode with ID: {episode_id}")
    
    # Create an insight
    insight_data = {
        "text": "AI is democratizing access to advanced technology",
        "confidence_score": 0.85,
        "insight_type": "observation"
    }
    
    insight_id = graph_provider.create_insight(
        Insight(**insight_data),
        episode_id
    )
    print(f"Created insight with ID: {insight_id}")
    
    # Query the graph
    query = """
    MATCH (p:Podcast)-[:HAS_EPISODE]->(e:Episode)-[:HAS_INSIGHT]->(i:Insight)
    WHERE p.name = $name
    RETURN i.text as insight, i.confidence_score as confidence
    """
    
    results = graph_provider.execute_query(query, {"name": "Tech Talks"})
    for record in results:
        print(f"Insight: {record['insight']} (confidence: {record['confidence']})")
    
    return podcast_id, episode_id


def example_embedding_provider():
    """Example: Using the embedding provider."""
    print("\n=== Embedding Provider Example ===")
    
    # Initialize provider
    embedding_provider = SentenceTransformerEmbeddingProvider(
        model_name="all-MiniLM-L6-v2"  # Fast and efficient model
    )
    
    # Generate embeddings for texts
    texts = [
        "Artificial intelligence is transforming technology",
        "Machine learning enables computers to learn from data",
        "The weather today is sunny and warm",
        "AI and ML are closely related fields"
    ]
    
    embeddings = embedding_provider.embed_batch(texts)
    print(f"Generated embeddings with shape: {embeddings.shape}")
    
    # Calculate similarities
    from sklearn.metrics.pairwise import cosine_similarity
    
    similarities = cosine_similarity(embeddings)
    print("\nText similarities:")
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            sim = similarities[i, j]
            print(f"  '{texts[i][:30]}...' <-> '{texts[j][:30]}...': {sim:.3f}")
    
    # Find most similar to a query
    query = "Deep learning and neural networks"
    query_embedding = embedding_provider.embed(query)
    
    similarities_to_query = cosine_similarity([query_embedding], embeddings)[0]
    most_similar_idx = similarities_to_query.argmax()
    
    print(f"\nMost similar to '{query}':")
    print(f"  '{texts[most_similar_idx]}' (similarity: {similarities_to_query[most_similar_idx]:.3f})")
    
    return embeddings


def example_provider_composition():
    """Example: Composing multiple providers together."""
    print("\n=== Provider Composition Example ===")
    
    # Initialize providers
    vtt_parser = VTTParser()
    llm_provider = GeminiProvider(api_key="your-key")
    graph_provider = Neo4jGraphProvider(
        uri="bolt://localhost:7687",
        user="neo4j",
        password="password"
    )
    embedding_provider = SentenceTransformerEmbeddingProvider()
    
    # Process a VTT transcript
    vtt_file = "episode_transcript.vtt"
    
    # Step 1: Parse VTT
    print("1. Parsing VTT transcript...")
    segments = vtt_parser.parse_file(vtt_file)
    transcript = " ".join([seg.text for seg in segments])
    
    # Step 2: Extract insights
    print("2. Extracting insights...")
    prompt = f"Extract key insights from: {transcript[:1000]}..."
    insights = llm_provider.generate_structured(
        prompt,
        {"insights": [{"text": "string", "confidence": "float"}]}
    )
    
    # Step 3: Generate embeddings
    print("3. Generating embeddings...")
    insight_texts = [i["text"] for i in insights.get("insights", [])]
    embeddings = embedding_provider.embed_batch(insight_texts)
    
    # Step 4: Store in graph
    print("4. Storing in knowledge graph...")
    podcast_id = graph_provider.create_podcast(
        Podcast(name="Example Podcast", category="Demo")
    )
    
    episode_id = graph_provider.create_episode(
        Episode(title="Example Episode", url="https://example.com"),
        podcast_id
    )
    
    for i, (insight, embedding) in enumerate(zip(insights["insights"], embeddings)):
        insight_obj = Insight(
            text=insight["text"],
            confidence_score=insight["confidence"],
            embedding=embedding.tolist()
        )
        graph_provider.create_insight(insight_obj, episode_id)
    
    print(f"Stored {len(insights['insights'])} insights in graph")
    
    return podcast_id, episode_id


def example_error_handling():
    """Example: Handling provider errors gracefully."""
    print("\n=== Error Handling Example ===")
    
    from src.core.exceptions import ProviderError, ProcessingError
    
    # Example: Handle VTT parsing errors
    vtt_parser = VTTParser()
    
    try:
        # Try to parse a non-existent file
        segments = vtt_parser.parse_file("non_existent.vtt")
    except (FileNotFoundError, ProcessingError) as e:
        print(f"VTT parsing failed: {e}")
        # Fallback action
        segments = []
    
    # Example: Handle LLM errors with retry
    from src.utils.retry import with_retry
    
    @with_retry(max_attempts=3, backoff_factor=2)
    def extract_with_retry(prompt):
        llm_provider = GeminiProvider(api_key="your-key")
        return llm_provider.generate(prompt)
    
    try:
        result = extract_with_retry("Extract insights from...")
    except ProviderError as e:
        print(f"LLM failed after retries: {e}")
        result = None
    
    # Example: Handle graph connection issues
    try:
        graph_provider = Neo4jGraphProvider(
            uri="bolt://localhost:7687",
            user="neo4j",
            password="wrong-password"
        )
    except Exception as e:
        print(f"Graph connection failed: {e}")
        # Use in-memory provider as fallback
        from src.providers.graph.memory import InMemoryGraphProvider
        graph_provider = InMemoryGraphProvider()
        print("Using in-memory graph as fallback")
    
    return graph_provider


def example_custom_configuration():
    """Example: Custom provider configuration."""
    print("\n=== Custom Configuration Example ===")
    
    from src.core.config import Config
    from src.factories.provider_factory import ProviderFactory
    
    # Create custom configuration
    config = Config()
    
    # VTT processing configuration
    config.vtt_directory = "/path/to/vtt/files"
    config.vtt_pattern = "*.vtt"
    config.merge_consecutive_segments = True
    config.segment_merge_threshold = 2.0
    
    # LLM configuration
    config.llm_provider = "gemini"
    config.model_name = "gemini-1.5-pro"
    config.temperature = 0.5
    config.max_output_tokens = 4000
    
    # Graph configuration
    config.graph_provider = "neo4j"
    config.neo4j_max_connection_lifetime = 3600
    config.neo4j_max_connection_pool_size = 50
    
    # Create providers from configuration
    factory = ProviderFactory()
    
    llm_provider = factory.create_provider("llm", config)
    graph_provider = factory.create_provider("graph", config)
    
    print(f"Created {config.llm_provider} LLM provider") 
    print(f"Created {config.graph_provider} graph provider")
    
    # Create VTT processing components
    vtt_parser = VTTParser(
        merge_consecutive=config.merge_consecutive_segments,
        merge_threshold=config.segment_merge_threshold
    )
    
    return vtt_parser, llm_provider, graph_provider


if __name__ == "__main__":
    """Run all provider examples."""
    
    # Note: These examples require actual API keys and services to be running
    # They are meant to demonstrate the API usage patterns
    
    print("Provider Examples - Demonstrating API usage patterns")
    print("=" * 60)
    
    # Run examples (will fail without proper setup, but shows the API)
    try:
        example_vtt_processing()
    except Exception as e:
        print(f"VTT example failed (expected without VTT file): {e}")
    
    try:
        example_llm_provider()
    except Exception as e:
        print(f"LLM example failed (expected without API key): {e}")
    
    try:
        example_graph_provider()
    except Exception as e:
        print(f"Graph example failed (expected without Neo4j): {e}")
    
    try:
        example_embedding_provider()
    except Exception as e:
        print(f"Embedding example failed: {e}")
    
    # These should work as they handle errors
    example_error_handling()
    example_custom_configuration()
    
    print("\n" + "=" * 60)
    print("Examples completed - see code for usage patterns")