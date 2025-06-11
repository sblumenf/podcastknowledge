# VTT Metadata Extraction Plan

## Overview
This plan outlines the approach for extracting and incorporating metadata (including YouTube URLs) from VTT files into the knowledge graph/Neo4j database.

## Current State

### What We Have Now:
1. **VTT files with rich metadata** - The transcriber creates VTT files that contain valuable metadata in NOTE blocks at the top of the file
2. **A parser that ignores metadata** - The seeding pipeline's VTT parser skips over all NOTE blocks and only extracts the transcript content (line 136: "Skip header and any metadata")
3. **Limited data model** - The Episode model doesn't have fields for YouTube URLs or other metadata that might be in the VTT files

### What's in the VTT Metadata:
The VTT files contain NOTE blocks with information like:
- Episode title and podcast name
- YouTube URL
- Original podcast URL
- Episode description
- Publication date
- Transcription service used
- Processing timestamps

Example from actual VTT file:
```vtt
NOTE Content Details
Description: [episode description]
Original URL: [podcast RSS link]
YouTube URL: https://www.youtube.com/watch?v=1JbfAr-BQjA

NOTE JSON Metadata
{
  "podcast": "The Mel Robbins Podcast",
  "episode": "3 Simple Steps to Change Your Life",
  "date": "2022-10-06",
  "youtube_url": "https://www.youtube.com/watch?v=1JbfAr-BQjA",
  ...
}
```

## Proposed Approach

### 1. **Enhance the VTT Parser**
Instead of skipping the NOTE blocks, modify the VTT parser to:
- Parse and extract all NOTE blocks before processing the transcript cues
- Specifically look for the "NOTE JSON Metadata" block which contains structured data
- Parse that JSON to extract fields like `youtube_url`, `podcast`, `episode`, `date`, etc.
- Return both the transcript segments AND the extracted metadata

### 2. **Update the Data Flow**
The parser would return something like:
```python
{
    "metadata": {
        "youtube_url": "https://youtube.com/...",
        "podcast_name": "The Mel Robbins Podcast",
        "episode_title": "3 Simple Steps...",
        "published_date": "2022-10-06",
        # ... other fields
    },
    "segments": [/* transcript segments */]
}
```

### 3. **Extend the Data Models**
Update the Episode model to include:
- `youtube_url` field
- Any other useful metadata fields we're currently missing
- Keep it backward compatible with episodes that don't have this data

### 4. **Update the Ingestion Process**
Modify the transcript ingestion to:
- Use the enhanced parser that extracts metadata
- Populate the Episode object with both transcript data and metadata
- Handle cases where metadata might be missing (older VTT files)

### 5. **Enhance Neo4j Storage**
Update the graph storage to:
- Include YouTube URL as a property on Episode nodes
- Potentially create a separate relationship or node type for YouTube videos if we want to track video-specific metrics
- Store other useful metadata that could enhance the knowledge graph

### 6. **Consider Future Extensibility**
Design this in a way that:
- Makes it easy to add new metadata fields in the future
- Doesn't break if VTT files don't have certain metadata
- Allows for different versions of VTT metadata formats

## YouTube Timestamp URL Support

### Current State
- Segment nodes already contain `start_time` and `end_time` (in seconds)
- Episode nodes don't currently have the YouTube URL
- Once YouTube URLs are extracted from VTT metadata and stored on Episode nodes, we can create timestamped links

### Implementation
With both pieces of information available, we can construct YouTube URLs that jump to specific segments:

#### URL Format Options:
1. **Seconds format**: `https://www.youtube.com/watch?v=VIDEO_ID&t=123`
2. **Time format**: `https://www.youtube.com/watch?v=VIDEO_ID&t=1h2m3s`

#### Example:
- Episode has `youtube_url`: `https://www.youtube.com/watch?v=1JbfAr-BQjA`
- Segment has `start_time`: `245.5` seconds
- Resulting URL: `https://www.youtube.com/watch?v=1JbfAr-BQjA&t=245`

### Use Cases
1. **Knowledge graph navigation** - Click on any segment to view it on YouTube
2. **Quote attribution** - Link quotes directly to their video timestamp
3. **Topic exploration** - Jump to specific topics discussed in the video
4. **Search results** - Return timestamped video links for relevant content

### Implementation Considerations
- Add a utility function to construct timestamped URLs
- Consider storing pre-constructed URLs as segment properties for performance
- Handle edge cases (missing YouTube URL, invalid timestamps)
- Support both seconds and formatted time strings

## YouTube URL Discovery for Missing URLs

### Simple Approach
When a VTT file doesn't contain a YouTube URL, the seeding pipeline should be able to find it independently.

### Implementation Strategy: Copy Core Search Logic
1. **Create a simple `youtube_search.py` file** in the seeding pipeline with basic YouTube search functionality
2. **Copy only essential logic** from the transcriber (not the entire matcher/scorer/builder system)
3. **Keep it simple**:
   - Direct YouTube Data API v3 calls
   - Basic search query: `"{podcast_name}" "{episode_title}"`
   - Simple validation: Does the video title reasonably match?
   - Return first good match or None

### Example Implementation
```python
# src/utils/youtube_search.py
def search_youtube_url(podcast_name: str, episode_title: str, 
                      published_date: Optional[str] = None) -> Optional[str]:
    """Simple YouTube search for podcast episodes."""
    # Build search query
    query = f'"{podcast_name}" "{episode_title}"'
    
    # Call YouTube API
    results = youtube_api.search(query, max_results=5)
    
    # Basic matching - check if podcast and episode names appear in title
    for video in results:
        if podcast_name.lower() in video.title.lower() and \
           any(word in video.title.lower() for word in episode_title.lower().split()[:3]):
            return f"https://www.youtube.com/watch?v={video.id}"
    
    return None
```

### Integration in VTT Ingestion
```python
# In transcript_ingestion.py
metadata = parse_vtt_metadata(vtt_file)
if not metadata.get('youtube_url'):
    # Try to find it
    youtube_url = search_youtube_url(
        metadata.get('podcast_name'),
        metadata.get('episode_title'),
        metadata.get('date')
    )
    if youtube_url:
        metadata['youtube_url'] = youtube_url
```

### Benefits of This Simple Approach
- **Independent deployment** - No dependencies between transcriber and seeding modules
- **Minimal code** - Maybe 100-200 lines total
- **Easy to maintain** - Self-contained functionality
- **Flexible** - Can enhance search logic independently in each module
- **No over-engineering** - Just basic search that works

### Configuration
Add simple config options:
```yaml
youtube_search:
  enabled: true
  api_key: ${YOUTUBE_API_KEY}
  max_results: 5
```

## InfraNodus-Inspired Knowledge Discovery Enhancements

### 1. Structural Gap Detection

**What It Does**: Identifies "blind spots" between topic clusters - areas where knowledge exists in silos but could be connected.

**Implementation Approach**:
```python
def update_structural_gaps(new_episode):
    # 1. Identify which topic clusters the new episode touches
    touched_clusters = get_clusters_for_episode(new_episode)
    
    # 2. Only recalculate gaps between affected clusters
    for cluster in touched_clusters:
        # Check if this cluster now connects to others
        update_cluster_connections(cluster)
    
    # 3. Store gap information
    store_gap_metrics(cluster_gaps)
```

**Storage in Neo4j**:
```cypher
(:StructuralGap {
    cluster1: "productivity",
    cluster2: "mental_health",
    gap_score: 0.85,
    potential_bridges: ["exercise", "meditation"],
    last_updated: timestamp()
})
```

### 2. Missing Link Analysis

**What It Does**: Finds entities/topics that could be connected but aren't currently linked in any episodes.

**Example**: If "morning routines" and "productivity" are never discussed together, this would identify that missing connection.

**Implementation Approach**:
```python
def update_missing_links(new_episode_entities):
    # Only check new entities against existing ones
    for new_entity in new_episode_entities:
        unconnected = find_unconnected_entities(new_entity)
        potential_connections = calculate_connection_potential(new_entity, unconnected)
        store_missing_links(potential_connections)
```

**Storage Pattern**:
```cypher
(:MissingLink {
    entity1: "James Clear",
    entity2: "Carol Dweck",
    potential_connection: "growth mindset in habit formation",
    strength: 0.75,
    first_detected: timestamp()
})
```

### 3. Ecological Thinking Metrics

**What It Does**: Measures knowledge diversity and balance across topics to prevent over-focus on certain areas.

**Metrics to Track**:
- Topic distribution (how evenly spread across different subjects)
- Knowledge depth vs breadth balance
- Emerging vs established topic ratio

**Implementation**:
```python
def update_diversity_metrics(new_episode):
    # Update running statistics
    metrics = load_current_metrics()
    
    for topic in new_episode.topics:
        metrics.topic_counts[topic] += 1
    
    # Calculate diversity score (Shannon entropy)
    metrics.diversity_score = calculate_diversity(metrics.topic_counts)
    metrics.balance_score = calculate_balance(metrics.topic_counts)
    
    save_metrics(metrics)
```

**Storage**:
```cypher
(:EcologicalMetrics {
    type: 'knowledge_diversity',
    diversity_score: 0.75,
    balance_score: 0.82,
    topic_distribution: {
        'productivity': 0.3,
        'mindset': 0.25,
        'health': 0.2,
        'technology': 0.25
    },
    last_updated: timestamp()
})
```

### Incremental Update Strategy

All three enhancements can be updated incrementally when new episodes are added:
1. No need to reprocess the entire graph
2. Only analyze how new content affects existing patterns
3. Maintain running statistics and metrics
4. Update only affected clusters and connections

## Benefits of This Approach

1. **No changes needed to the transcriber** - It's already producing the right output
2. **Preserves all valuable metadata** - Not just YouTube URLs but all the enrichment the transcriber provides
3. **Enhances the knowledge graph** - More connections and richer data for analysis
4. **Backward compatible** - Older VTT files without metadata still work
5. **Discovers hidden patterns** - Reveals gaps and missing connections in knowledge
6. **Promotes balanced learning** - Tracks knowledge diversity and prevents over-focus

## Key Design Decisions

1. **Where to parse the metadata**: In the VTT parser itself, keeping all VTT-related logic together
2. **How to handle missing metadata**: Use Optional fields and graceful defaults
3. **What metadata to store**: Start with YouTube URL but design for easy extension
4. **How to structure in Neo4j**: As properties on Episode nodes initially, with option to expand later

## Implementation Notes

The core insight is that the VTT files are already rich with metadata - we just need to stop throwing it away and start incorporating it into the knowledge graph. The changes would be focused and wouldn't require major architectural changes to either system.

## Files to Modify

1. `src/vtt/vtt_parser.py` - Main parser changes
2. `src/core/models.py` - Add youtube_url and other metadata fields to Episode
3. `src/seeding/transcript_ingestion.py` - Update to use metadata from parser
4. `src/storage/graph_storage.py` - Store additional metadata in Neo4j
5. `src/utils/youtube_search.py` - New file for simple YouTube search functionality
6. `src/analysis/gap_detection.py` - New file for structural gap analysis
7. `src/analysis/missing_links.py` - New file for missing link detection
8. `src/analysis/diversity_metrics.py` - New file for ecological thinking metrics
9. Tests for all of the above

## Next Steps

- [ ] Review and refine this plan
- [ ] Implement VTT parser enhancements
- [ ] Update data models
- [ ] Modify ingestion process
- [ ] Update Neo4j storage
- [ ] Add comprehensive tests
- [ ] Document the new metadata fields