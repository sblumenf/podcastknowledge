# InfraNodus-Inspired Knowledge Enhancement Implementation Plan

## Overview

This document provides an extremely detailed, step-by-step implementation plan for enhancing the podcast knowledge extraction system with five key features inspired by InfraNodus's approach to knowledge graph analysis. These enhancements will significantly improve the depth and utility of extracted knowledge by analyzing not just what is said, but the structural relationships, gaps, and patterns in the discourse.

**Core Philosophy**: Knowledge value comes from understanding relationships, gaps, and evolution of concepts, not just extracting entities and facts.

**Implementation Note**: When implementing these enhancements, Claude Code should reference https://infranodus.com/docs to understand the theoretical foundations of these concepts.

## Enhancement 1: Multi-Factor Importance Scoring

### Purpose
Replace the current simple importance scoring (1-10 scale) with a sophisticated multi-factor system that considers frequency, structural position, semantic centrality, discourse function, and temporal dynamics. This will help identify truly important concepts that shape discussions, even if mentioned briefly.

### Detailed Implementation Tasks

#### 1.1 Create Multi-Factor Importance Model
- [ ] **Task**: Create new file `src/processing/importance_scoring.py`
- [ ] **Purpose**: Centralize all importance calculation logic in one module
- [ ] **What to implement**:
  ```python
  class ImportanceScorer:
      """
      Calculates multi-factor importance scores for entities based on:
      1. Frequency: How often mentioned (normalized by episode length)
      2. Structural Centrality: Position in knowledge graph
      3. Semantic Centrality: Embedding-based importance
      4. Discourse Function: Role in conversation (introduction, elaboration, conclusion)
      5. Temporal Dynamics: When and how concepts are introduced
      6. Cross-Reference Score: How often other concepts reference this one
      """
  ```
- [ ] **Specific instruction**: Import necessary dependencies including networkx for graph metrics, numpy for calculations, and existing models from src/core/models.py

#### 1.2 Implement Frequency Factor Calculation
- [ ] **Task**: Add method `calculate_frequency_factor(entity_mentions: List[Dict], episode_duration: float) -> float`
- [ ] **Purpose**: Calculate normalized frequency score that accounts for episode length
- [ ] **What it does**:
  - Count total mentions of entity across all segments
  - Normalize by episode duration (mentions per minute)
  - Apply logarithmic scaling to prevent frequency dominance
  - Return score between 0 and 1
- [ ] **Implementation details**:
  ```python
  def calculate_frequency_factor(self, entity_mentions: List[Dict], episode_duration: float) -> float:
      """
      Example: If "AI" is mentioned 50 times in a 60-minute podcast = 0.83 mentions/min
      Apply log scaling: log(1 + 0.83) / log(1 + max_expected_frequency)
      Where max_expected_frequency might be 2 mentions/min
      """
  ```

#### 1.3 Implement Structural Centrality Factor
- [ ] **Task**: Add method `calculate_structural_centrality(entity_id: str, graph: nx.Graph) -> float`
- [ ] **Purpose**: Measure how central the entity is in the knowledge structure
- [ ] **What it calculates**:
  - Betweenness centrality: How often this entity bridges other concepts
  - Degree centrality: How many connections it has
  - Eigenvector centrality: Connection to other important entities
  - Combine into weighted score
- [ ] **Specific instruction**: Use NetworkX library methods but catch exceptions for disconnected nodes

#### 1.4 Implement Semantic Centrality Factor
- [ ] **Task**: Add method `calculate_semantic_centrality(entity_embedding: np.ndarray, all_embeddings: List[np.ndarray]) -> float`
- [ ] **Purpose**: Determine semantic importance based on embedding relationships
- [ ] **What it does**:
  - Calculate average cosine similarity to all other entities
  - Identify if entity is semantically central or peripheral
  - Higher scores for entities that relate to many others
- [ ] **Implementation note**: Handle edge case where embeddings might be None

#### 1.5 Implement Discourse Function Analysis
- [ ] **Task**: Add method `analyze_discourse_function(entity_mentions: List[Dict], segments: List[Dict]) -> Dict[str, float]`
- [ ] **Purpose**: Understand the role of entity in conversation structure
- [ ] **What to track**:
  - **Introduction score**: First appearance in first 20% of episode
  - **Development score**: Mentioned across multiple segments
  - **Conclusion score**: Appears in final 20% of episode
  - **Bridge score**: Connects different topics/segments
- [ ] **Output format**:
  ```python
  {
      "introduction_role": 0.8,  # Strong introduction
      "development_role": 0.6,   # Moderate development
      "conclusion_role": 0.2,    # Weak conclusion presence
      "bridge_role": 0.9         # Strong bridging function
  }
  ```

#### 1.6 Implement Temporal Dynamics Analysis
- [ ] **Task**: Add method `analyze_temporal_dynamics(entity_mentions: List[Dict], segments: List[Dict]) -> Dict[str, float]`
- [ ] **Purpose**: Analyze how entity importance changes over time
- [ ] **What to calculate**:
  - **Recency weight**: Recent mentions weighted higher
  - **Persistence score**: Sustained discussion vs one-time mention
  - **Peak influence**: Maximum importance at any point
  - **Momentum**: Increasing or decreasing importance
- [ ] **Specific calculation**: Use exponential decay for recency: `weight = exp(-alpha * time_since_mention)`

#### 1.7 Implement Cross-Reference Analysis
- [ ] **Task**: Add method `calculate_cross_reference_score(entity_id: str, all_entities: List[Entity], insights: List[Insight]) -> float`
- [ ] **Purpose**: Measure how often other entities/insights reference this concept
- [ ] **What to check**:
  - Count mentions in other entity descriptions
  - Count appearances in insight descriptions
  - Weight by importance of referencing entities
- [ ] **Note**: This creates a "PageRank-like" importance propagation

#### 1.8 Create Composite Score Calculator
- [ ] **Task**: Add method `calculate_composite_importance(all_factors: Dict[str, float], weights: Dict[str, float] = None) -> float`
- [ ] **Purpose**: Combine all factors into final importance score
- [ ] **Default weights**:
  ```python
  {
      "frequency": 0.15,
      "structural_centrality": 0.25,
      "semantic_centrality": 0.20,
      "discourse_function": 0.20,
      "temporal_dynamics": 0.10,
      "cross_reference": 0.10
  }
  ```
- [ ] **Output**: Single importance score 0-1 with factor breakdown

#### 1.9 Integrate with Entity Extraction
- [ ] **Task**: Modify `src/processing/extraction.py` to use new importance scoring
- [ ] **Where to modify**: In `_extract_entities_large_context` and `_extract_entities` methods
- [ ] **What to change**:
  - After LLM extraction, before returning entities
  - Create ImportanceScorer instance
  - Calculate multi-factor importance for each entity
  - Store both composite score and factor breakdown
- [ ] **Storage format**: Add to entity data:
  ```python
  entity["importance_score"] = composite_score
  entity["importance_factors"] = {
      "frequency": 0.7,
      "structural_centrality": 0.8,
      # ... all factors
  }
  ```

#### 1.10 Update Entity Model
- [ ] **Task**: Modify `Entity` class in `src/core/models.py`
- [ ] **Add fields**:
  ```python
  importance_score: float = Field(0.5, description="Multi-factor importance 0-1")
  importance_factors: Dict[str, float] = Field(default_factory=dict, description="Breakdown of importance factors")
  discourse_roles: Dict[str, float] = Field(default_factory=dict, description="Entity's discourse functions")
  ```
- [ ] **Ensure backward compatibility**: Keep original importance field, map to frequency factor

#### 1.11 Create Importance Visualization Data
- [ ] **Task**: Add method `generate_importance_visualization_data(entities: List[Entity]) -> Dict`
- [ ] **Purpose**: Prepare data for future visualization of importance factors
- [ ] **Output structure**:
  ```python
  {
      "entities": [...],
      "importance_distribution": {...},
      "factor_correlations": {...},
      "top_by_factor": {
          "frequency": [...],
          "centrality": [...],
          # etc
      }
  }
  ```

#### 1.12 Add Importance-Based Filtering
- [ ] **Task**: Add utility methods for filtering entities by importance
- [ ] **Methods to add**:
  - `get_top_entities_by_importance(entities, top_n=10)`
  - `filter_entities_by_importance_threshold(entities, threshold=0.5)`
  - `get_entities_by_factor(entities, factor_name, top_n=5)`
- [ ] **Purpose**: Enable smart filtering based on multi-factor importance

#### 1.13 Write Comprehensive Tests
- [ ] **Task**: Create `tests/processing/test_importance_scoring.py`
- [ ] **Test cases**:
  - Each factor calculation independently
  - Composite score calculation with various weights
  - Edge cases (single mention, no connections, etc.)
  - Integration with entity extraction
- [ ] **Use fixtures**: Create test entities with known importance characteristics

## Enhancement 2: Enhanced Structural Gap Analysis

### Purpose
Extend the existing basic gap detection to analyze the semantic distance between disconnected communities, identify potential bridging concepts, and score gaps by their "bridgeability". This helps users discover unexplored connections between topics.

### Detailed Implementation Tasks

#### 2.1 Enhance Gap Analysis Class
- [ ] **Task**: Extend `GraphAnalyzer` class in `src/processing/graph_analysis.py`
- [ ] **Current method**: `identify_structural_gaps()` - keep this
- [ ] **Add new class**: `EnhancedGapAnalyzer` as inner class
- [ ] **Purpose**: Separate enhanced gap analysis while maintaining backward compatibility

#### 2.2 Implement Semantic Distance Calculator
- [ ] **Task**: Add method `calculate_semantic_distance(community1_entities: List[Entity], community2_entities: List[Entity]) -> float`
- [ ] **Purpose**: Measure how semantically different two disconnected communities are
- [ ] **Algorithm**:
  1. Get embeddings for all entities in each community
  2. Calculate centroid embedding for each community
  3. Compute cosine distance between centroids
  4. Also calculate min/max/avg pairwise distances
- [ ] **Return format**:
  ```python
  {
      "centroid_distance": 0.73,
      "min_pairwise_distance": 0.45,
      "max_pairwise_distance": 0.92,
      "avg_pairwise_distance": 0.68
  }
  ```

#### 2.3 Implement Potential Bridge Finder
- [ ] **Task**: Add method `find_potential_bridges(gap: Dict, all_entities: List[Entity], top_n: int = 5) -> List[Dict]`
- [ ] **Purpose**: Identify concepts that could connect disconnected communities
- [ ] **Algorithm**:
  1. For each entity not in either community
  2. Calculate semantic similarity to both communities
  3. Score bridging potential: `min(sim_to_comm1, sim_to_comm2) * 2`
  4. Rank and return top candidates
- [ ] **Output format**:
  ```python
  {
      "entity": entity_object,
      "bridge_score": 0.82,
      "similarity_to_community1": 0.85,
      "similarity_to_community2": 0.79,
      "explanation": "This concept relates to both AI and healthcare aspects"
  }
  ```

#### 2.4 Implement Gap Bridgeability Scorer
- [ ] **Task**: Add method `calculate_gap_bridgeability(gap: Dict, semantic_distance: Dict, potential_bridges: List[Dict]) -> float`
- [ ] **Purpose**: Score how easily a gap could be bridged
- [ ] **Factors to consider**:
  - Semantic distance (closer = more bridgeable)
  - Number of quality bridge candidates
  - Conceptual coherence of communities
  - Size differential between communities
- [ ] **Formula**: 
  ```python
  bridgeability = (1 - semantic_distance) * bridge_quality * size_balance * coherence_factor
  ```

#### 2.5 Implement Conceptual Path Finder
- [ ] **Task**: Add method `find_conceptual_paths(entity1: Entity, entity2: Entity, max_hops: int = 3) -> List[List[Entity]]`
- [ ] **Purpose**: Find potential conceptual paths between disconnected entities
- [ ] **Algorithm**:
  1. Use embedding space to find intermediate concepts
  2. Build paths through semantic similarity
  3. Validate paths don't go through unrelated concepts
  4. Return top 3 most coherent paths

#### 2.6 Create Gap Analysis Report Structure
- [ ] **Task**: Add method `generate_enhanced_gap_report(gap: Dict) -> Dict`
- [ ] **Purpose**: Create comprehensive gap analysis data
- [ ] **Report structure**:
  ```python
  {
      "gap_id": "community_3_to_7",
      "semantic_analysis": {
          "distance_metrics": {...},
          "interpretation": "These communities are moderately distant"
      },
      "bridge_analysis": {
          "potential_bridges": [...],
          "bridgeability_score": 0.72,
          "recommended_connections": [...]
      },
      "exploration_suggestions": [
          "Consider discussing how AI impacts healthcare costs",
          "Explore connection between technology adoption and patient outcomes"
      ]
  }
  ```

#### 2.7 Implement Gap Evolution Tracking
- [ ] **Task**: Add method `track_gap_evolution(current_gaps: List[Dict], previous_gaps: List[Dict]) -> Dict`
- [ ] **Purpose**: Track how gaps change as more content is processed
- [ ] **What to track**:
  - New gaps emerged
  - Gaps that were bridged
  - Gaps that grew larger
  - Stability of gap structure

#### 2.8 Add Intelligent Gap Prioritization
- [ ] **Task**: Add method `prioritize_gaps(gaps: List[Dict]) -> List[Dict]`
- [ ] **Purpose**: Rank gaps by their importance and exploration value
- [ ] **Prioritization factors**:
  - Size of disconnected communities
  - Importance of entities in communities
  - Bridgeability score
  - Novelty of potential connections
- [ ] **Add priority score and rank to each gap**

#### 2.9 Integrate with Main Processing
- [ ] **Task**: Modify `enhance_with_graph_analysis` in `src/seeding/orchestrator.py`
- [ ] **Where to add**: After basic gap identification
- [ ] **What to add**:
  ```python
  # After identifying basic gaps
  enhanced_gaps = []
  for gap in structural_gaps:
      enhanced_gap = analyzer.enhance_gap_analysis(gap)
      enhanced_gaps.append(enhanced_gap)
  
  # Store enhanced gap data
  episode_enhancements["enhanced_structural_gaps"] = enhanced_gaps
  ```

#### 2.10 Create Gap Visualization Data
- [ ] **Task**: Add method `prepare_gap_visualization_data(enhanced_gaps: List[Dict]) -> Dict`
- [ ] **Purpose**: Structure data for future gap visualization
- [ ] **Include**:
  - Community positions and sizes
  - Bridge candidate positions
  - Semantic distance gradients
  - Suggested connection paths

## Enhancement 3: Discourse Flow Tracking

### Purpose
Track how concepts flow through conversations, identifying introduction points, development arcs, and resolution patterns. This helps users understand the logical progression and narrative structure of complex discussions.

### Detailed Implementation Tasks

#### 3.1 Create Discourse Flow Tracker
- [ ] **Task**: Create new file `src/processing/discourse_flow.py`
- [ ] **Purpose**: Centralize all discourse flow analysis
- [ ] **Main class structure**:
  ```python
  class DiscourseFlowTracker:
      """
      Tracks the temporal flow of concepts through podcast conversations.
      Identifies introduction, development, peak, and resolution phases.
      Maps concept trajectories and narrative patterns.
      """
  ```

#### 3.2 Implement Concept Timeline Builder
- [ ] **Task**: Add method `build_concept_timeline(segments: List[Segment], entities: List[Entity]) -> Dict[str, List[Dict]]`
- [ ] **Purpose**: Create timeline of when each concept appears
- [ ] **For each entity, track**:
  ```python
  {
      "entity_id": "uuid",
      "timeline": [
          {
              "segment_index": 0,
              "timestamp": 120.5,
              "mention_type": "introduction",  # introduction/development/callback/conclusion
              "context_density": 0.8,  # How much discussion around it
              "speaker": "Host"
          }
      ]
  }
  ```

#### 3.3 Implement Concept Lifecycle Analyzer
- [ ] **Task**: Add method `analyze_concept_lifecycle(concept_timeline: List[Dict]) -> Dict`
- [ ] **Purpose**: Identify lifecycle phases of each concept
- [ ] **Lifecycle phases**:
  - **Introduction**: First meaningful mention
  - **Elaboration**: Expanded discussion
  - **Peak**: Most intensive discussion
  - **Integration**: Connected to other concepts
  - **Resolution**: Final state or conclusion
- [ ] **Output format**:
  ```python
  {
      "lifecycle_pattern": "introduce-develop-integrate",
      "introduction_segment": 3,
      "peak_segment": 8,
      "total_duration": 1240.5,  # seconds
      "development_intensity": 0.75
  }
  ```

#### 3.4 Implement Discourse Pattern Detector
- [ ] **Task**: Add method `detect_discourse_patterns(concept_timelines: Dict[str, List]) -> List[Dict]`
- [ ] **Purpose**: Identify common discourse patterns
- [ ] **Patterns to detect**:
  - **Linear progression**: A→B→C→D
  - **Circular return**: A→B→C→A
  - **Hub and spoke**: Central concept with radiating discussions
  - **Parallel threads**: Multiple concepts developed simultaneously
  - **Convergence**: Multiple concepts merge into one
- [ ] **Include pattern confidence scores**

#### 3.5 Implement Concept Momentum Calculator
- [ ] **Task**: Add method `calculate_concept_momentum(timeline: List[Dict], window_size: int = 3) -> List[float]`
- [ ] **Purpose**: Measure how concept importance changes over time
- [ ] **Algorithm**:
  1. For each time window, calculate mention density
  2. Compute rate of change between windows
  3. Identify acceleration/deceleration points
  4. Mark momentum shifts

#### 3.6 Implement Narrative Arc Detector
- [ ] **Task**: Add method `detect_narrative_arcs(segments: List[Segment], concept_timelines: Dict) -> Dict`
- [ ] **Purpose**: Identify story-like structures in discussions
- [ ] **Arc types to detect**:
  - **Problem-solution**: Issue introduced, explored, resolved
  - **Journey**: Sequential exploration of related concepts
  - **Debate**: Contrasting viewpoints presented
  - **Discovery**: Unknown to known progression
- [ ] **Output**: Arc type, key turning points, resolution status

#### 3.7 Implement Concept Interaction Tracker
- [ ] **Task**: Add method `track_concept_interactions(timelines: Dict[str, List], segments: List[Segment]) -> List[Dict]`
- [ ] **Purpose**: Track when concepts interact or merge
- [ ] **Interaction types**:
  - **Co-introduction**: Concepts introduced together
  - **Causal link**: One concept leads to another
  - **Synthesis**: Concepts merge into new idea
  - **Contrast**: Concepts presented as alternatives
- [ ] **Track interaction strength and type**

#### 3.8 Implement Discourse Transition Analyzer
- [ ] **Task**: Add method `analyze_transitions(segments: List[Segment], concept_timelines: Dict) -> List[Dict]`
- [ ] **Purpose**: Identify how conversation moves between topics
- [ ] **Transition types**:
  - **Smooth**: Natural progression
  - **Abrupt**: Sudden topic change
  - **Bridged**: Explicit connection made
  - **Returned**: Coming back to earlier topic
- [ ] **Include transition quality scores**

#### 3.9 Create Flow Visualization Data
- [ ] **Task**: Add method `generate_flow_visualization_data(flow_analysis: Dict) -> Dict`
- [ ] **Purpose**: Prepare data for timeline visualization
- [ ] **Data structure**:
  ```python
  {
      "concept_streams": [...],  # Parallel concept timelines
      "interaction_points": [...],  # Where concepts meet
      "narrative_phases": [...],  # Story structure
      "key_transitions": [...],  # Major topic shifts
      "momentum_data": [...]  # Concept importance over time
  }
  ```

#### 3.10 Integrate with Segment Processing
- [ ] **Task**: Modify `process_episode` in `src/seeding/orchestrator.py`
- [ ] **Where to add**: After entity extraction, before graph storage
- [ ] **Integration code**:
  ```python
  # After extraction
  flow_tracker = DiscourseFlowTracker()
  discourse_flow = flow_tracker.analyze_episode_flow(
      segments=processed_segments,
      entities=extraction_results.entities,
      insights=extraction_results.insights
  )
  
  # Add to episode metadata
  episode_data["discourse_flow"] = discourse_flow
  ```

#### 3.11 Add Flow-Based Entity Enrichment
- [ ] **Task**: Add method `enrich_entities_with_flow_data(entities: List[Entity], flow_analysis: Dict) -> List[Entity]`
- [ ] **Purpose**: Add discourse flow information to entities
- [ ] **Enrichments**:
  - Discourse role (introducer, developer, integrator)
  - Lifecycle phase when most discussed
  - Narrative importance score
  - Transition catalyst score

#### 3.12 Create Flow Summary Generator
- [ ] **Task**: Add method `generate_flow_summary(flow_analysis: Dict) -> str`
- [ ] **Purpose**: Create human-readable summary of discourse flow
- [ ] **Example output**:
  ```
  "The discussion begins with AI ethics, develops through three main phases 
  exploring bias, accountability, and regulation. Key transition at 15:30 
  bridges to practical applications. Circular return to ethics in conclusion."
  ```

## Enhancement 4: Emergent Theme Detection

### Purpose
Identify themes that emerge from the interaction of concepts rather than being explicitly stated. This reveals implicit patterns, underlying messages, and hidden connections that speakers don't directly articulate.

### Detailed Implementation Tasks

#### 4.1 Create Emergent Theme Detector
- [ ] **Task**: Create new file `src/processing/emergent_themes.py`
- [ ] **Purpose**: Detect implicit themes from concept interactions
- [ ] **Main class**:
  ```python
  class EmergentThemeDetector:
      """
      Identifies implicit themes by analyzing concept clusters,
      co-occurrence patterns, and semantic fields.
      Discovers what the conversation is "really about" beyond surface topics.
      """
  ```

#### 4.2 Implement Concept Cluster Analyzer
- [ ] **Task**: Add method `analyze_concept_clusters(entities: List[Entity], co_occurrences: List[Dict]) -> List[Dict]`
- [ ] **Purpose**: Group entities into semantic clusters
- [ ] **Algorithm**:
  1. Build co-occurrence graph
  2. Apply community detection at multiple resolutions
  3. Calculate cluster coherence using embeddings
  4. Filter for significant clusters only
- [ ] **Output**: List of coherent concept clusters with member entities

#### 4.3 Implement Semantic Field Extractor
- [ ] **Task**: Add method `extract_semantic_fields(clusters: List[Dict], entities: List[Entity]) -> List[Dict]`
- [ ] **Purpose**: Identify the semantic field each cluster represents
- [ ] **Process**:
  1. For each cluster, get all entity embeddings
  2. Find the semantic centroid
  3. Identify closest abstract concepts in embedding space
  4. Generate field description using LLM
- [ ] **Output format**:
  ```python
  {
      "cluster_id": "cluster_1",
      "semantic_field": "technological disruption",
      "confidence": 0.85,
      "key_concepts": ["AI", "automation", "job displacement"],
      "peripheral_concepts": ["retraining", "UBI"]
  }
  ```

#### 4.4 Implement Cross-Cluster Pattern Detector
- [ ] **Task**: Add method `detect_cross_cluster_patterns(clusters: List[Dict], insights: List[Insight]) -> List[Dict]`
- [ ] **Purpose**: Find patterns that span multiple concept clusters
- [ ] **Patterns to detect**:
  - **Causal chains**: Cluster A → affects → Cluster B
  - **Tensions**: Opposing clusters in dialogue
  - **Dependencies**: Cluster A requires Cluster B
  - **Emergence**: Clusters combine to form new concept
- [ ] **Include pattern strength and evidence**

#### 4.5 Implement Implicit Message Extractor
- [ ] **Task**: Add method `extract_implicit_messages(semantic_fields: List[Dict], discourse_flow: Dict) -> List[Dict]`
- [ ] **Purpose**: Identify messages not explicitly stated
- [ ] **Analysis approach**:
  1. Look for recurring semantic patterns
  2. Analyze emotional undertones of clusters
  3. Identify value judgments in concept relationships
  4. Detect unstated assumptions
- [ ] **Output format**:
  ```python
  {
      "implicit_message": "Technology adoption requires cultural change",
      "supporting_evidence": [...],
      "confidence": 0.78,
      "interpretation": "While discussing AI, speakers repeatedly link to organizational culture"
  }
  ```

#### 4.6 Implement Theme Emergence Scorer
- [ ] **Task**: Add method `score_theme_emergence(theme: Dict, explicit_topics: List[str]) -> float`
- [ ] **Purpose**: Measure how "emergent" vs explicit a theme is
- [ ] **Scoring factors**:
  - Absence from explicit topic list
  - Distributed across multiple segments
  - Arises from concept interactions
  - Not directly named but repeatedly implied
- [ ] **Score range**: 0 (explicit) to 1 (fully emergent)

#### 4.7 Implement Metaphor and Analogy Detector
- [ ] **Task**: Add method `detect_metaphorical_themes(segments: List[Segment], entities: List[Entity]) -> List[Dict]`
- [ ] **Purpose**: Identify recurring metaphors that reveal themes
- [ ] **Process**:
  1. Identify analogical language patterns
  2. Track metaphor families (e.g., journey, war, growth)
  3. Link metaphors to concept clusters
  4. Extract thematic implications
- [ ] **Example**: "Multiple 'battle' metaphors suggest underlying theme of competition"

#### 4.8 Implement Theme Evolution Tracker
- [ ] **Task**: Add method `track_theme_evolution(emergent_themes: List[Dict], segments: List[Segment]) -> Dict`
- [ ] **Purpose**: Track how emergent themes develop through conversation
- [ ] **Track**:
  - When theme first emerges
  - How it strengthens or weakens
  - Which concepts contribute to it
  - Whether it gets explicitly acknowledged

#### 4.9 Implement Theme Validation
- [ ] **Task**: Add method `validate_emergent_themes(themes: List[Dict], segments: List[Segment], insights: List[Insight]) -> List[Dict]`
- [ ] **Purpose**: Ensure detected themes are genuine, not artifacts
- [ ] **Validation checks**:
  - Multiple independent evidence sources
  - Coherence across conversation
  - Not contradicted by explicit statements
  - Statistical significance of patterns

#### 4.10 Create Theme Hierarchy Builder
- [ ] **Task**: Add method `build_theme_hierarchy(emergent_themes: List[Dict]) -> Dict`
- [ ] **Purpose**: Organize themes into hierarchical structure
- [ ] **Hierarchy levels**:
  - Meta-themes: Overarching patterns
  - Primary themes: Main emergent topics
  - Sub-themes: Specific aspects
  - Micro-themes: Detailed patterns
- [ ] **Include parent-child relationships**

#### 4.11 Integrate with Main Processing
- [ ] **Task**: Modify extraction pipeline to include emergent themes
- [ ] **Where**: In `orchestrator.py`, after entity extraction
- [ ] **Integration**:
  ```python
  # After entity and insight extraction
  theme_detector = EmergentThemeDetector()
  emergent_themes = theme_detector.detect_themes(
      entities=extraction_results.entities,
      insights=extraction_results.insights,
      segments=processed_segments,
      co_occurrences=co_occurrence_data
  )
  
  # Store as separate node type
  graph_provider.store_emergent_themes(episode_id, emergent_themes)
  ```

#### 4.12 Create Theme Summary Generator
- [ ] **Task**: Add method `generate_theme_summary(emergent_themes: List[Dict]) -> Dict`
- [ ] **Purpose**: Create interpretable summary of emergent themes
- [ ] **Output format**:
  ```python
  {
      "major_themes": [
          {
              "theme": "Innovation requires accepting failure",
              "emergence_score": 0.89,
              "supporting_concepts": [...],
              "interpretation": "..."
          }
      ],
      "theme_relationships": [...],
      "overall_narrative": "The conversation implicitly explores..."
  }
  ```

## Enhancement 5: Within-Episode Discourse Flow

### Purpose
Track concept progression within individual episodes, understanding how ideas develop, transform, and resolve throughout a single conversation. This is a focused version of Enhancement 3, specifically designed to work within the current episode-by-episode processing architecture.

### Detailed Implementation Tasks

#### 5.1 Create Episode Flow Analyzer
- [ ] **Task**: Create new file `src/processing/episode_flow.py`
- [ ] **Purpose**: Analyze concept flow within single episodes
- [ ] **Note**: This is separate from cross-episode analysis to work within current architecture
- [ ] **Main class**:
  ```python
  class EpisodeFlowAnalyzer:
      """
      Tracks how concepts flow within a single episode.
      Maps introduction, development, and resolution of ideas.
      Works entirely within episode boundaries.
      """
  ```

#### 5.2 Implement Segment Transition Classifier
- [ ] **Task**: Add method `classify_segment_transitions(segments: List[Segment]) -> List[Dict]`
- [ ] **Purpose**: Classify how conversation moves between segments
- [ ] **Transition types**:
  - **Continuation**: Same topic, deeper exploration
  - **Expansion**: Related topic, broadening scope
  - **Pivot**: Shift to new but connected topic
  - **Jump**: Abrupt change to unrelated topic
  - **Return**: Coming back to earlier topic
- [ ] **For each transition, calculate**:
  ```python
  {
      "from_segment": 5,
      "to_segment": 6,
      "transition_type": "expansion",
      "semantic_similarity": 0.73,
      "explicit_marker": "Speaking of which...",
      "smoothness_score": 0.85
  }
  ```

#### 5.3 Implement Concept Introduction Tracker
- [ ] **Task**: Add method `track_concept_introductions(segments: List[Segment], entities: List[Entity]) -> Dict[str, Dict]`
- [ ] **Purpose**: Identify how concepts are introduced
- [ ] **Introduction types**:
  - **Planned**: Announced introduction ("Today we'll discuss...")
  - **Organic**: Natural emergence from discussion
  - **Responsive**: Introduced in response to question
  - **Tangential**: Side mention that develops
- [ ] **Track for each concept**:
  ```python
  {
      "entity_id": {
          "introduction_segment": 3,
          "introduction_type": "organic",
          "introduction_context": "Emerged from discussion of...",
          "initial_depth": "surface",  # surface/moderate/deep
          "introducer": "Guest"
      }
  }
  ```

#### 5.4 Implement Concept Development Mapper
- [ ] **Task**: Add method `map_concept_development(entity: Entity, segments: List[Segment]) -> Dict`
- [ ] **Purpose**: Track how each concept develops through episode
- [ ] **Development phases**:
  - **Introduction**: First mention
  - **Elaboration**: Detailed explanation
  - **Application**: Practical examples
  - **Challenge**: Questions or counterpoints
  - **Integration**: Connection to other concepts
  - **Resolution**: Final state or conclusion
- [ ] **Create development timeline with phase markers**

#### 5.5 Implement Conversation Momentum Analyzer
- [ ] **Task**: Add method `analyze_conversation_momentum(segments: List[Segment], window_size: int = 5) -> List[Dict]`
- [ ] **Purpose**: Track energy and pace of discussion
- [ ] **Momentum factors**:
  - New concept introduction rate
  - Speaker turn frequency
  - Question density
  - Insight generation rate
  - Emotional intensity
- [ ] **Output momentum curve with annotations**

#### 5.6 Implement Topic Depth Tracker
- [ ] **Task**: Add method `track_topic_depth(segments: List[Segment], entities: List[Entity]) -> Dict[str, float]`
- [ ] **Purpose**: Measure how deeply each topic is explored
- [ ] **Depth indicators**:
  - Time spent on topic
  - Number of related concepts introduced
  - Level of detail in explanations
  - Examples and evidence provided
  - Questions answered vs raised
- [ ] **Return depth score 0-1 for each major topic**

#### 5.7 Implement Circular Reference Detector
- [ ] **Task**: Add method `detect_circular_references(concept_timeline: Dict[str, List]) -> List[Dict]`
- [ ] **Purpose**: Find when conversation returns to earlier concepts
- [ ] **For each circular reference**:
  ```python
  {
      "concept": "AI ethics",
      "first_mention": {"segment": 3, "timestamp": 180.5},
      "return_mention": {"segment": 15, "timestamp": 1200.3},
      "evolution": "Initial concern → Explored solutions → Returned with new perspective",
      "closure_achieved": True
  }
  ```

#### 5.8 Implement Concept Resolution Analyzer
- [ ] **Task**: Add method `analyze_concept_resolution(concepts: Dict[str, Dict], final_segments: List[Segment]) -> Dict[str, Dict]`
- [ ] **Purpose**: Determine if/how concepts are resolved
- [ ] **Resolution types**:
  - **Answered**: Question fully addressed
  - **Partial**: Some aspects resolved
  - **Deferred**: Explicitly left for future
  - **Abandoned**: Dropped without resolution
  - **Transformed**: Evolved into different question
- [ ] **Include resolution quality score**

#### 5.9 Create Episode Flow Summary
- [ ] **Task**: Add method `generate_episode_flow_summary(flow_analysis: Dict) -> Dict`
- [ ] **Purpose**: Create structured summary of episode flow
- [ ] **Summary includes**:
  ```python
  {
      "opening_concepts": [...],
      "core_developments": [...],
      "key_transitions": [...],
      "unresolved_threads": [...],
      "circular_themes": [...],
      "flow_pattern": "linear_progression",  # or spiral/branching/etc
      "narrative_coherence": 0.82
  }
  ```

#### 5.10 Implement Speaker Contribution Flow
- [ ] **Task**: Add method `analyze_speaker_contribution_flow(segments: List[Segment]) -> Dict[str, Dict]`
- [ ] **Purpose**: Track how each speaker contributes to flow
- [ ] **For each speaker track**:
  - Concept introduction rate
  - Question vs statement ratio
  - Topic transition initiation
  - Flow disruption vs continuation
  - Role in concept development

#### 5.11 Add Flow Metrics to Storage
- [ ] **Task**: Modify entity and episode storage to include flow data
- [ ] **Entity additions**:
  ```python
  entity["flow_data"] = {
      "introduction_point": 0.15,  # Position in episode (0-1)
      "development_duration": 450.2,  # seconds
      "peak_discussion": 0.45,  # Position of peak
      "resolution_status": "partial"
  }
  ```
- [ ] **Episode additions**:
  ```python
  episode["discourse_flow"] = {
      "pattern": "problem_solution",
      "key_transitions": [...],
      "flow_quality": 0.78
  }
  ```

#### 5.12 Create Flow-Based Segment Importance
- [ ] **Task**: Add method `calculate_segment_flow_importance(segment: Segment, flow_analysis: Dict) -> float`
- [ ] **Purpose**: Score segment importance based on flow role
- [ ] **High importance for segments that**:
  - Introduce major concepts
  - Contain key transitions
  - Achieve resolutions
  - Bridge disparate topics
  - Contain flow turning points

## Testing and Validation Plan

### Test Data Requirements
- [ ] **Create diverse test episodes**:
  - Technical podcast with linear progression
  - Interview with organic flow
  - Debate with opposing viewpoints
  - Educational content with structured flow
  - Conversational podcast with tangential discussions

### Integration Testing
- [ ] **Test each enhancement independently first**
- [ ] **Test interactions between enhancements**
- [ ] **Verify no performance degradation**
- [ ] **Ensure backward compatibility**

### Validation Metrics
- [ ] **Importance scoring**: Compare with human-annotated importance
- [ ] **Gap analysis**: Validate bridge suggestions make sense
- [ ] **Flow tracking**: Check against manual flow annotation
- [ ] **Theme detection**: Verify themes with content experts
- [ ] **Episode flow**: Ensure captures real conversation dynamics

## Implementation Notes for Claude Code

1. **Start with Enhancement 1** (Multi-Factor Importance) as it enhances existing functionality
2. **Test thoroughly** after each enhancement before moving to next
3. **Preserve all existing functionality** - these are additions, not replacements
4. **Use existing models and patterns** in the codebase for consistency
5. **Reference InfraNodus documentation** at https://infranodus.com/docs for theoretical background
6. **Focus on practical value** - each enhancement should clearly benefit podcast listeners
7. **Document all new methods** with clear docstrings explaining purpose and usage
8. **Add logging** for debugging and monitoring enhancement performance
9. **Consider memory usage** - these enhancements analyze more data
10. **Create examples** showing how each enhancement improves knowledge extraction

## Success Criteria

Each enhancement is complete when:
- [ ] All code tasks are implemented
- [ ] Unit tests pass with >90% coverage
- [ ] Integration tests show enhancement working with real podcast data
- [ ] Performance impact is <20% on processing time
- [ ] Documentation is complete
- [ ] Enhancement provides clear value in test examples