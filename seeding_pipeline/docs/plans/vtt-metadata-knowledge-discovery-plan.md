# VTT Metadata Extraction and Knowledge Discovery Implementation Plan

## Executive Summary

This plan implements comprehensive enhancements to the seeding pipeline that will extract YouTube URLs and metadata from VTT files, automatically discover missing YouTube URLs, and add three knowledge discovery features inspired by InfraNodus. The result will be a knowledge graph enriched with video timestamps and advanced analytics that can identify content gaps, missing connections, and knowledge diversity patterns - ultimately enabling podcasters to discover untapped content opportunities.

## Phase 1: VTT Metadata Extraction Foundation

### Task 1.1: Enhance VTT Parser to Extract Metadata
- [x] Task description: Modify the VTT parser to extract and parse NOTE blocks containing metadata
- Purpose: Capture YouTube URLs and episode metadata currently being skipped
- Steps:
  1. Use context7 MCP tool to review VTT parsing documentation and best practices
  2. Open `src/vtt/vtt_parser.py` and locate the line that skips metadata (line ~136)
  3. Add new method `_parse_note_blocks(self, lines: List[str]) -> Dict[str, Any]`
  4. Implement JSON metadata extraction:
     - Search for "NOTE JSON Metadata" marker
     - Extract JSON block and parse with json.loads()
     - Handle parsing errors gracefully
  5. Implement fallback regex parsing for human-readable NOTE blocks:
     - Pattern for "YouTube URL: <url>"
     - Pattern for "Description: <text>"
     - Pattern for other metadata fields
  6. Modify `parse_content()` to call `_parse_note_blocks()` before parsing cues
  7. Update return structure to include both metadata and segments
- Validation: 
  - Unit test with sample VTT files containing metadata
  - Verify parser extracts YouTube URL correctly
  - Ensure backward compatibility with VTT files without metadata

### Task 1.2: Update Episode Data Model
- [x] Task description: Add YouTube URL and metadata fields to Episode model
- Purpose: Enable storage of extracted metadata in the data structure
- Steps:
  1. Use context7 MCP tool to review data model documentation
  2. Open `src/core/models.py` and locate Episode class
  3. Add fields:
     - `youtube_url: Optional[str] = None`
     - `transcript_metadata: Optional[Dict[str, Any]] = None`
  4. Update any Episode factory methods or constructors
  5. Ensure serialization/deserialization handles new fields
  6. Add validation for YouTube URL format
- Validation:
  - Create test Episode objects with new fields
  - Verify serialization to/from dict works
  - Check that existing code doesn't break with new optional fields

### Task 1.3: Update Transcript Ingestion Process
- [x] Task description: Modify ingestion to use metadata from enhanced parser
- Purpose: Flow metadata from VTT files into Episode objects
- Steps:
  1. Use context7 MCP tool to review ingestion process documentation
  2. Open `src/seeding/transcript_ingestion.py`
  3. Locate VTT file processing logic
  4. Update to use enhanced parser that returns metadata
  5. Extract metadata fields and populate Episode object:
     - Set episode.youtube_url from metadata
     - Store additional metadata in episode.transcript_metadata
  6. Add logging for metadata extraction success/failure
  7. Handle cases where metadata is missing gracefully
- Validation:
  - Process a VTT file with metadata and verify Episode has YouTube URL
  - Process a VTT file without metadata and verify it still works
  - Check logs show metadata extraction status

### Task 1.4: Enhance Neo4j Storage for Metadata
- [x] Task description: Update graph storage to persist YouTube URLs and metadata
- Purpose: Store enriched metadata in the knowledge graph
- Steps:
  1. Use context7 MCP tool to review Neo4j schema documentation
  2. Open `src/storage/graph_storage.py`
  3. Locate Episode node creation logic
  4. Add YouTube URL to Episode node properties:
     - Add 'youtube_url' to property dict
     - Ensure None values are handled properly
  5. Add metadata storage strategy:
     - Store key metadata fields as node properties
     - Consider JSON serialization for complex metadata
  6. Update any Episode node queries to include new fields
  7. Add index on youtube_url for performance
- Validation:
  - Create Episode node with YouTube URL and query it back
  - Verify YouTube URL appears in Neo4j browser
  - Test querying episodes by YouTube URL

## Phase 2: YouTube URL Discovery

### Task 2.1: Create Simple YouTube Search Module
- [ ] Task description: Implement basic YouTube search functionality
- Purpose: Find YouTube URLs for episodes missing them
- Steps:
  1. Use context7 MCP tool to review YouTube Data API documentation
  2. Create new file `src/utils/youtube_search.py`
  3. Implement basic search function:
     ```python
     def search_youtube_url(podcast_name: str, episode_title: str, 
                           published_date: Optional[str] = None) -> Optional[str]
     ```
  4. Add YouTube API client initialization:
     - Use googleapiclient.discovery
     - Handle API key from environment/config
  5. Implement search logic:
     - Build query string: f'"{podcast_name}" "{episode_title}"'
     - Call youtube.search().list() with parameters
     - Parse results and extract video IDs
  6. Add basic matching validation:
     - Check if podcast name appears in video title
     - Check if key episode words appear
     - Return first match or None
  7. Add error handling for API failures
  8. Add rate limiting to respect quotas
- Validation:
  - Test with known podcast/episode combinations
  - Verify correct YouTube URLs are returned
  - Test with non-existent episodes returns None

### Task 2.2: Integrate YouTube Discovery in Ingestion
- [ ] Task description: Add YouTube search fallback during VTT processing
- Purpose: Automatically find missing YouTube URLs
- Steps:
  1. Use context7 MCP tool to review ingestion pipeline documentation
  2. Open `src/seeding/transcript_ingestion.py`
  3. Import youtube_search module
  4. After metadata extraction, check if youtube_url exists
  5. If missing, extract search parameters:
     - podcast_name from metadata or directory structure
     - episode_title from metadata or filename
     - published_date if available
  6. Call search_youtube_url() with parameters
  7. If URL found, add to episode data
  8. Add configuration flag to enable/disable YouTube search
  9. Log search attempts and results
- Validation:
  - Process VTT without YouTube URL and verify search runs
  - Check that found URLs are added to Episode objects
  - Verify configuration flag works

### Task 2.3: Add YouTube Search Configuration
- [ ] Task description: Add configuration options for YouTube search
- Purpose: Make YouTube search configurable and manageable
- Steps:
  1. Use context7 MCP tool to review configuration system documentation
  2. Open `config/seeding.yaml` or relevant config file
  3. Add YouTube search configuration section:
     ```yaml
     youtube_search:
       enabled: true
       api_key: ${YOUTUBE_API_KEY}
       max_results: 5
       confidence_threshold: 0.7
     ```
  4. Update configuration loading to include these settings
  5. Modify youtube_search.py to use configuration
  6. Add environment variable support for API key
  7. Document configuration options
- Validation:
  - Toggle enabled flag and verify search behavior
  - Test with different max_results values
  - Verify API key loads from environment

## Phase 3: Knowledge Discovery Enhancements

### Task 3.1: Implement Structural Gap Detection
- [ ] Task description: Create gap detection between topic clusters
- Purpose: Identify knowledge silos and unexplored connections
- Steps:
  1. Use context7 MCP tool to review graph analysis documentation
  2. Create new file `src/analysis/gap_detection.py`
  3. Implement topic cluster identification:
     ```python
     def identify_topic_clusters(session) -> List[Set[str]]
     ```
     - Query topics and their episode relationships
     - Group topics that frequently co-occur
     - Use simple threshold (e.g., appear together in >30% of episodes)
  4. Implement gap scoring:
     ```python
     def calculate_gap_score(cluster1: Set[str], cluster2: Set[str], session) -> float
     ```
     - Count episodes where cluster1 topics appear
     - Count episodes where cluster2 topics appear
     - Count episodes where both appear
     - Gap score = 1 - (both_count / min(cluster1_count, cluster2_count))
  5. Create StructuralGap node storage:
     - Define node properties: cluster1, cluster2, gap_score, potential_bridges
     - Implement create_gap_node() function
  6. Add incremental update logic:
     - Only recalculate gaps for clusters touched by new episode
     - Update existing gap scores
  7. Add bridge concept detection:
     - Find entities that appear with both clusters separately
- Validation:
  - Run on test data with known topic clusters
  - Verify gap scores make logical sense
  - Query StructuralGap nodes from Neo4j

### Task 3.2: Implement Missing Link Analysis
- [ ] Task description: Detect potentially valuable unconnected entities
- Purpose: Find entities that should be connected but aren't
- Steps:
  1. Use context7 MCP tool to review entity analysis patterns
  2. Create new file `src/analysis/missing_links.py`
  3. Implement entity pair analysis:
     ```python
     def find_missing_links(new_entities: List[str], session) -> List[Dict]
     ```
  4. For each new entity:
     - Query entities of same type (person, concept, etc.)
     - Find entities with high individual frequency
     - Check if they ever co-occur
  5. Calculate connection potential:
     - Base score on entity frequencies
     - Boost score for same entity type
     - Consider semantic similarity if embeddings available
  6. Create MissingLink node storage:
     - Properties: entity1, entity2, potential_connection, strength
     - Store suggested connection topic
  7. Implement incremental updates:
     - Only check new entities against existing ones
     - Update scores if entities now connected
  8. Add connection suggestion logic:
     - Generate potential topic combining both entities
- Validation:
  - Test with known unconnected entities
  - Verify missing links are logical
  - Check that connected entities don't appear as missing links

### Task 3.3: Implement Ecological Thinking Metrics
- [ ] Task description: Track knowledge diversity and balance
- Purpose: Measure and promote balanced knowledge exploration
- Steps:
  1. Use context7 MCP tool to review diversity metrics documentation
  2. Create new file `src/analysis/diversity_metrics.py`
  3. Implement diversity tracking:
     ```python
     def update_diversity_metrics(episode_topics: List[str], session) -> Dict
     ```
  4. Load or initialize metrics node:
     - Query existing EcologicalMetrics node
     - Create if doesn't exist
  5. Update topic distribution:
     - Increment count for each topic
     - Recalculate percentages
  6. Calculate diversity score:
     - Use Shannon entropy formula
     - Higher entropy = more diverse
  7. Calculate balance score:
     - Measure standard deviation of topic frequencies
     - Lower deviation = more balanced
  8. Store updated metrics:
     - Update EcologicalMetrics node
     - Include timestamp
  9. Add trend tracking:
     - Store historical diversity scores
     - Detect if diversity increasing/decreasing
- Validation:
  - Process episodes with varied topics, verify high diversity
  - Process episodes with single topic, verify low diversity
  - Check metrics update incrementally

### Task 3.4: Create Analysis Orchestrator
- [ ] Task description: Coordinate all analysis components during ingestion
- Purpose: Run all knowledge discovery analyses when new episodes are added
- Steps:
  1. Use context7 MCP tool to review orchestration patterns
  2. Create new file `src/analysis/analysis_orchestrator.py`
  3. Implement orchestration function:
     ```python
     def run_knowledge_discovery(episode_id: str, session)
     ```
  4. Extract episode data needed for analysis:
     - Topics, entities, segments
  5. Call each analysis component:
     - Gap detection for affected clusters
     - Missing link analysis for new entities
     - Diversity metrics update
  6. Add error handling:
     - Continue if one analysis fails
     - Log failures but don't block pipeline
  7. Integrate into main ingestion pipeline:
     - Call after episode stored in Neo4j
     - Make it optional via configuration
  8. Add performance logging:
     - Track time for each analysis
     - Log if analyses take too long
- Validation:
  - Process new episode and verify all analyses run
  - Check that failures in one analysis don't stop others
  - Verify minimal performance impact

## Phase 4: Report Generation

### Task 4.1: Create Report Generation Module
- [ ] Task description: Build module to generate content intelligence reports
- Purpose: Create valuable insights for podcasters
- Steps:
  1. Use context7 MCP tool to review report generation patterns
  2. Create new file `src/reports/content_intelligence.py`
  3. Implement gap analysis report:
     ```python
     def generate_gap_report(podcast_name: str, session) -> Dict
     ```
     - Query StructuralGap nodes
     - Format with topics, scores, bridge suggestions
  4. Implement missing links report:
     - Query MissingLink nodes
     - Group by entity types
     - Include connection suggestions
  5. Implement diversity dashboard:
     - Query EcologicalMetrics
     - Show topic distribution
     - Include diversity trends
  6. Create combined intelligence report:
     - Top gaps to explore
     - High-value missing connections
     - Diversity insights
  7. Add export formats:
     - JSON for API consumption
     - Markdown for human reading
     - CSV for spreadsheet analysis
- Validation:
  - Generate reports for test podcast
  - Verify reports contain actionable insights
  - Check all export formats work

### Task 4.2: Add Report CLI Commands
- [ ] Task description: Expose report generation through CLI
- Purpose: Allow users to generate reports on demand
- Steps:
  1. Use context7 MCP tool to review CLI patterns
  2. Open CLI module file
  3. Add report generation commands:
     - `generate-gap-report --podcast "name"`
     - `generate-content-intelligence --podcast "name"`
  4. Wire commands to report module
  5. Add output options:
     - `--format json|markdown|csv`
     - `--output filename`
  6. Add filtering options:
     - `--min-gap-score 0.7`
     - `--episode-range last-50`
  7. Add help documentation
- Validation:
  - Run CLI commands and verify reports generate
  - Test different format options
  - Verify filtering works correctly

## Success Criteria

1. **VTT Metadata Extraction**
   - [ ] YouTube URLs extracted from VTT files and stored in Neo4j
   - [ ] Metadata parsing works for both JSON and human-readable formats
   - [ ] Backward compatible with VTT files lacking metadata

2. **YouTube URL Discovery**
   - [ ] Missing YouTube URLs automatically discovered
   - [ ] Search accuracy >80% for known podcast episodes
   - [ ] Rate limiting prevents API quota issues

3. **Knowledge Discovery**
   - [ ] Gap detection identifies topic clusters with low connectivity
   - [ ] Missing links found between frequently mentioned but unconnected entities
   - [ ] Diversity metrics track knowledge balance over time

4. **Report Generation**
   - [ ] Podcasters can generate actionable content intelligence reports
   - [ ] Reports highlight specific content opportunities
   - [ ] Multiple export formats support different use cases

## Technology Requirements

All components use existing approved technologies:
- Python (existing language)
- Neo4j (existing database)
- YouTube Data API v3 (already used in transcriber)
- No new frameworks or databases required

## Validation Strategy

Each phase includes comprehensive validation:
1. Unit tests for individual components
2. Integration tests for end-to-end flows
3. Manual testing with real podcast data
4. Performance validation for incremental updates