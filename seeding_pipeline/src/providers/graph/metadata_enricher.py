"""
Metadata preservation layer for schemaless extraction.

This module adds metadata to extracted nodes that SimpleKGPipeline doesn't provide,
ensuring all context from the current system is preserved in the schemaless approach.

JUSTIFICATION: SimpleKGPipeline extracts entities and relationships but doesn't:
- Add temporal metadata (when something was mentioned)
- Include source tracking (which episode/podcast/segment)
- Generate extraction metadata (timestamp, confidence scores)
- Create vector embeddings for similarity search
- Preserve segment-level context

EVIDENCE: Phase 1 testing showed extracted nodes lack essential metadata for:
- Temporal queries ("What was discussed in minute 15?")
- Source attribution ("Which episode mentioned AI?")
- Confidence filtering ("Show high-confidence entities only")
- Similarity search (no embeddings)

REMOVAL CRITERIA: This component can be removed if SimpleKGPipeline adds:
- Automatic metadata preservation from source documents
- Built-in temporal and source tracking
- Confidence scoring for extractions
- Automatic embedding generation

IMPORTANCE: Each metadata field serves a specific purpose:
- timestamps: Enable time-based navigation and analysis
- source_metadata: Track provenance and enable filtering
- confidence: Allow quality-based filtering
- embeddings: Enable semantic search and clustering
"""

import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from dataclasses import dataclass

from src.utils.component_tracker import track_component_impact, ComponentContribution, get_tracker
from src.core.models import Segment

logger = logging.getLogger(__name__)


@dataclass
class MetadataEnrichmentConfig:
    """Configuration for metadata enrichment."""
    add_timestamps: bool = True
    add_source_metadata: bool = True
    add_extraction_metadata: bool = True
    add_embeddings: bool = True
    add_confidence_scores: bool = True
    add_segment_context: bool = True
    minimal_mode: bool = False  # Only essential metadata
    full_mode: bool = True  # All available metadata
    dry_run: bool = False  # Preview enrichment without applying


class MetadataEnricher:
    """Alias for SchemalessMetadataEnricher for backward compatibility."""
    def __init__(self, *args, **kwargs):
        # Create instance of SchemalessMetadataEnricher
        self._enricher = SchemalessMetadataEnricher(*args, **kwargs)
    
    def __getattr__(self, name):
        # Delegate all attribute access to the actual enricher
        return getattr(self._enricher, name)


class SchemalessMetadataEnricher:
    """
    Enriches extracted nodes with metadata not provided by SimpleKGPipeline.
    
    This class adds temporal information, source tracking, confidence scores,
    and other metadata to ensure feature parity with the fixed-schema system.
    """
    
    def __init__(self, config_or_provider=None):
        """Initialize the metadata enricher with configuration or embedding provider.
        
        Args:
            config_or_provider: Either a MetadataEnrichmentConfig object or an embedding provider
                               (for backward compatibility with tests)
        """
        # Handle both config object and embedding provider for compatibility
        if config_or_provider is None:
            self.config = MetadataEnrichmentConfig()
            self.embedding_provider = None
        elif isinstance(config_or_provider, MetadataEnrichmentConfig):
            self.config = config_or_provider
            self.embedding_provider = None
        else:
            # Assume it's an embedding provider (for test compatibility)
            self.config = MetadataEnrichmentConfig()
            self.embedding_provider = config_or_provider
            
        self.enrichment_stats = {
            "nodes_enriched": 0,
            "metadata_added": {},
            "fields_per_node": []
        }
    
    @track_component_impact("metadata_enricher", "1.0.0")
    def enrich_extraction_results(
        self,
        extraction_results: Dict[str, Any],
        segment: Segment,
        episode_metadata: Dict[str, Any],
        podcast_metadata: Dict[str, Any],
        embedder: Optional[Callable] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Enrich extraction results with comprehensive metadata.
        
        Args:
            extraction_results: Results from SimpleKGPipeline
            segment: Source segment with temporal info
            episode_metadata: Episode-level metadata
            podcast_metadata: Podcast-level metadata
            embedder: Optional embedding function
            **kwargs: Additional context
            
        Returns:
            Enriched extraction results with metadata
        """
        if self.config.dry_run:
            return self._preview_enrichment(extraction_results, segment, episode_metadata)
        
        # Reset stats
        self.enrichment_stats = {
            "nodes_enriched": 0,
            "metadata_added": {},
            "fields_per_node": []
        }
        
        # Process different types of results
        enriched_results = extraction_results.copy()
        
        # Enrich nodes/entities
        if 'nodes' in enriched_results:
            enriched_results['nodes'] = self._enrich_nodes(
                enriched_results['nodes'],
                segment,
                episode_metadata,
                podcast_metadata,
                embedder
            )
        elif 'entities' in enriched_results:
            enriched_results['entities'] = self._enrich_nodes(
                enriched_results['entities'],
                segment,
                episode_metadata,
                podcast_metadata,
                embedder
            )
        
        # Enrich relationships
        if 'relationships' in enriched_results:
            enriched_results['relationships'] = self._enrich_relationships(
                enriched_results['relationships'],
                segment,
                episode_metadata
            )
        
        # Add extraction-level metadata
        enriched_results['extraction_metadata'] = self._create_extraction_metadata(
            segment,
            episode_metadata,
            podcast_metadata
        )
        
        # Get enrichment metrics
        metrics = self.get_enrichment_metrics()
        
        # Track contribution
        if self.enrichment_stats["nodes_enriched"] > 0:
            tracker = get_tracker()
            contribution = ComponentContribution(
                component_name="metadata_enricher",
                contribution_type="metadata_added",
                details=self.enrichment_stats["metadata_added"],
                count=self.enrichment_stats["nodes_enriched"],
                timestamp=kwargs.get('timestamp', datetime.now().isoformat())
            )
            tracker.track_contribution(contribution)
        
        return {
            "enriched_results": enriched_results,
            "metrics": metrics,
            "episode_id": kwargs.get('episode_id'),
            "segment_id": kwargs.get('segment_id')
        }
    
    def _enrich_nodes(
        self,
        nodes: List[Dict[str, Any]],
        segment: Segment,
        episode_metadata: Dict[str, Any],
        podcast_metadata: Dict[str, Any],
        embedder: Optional[Callable]
    ) -> List[Dict[str, Any]]:
        """Enrich a list of nodes with metadata."""
        enriched_nodes = []
        
        for node in nodes:
            enriched_node = node.copy()
            fields_added = []
            
            # Add temporal metadata
            if self.config.add_timestamps:
                temporal_meta = self.add_temporal_metadata(enriched_node, segment)
                if temporal_meta:
                    fields_added.extend(temporal_meta)
            
            # Add source metadata
            if self.config.add_source_metadata:
                source_meta = self.add_source_metadata(
                    enriched_node,
                    episode_metadata,
                    podcast_metadata
                )
                if source_meta:
                    fields_added.extend(source_meta)
            
            # Add extraction metadata
            if self.config.add_extraction_metadata:
                extraction_meta = self.add_extraction_metadata(enriched_node)
                if extraction_meta:
                    fields_added.extend(extraction_meta)
            
            # Add embeddings
            if self.config.add_embeddings and embedder:
                embedding_meta = self.add_embeddings(enriched_node, embedder)
                if embedding_meta:
                    fields_added.extend(embedding_meta)
            
            # Add confidence scores
            if self.config.add_confidence_scores:
                confidence_meta = self._add_confidence_scores(enriched_node, segment)
                if confidence_meta:
                    fields_added.extend(confidence_meta)
            
            # Add segment context
            if self.config.add_segment_context:
                segment_meta = self._add_segment_context(enriched_node, segment)
                if segment_meta:
                    fields_added.extend(segment_meta)
            
            enriched_nodes.append(enriched_node)
            
            # Update stats
            self.enrichment_stats["nodes_enriched"] += 1
            self.enrichment_stats["fields_per_node"].append(len(fields_added))
            
            for field in fields_added:
                if field not in self.enrichment_stats["metadata_added"]:
                    self.enrichment_stats["metadata_added"][field] = 0
                self.enrichment_stats["metadata_added"][field] += 1
        
        return enriched_nodes
    
    def add_temporal_metadata(self, node: Dict[str, Any], segment: Segment) -> List[str]:
        """Add timestamp information to a node."""
        fields_added = []
        
        if segment.start_time is not None:
            node['start_time'] = segment.start_time
            fields_added.append('start_time')
        
        if segment.end_time is not None:
            node['end_time'] = segment.end_time
            fields_added.append('end_time')
        
        if segment.start_time is not None and segment.end_time is not None:
            node['duration'] = segment.end_time - segment.start_time
            fields_added.append('duration')
        
        # Add human-readable timestamp
        if segment.start_time is not None:
            node['timestamp_formatted'] = self._format_timestamp(segment.start_time)
            fields_added.append('timestamp_formatted')
        
        return fields_added
    
    def add_source_metadata(
        self,
        node: Dict[str, Any],
        episode_metadata: Dict[str, Any],
        podcast_metadata: Dict[str, Any]
    ) -> List[str]:
        """Add source tracking information to a node."""
        fields_added = []
        
        # Episode metadata
        if episode_metadata:
            if 'id' in episode_metadata:
                node['episode_id'] = episode_metadata['id']
                fields_added.append('episode_id')
            
            if 'title' in episode_metadata:
                node['episode_title'] = episode_metadata['title']
                fields_added.append('episode_title')
            
            if 'published_at' in episode_metadata:
                node['episode_date'] = episode_metadata['published_at']
                fields_added.append('episode_date')
        
        # Podcast metadata
        if podcast_metadata:
            if 'id' in podcast_metadata:
                node['podcast_id'] = podcast_metadata['id']
                fields_added.append('podcast_id')
            
            if 'name' in podcast_metadata:
                node['podcast_name'] = podcast_metadata['name']
                fields_added.append('podcast_name')
            
            if 'category' in podcast_metadata:
                node['podcast_category'] = podcast_metadata['category']
                fields_added.append('podcast_category')
        
        return fields_added
    
    def add_extraction_metadata(self, node: Dict[str, Any]) -> List[str]:
        """Add metadata about the extraction process."""
        fields_added = []
        
        # Extraction timestamp
        node['extracted_at'] = datetime.now().isoformat()
        fields_added.append('extracted_at')
        
        # Extraction method
        node['extraction_method'] = 'schemaless_simplekgpipeline'
        fields_added.append('extraction_method')
        
        # Version info
        node['extractor_version'] = '1.0.0'
        fields_added.append('extractor_version')
        
        return fields_added
    
    def add_embeddings(self, node: Dict[str, Any], embedder: Callable) -> List[str]:
        """Generate and add vector embeddings to a node."""
        fields_added = []
        
        # Get text representation of node
        text = node.get('value', node.get('name', ''))
        if 'description' in node:
            text += f" {node['description']}"
        
        if text:
            try:
                # Generate embedding
                embedding = embedder(text)
                node['embedding'] = embedding
                fields_added.append('embedding')
                
                # Add embedding metadata
                node['embedding_model'] = getattr(embedder, 'model_name', 'unknown')
                fields_added.append('embedding_model')
                
                node['embedding_dimension'] = len(embedding) if isinstance(embedding, list) else None
                fields_added.append('embedding_dimension')
                
            except Exception as e:
                logger.warning(f"Failed to generate embedding: {e}")
        
        return fields_added
    
    def _add_confidence_scores(self, node: Dict[str, Any], segment: Segment) -> List[str]:
        """Add confidence scoring to nodes."""
        fields_added = []
        
        # If node already has confidence, preserve it
        if 'confidence' not in node:
            # Calculate confidence based on various factors
            confidence = 0.8  # Base confidence
            
            # Adjust based on segment confidence
            if hasattr(segment, 'confidence') and segment.confidence:
                confidence *= segment.confidence
            
            # Adjust based on node properties
            if 'occurrences' in node:
                # Higher occurrences = higher confidence
                confidence = min(confidence * (1 + node['occurrences'] * 0.1), 1.0)
            
            node['confidence'] = round(confidence, 3)
            fields_added.append('confidence')
        
        # Add confidence category
        if node.get('confidence', 0) >= 0.9:
            node['confidence_level'] = 'high'
        elif node.get('confidence', 0) >= 0.7:
            node['confidence_level'] = 'medium'
        else:
            node['confidence_level'] = 'low'
        fields_added.append('confidence_level')
        
        return fields_added
    
    def _add_segment_context(self, node: Dict[str, Any], segment: Segment) -> List[str]:
        """Add segment-level context to nodes."""
        fields_added = []
        
        # Segment ID
        if segment.id:
            node['segment_id'] = segment.id
            fields_added.append('segment_id')
        
        # Speaker information
        if segment.speaker:
            node['mentioned_by'] = segment.speaker
            fields_added.append('mentioned_by')
        
        # Segment index/position
        if hasattr(segment, 'index'):
            node['segment_index'] = segment.index
            fields_added.append('segment_index')
        
        # Word count context
        if segment.text:
            node['segment_word_count'] = len(segment.text.split())
            fields_added.append('segment_word_count')
        
        return fields_added
    
    def _enrich_relationships(
        self,
        relationships: List[Dict[str, Any]],
        segment: Segment,
        episode_metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Enrich relationships with metadata."""
        enriched_relationships = []
        
        for rel in relationships:
            enriched_rel = rel.copy()
            
            # Add temporal context
            if self.config.add_timestamps and segment.start_time is not None:
                enriched_rel['mentioned_at'] = segment.start_time
                enriched_rel['segment_id'] = segment.id
            
            # Add source context
            if self.config.add_source_metadata and episode_metadata:
                enriched_rel['episode_id'] = episode_metadata.get('id')
            
            # Add confidence
            if self.config.add_confidence_scores and 'confidence' not in enriched_rel:
                enriched_rel['confidence'] = 0.75  # Default relationship confidence
            
            enriched_relationships.append(enriched_rel)
        
        return enriched_relationships
    
    def _create_extraction_metadata(
        self,
        segment: Segment,
        episode_metadata: Dict[str, Any],
        podcast_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create metadata about the entire extraction."""
        return {
            'extraction_timestamp': datetime.now().isoformat(),
            'segment_id': segment.id,
            'segment_timerange': f"{segment.start_time}-{segment.end_time}s" if segment.start_time else None,
            'episode_id': episode_metadata.get('id'),
            'episode_title': episode_metadata.get('title'),
            'podcast_id': podcast_metadata.get('id'),
            'podcast_name': podcast_metadata.get('name'),
            'enrichment_version': '1.0.0'
        }
    
    def get_enrichment_metrics(self) -> Dict[str, Any]:
        """Get metrics about the enrichment process."""
        avg_fields = (
            sum(self.enrichment_stats["fields_per_node"]) / len(self.enrichment_stats["fields_per_node"])
            if self.enrichment_stats["fields_per_node"] else 0
        )
        
        return {
            "type": "metadata_enrichment",
            "details": {
                "nodes_enriched": self.enrichment_stats["nodes_enriched"],
                "metadata_fields_added": self.enrichment_stats["metadata_added"],
                "avg_fields_per_node": round(avg_fields, 2),
                "total_fields_added": sum(self.enrichment_stats["metadata_added"].values())
            },
            "count": self.enrichment_stats["nodes_enriched"]
        }
    
    def _preview_enrichment(
        self,
        extraction_results: Dict[str, Any],
        segment: Segment,
        episode_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Preview what metadata would be added without applying."""
        preview = {
            "would_add": {
                "temporal": [],
                "source": [],
                "extraction": [],
                "confidence": [],
                "segment": []
            }
        }
        
        if self.config.add_timestamps and segment.start_time:
            preview["would_add"]["temporal"] = [
                "start_time", "end_time", "duration", "timestamp_formatted"
            ]
        
        if self.config.add_source_metadata:
            preview["would_add"]["source"] = [
                "episode_id", "episode_title", "podcast_id", "podcast_name"
            ]
        
        if self.config.add_extraction_metadata:
            preview["would_add"]["extraction"] = [
                "extracted_at", "extraction_method", "extractor_version"
            ]
        
        if self.config.add_confidence_scores:
            preview["would_add"]["confidence"] = [
                "confidence", "confidence_level"
            ]
        
        if self.config.add_segment_context:
            preview["would_add"]["segment"] = [
                "segment_id", "mentioned_by", "segment_index"
            ]
        
        # Count total fields
        total_fields = sum(len(fields) for fields in preview["would_add"].values())
        node_count = len(extraction_results.get('nodes', []))
        
        preview["summary"] = {
            "nodes_to_enrich": node_count,
            "fields_per_node": total_fields,
            "total_fields_to_add": node_count * total_fields
        }
        
        return preview
    
    def _format_timestamp(self, seconds: float) -> str:
        """Format seconds into human-readable timestamp."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = int(seconds % 60)
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"