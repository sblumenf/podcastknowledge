"""
Embeddings extractor for semantic clustering.

Extracts MeaningfulUnit embeddings from Neo4j for clustering.
Follows KISS principle - no caching, no optimization unless needed.
"""

import numpy as np
from typing import Dict, List, Any, Optional
from src.utils.logging import get_logger

logger = get_logger(__name__)


class EmbeddingsExtractor:
    """
    Extracts MeaningfulUnit embeddings from Neo4j.
    
    Uses existing 768-dimensional embeddings created by Gemini.
    No new embedding generation - works with what's already stored.
    """
    
    def __init__(self, neo4j_service):
        """
        Initialize embeddings extractor.
        
        Args:
            neo4j_service: GraphStorageService instance
        """
        self.neo4j = neo4j_service
        
    def extract_all_embeddings(self) -> Dict[str, Any]:
        """
        Extract all MeaningfulUnit embeddings and metadata from Neo4j.
        
        Returns:
            Dictionary containing:
            - 'embeddings': np.ndarray of shape (n_units, 768)
            - 'unit_ids': List[str] of unit identifiers
            - 'metadata': List[Dict] with unit metadata
            
        Raises:
            Exception: If extraction fails
        """
        logger.info("Starting embeddings extraction from Neo4j")
        
        try:
            # Query to get all MeaningfulUnits with embeddings
            query = """
            MATCH (m:MeaningfulUnit)<-[:CONTAINS]-(e:Episode)
            WHERE m.embedding IS NOT NULL
            RETURN 
                m.id as unit_id,
                m.embedding as embedding,
                m.summary as summary,
                e.id as episode_id,
                e.title as episode_title,
                m.themes as themes,
                m.start_time as start_time,
                m.end_time as end_time,
                m.speaker_distribution as speaker_distribution
            ORDER BY m.id
            """
            
            results = self.neo4j.query(query)
            
            if not results:
                logger.warning("No MeaningfulUnits with embeddings found")
                return {
                    'embeddings': np.array([]),
                    'unit_ids': [],
                    'metadata': []
                }
            
            # Process results
            embeddings = []
            unit_ids = []
            metadata = []
            
            for record in results:
                # Validate embedding
                embedding = record['embedding']
                if not isinstance(embedding, list) or len(embedding) != 768:
                    logger.warning(
                        f"Invalid embedding for unit {record['unit_id']}: "
                        f"type={type(embedding)}, len={len(embedding) if isinstance(embedding, list) else 'N/A'}"
                    )
                    continue
                
                embeddings.append(embedding)
                unit_ids.append(record['unit_id'])
                
                # Collect metadata
                metadata.append({
                    'unit_id': record['unit_id'],
                    'summary': record['summary'] or '',
                    'episode_id': record['episode_id'],
                    'episode_title': record['episode_title'] or '',
                    'themes': record['themes'] or [],
                    'start_time': record['start_time'],
                    'end_time': record['end_time'],
                    'speaker_distribution': record['speaker_distribution'] or {}
                })
            
            # Convert to numpy array
            embeddings_array = np.array(embeddings, dtype=np.float32)
            
            logger.info(
                f"Successfully extracted {len(embeddings)} embeddings "
                f"from {len(set(m['episode_id'] for m in metadata))} episodes"
            )
            
            return {
                'embeddings': embeddings_array,
                'unit_ids': unit_ids,
                'metadata': metadata
            }
            
        except Exception as e:
            logger.error(f"Failed to extract embeddings: {str(e)}", exc_info=True)
            raise
    
    def extract_embeddings_by_episode(self, episode_id: str) -> Dict[str, Any]:
        """
        Extract embeddings for a specific episode.
        
        Args:
            episode_id: Episode identifier
            
        Returns:
            Same format as extract_all_embeddings but for single episode
        """
        logger.info(f"Extracting embeddings for episode: {episode_id}")
        
        query = """
        MATCH (e:Episode {id: $episode_id})-[:CONTAINS]->(m:MeaningfulUnit)
        WHERE m.embedding IS NOT NULL
        RETURN 
            m.id as unit_id,
            m.embedding as embedding,
            m.summary as summary,
            e.id as episode_id,
            e.title as episode_title,
            m.themes as themes,
            m.start_time as start_time,
            m.end_time as end_time,
            m.speaker_distribution as speaker_distribution
        ORDER BY m.start_time
        """
        
        results = self.neo4j.query(query, {'episode_id': episode_id})
        
        # Process using same logic as extract_all_embeddings
        embeddings = []
        unit_ids = []
        metadata = []
        
        for record in results:
            embedding = record['embedding']
            if not isinstance(embedding, list) or len(embedding) != 768:
                logger.warning(f"Invalid embedding for unit {record['unit_id']}")
                continue
                
            embeddings.append(embedding)
            unit_ids.append(record['unit_id'])
            metadata.append({
                'unit_id': record['unit_id'],
                'summary': record['summary'] or '',
                'episode_id': record['episode_id'],
                'episode_title': record['episode_title'] or '',
                'themes': record['themes'] or [],
                'start_time': record['start_time'],
                'end_time': record['end_time'],
                'speaker_distribution': record['speaker_distribution'] or {}
            })
        
        return {
            'embeddings': np.array(embeddings, dtype=np.float32),
            'unit_ids': unit_ids,
            'metadata': metadata
        }
    
    def count_embeddings(self) -> Dict[str, int]:
        """
        Get counts of embeddings and units for validation.
        
        Returns:
            Dictionary with counts and statistics
        """
        query = """
        MATCH (m:MeaningfulUnit)
        WITH 
            count(m) as total_units,
            count(CASE WHEN m.embedding IS NOT NULL THEN 1 END) as units_with_embeddings,
            count(CASE WHEN m.embedding IS NOT NULL AND size(m.embedding) = 768 THEN 1 END) as valid_embeddings
        MATCH (e:Episode)
        WITH total_units, units_with_embeddings, valid_embeddings, count(e) as total_episodes
        RETURN 
            total_units,
            units_with_embeddings,
            valid_embeddings,
            total_episodes,
            CASE WHEN total_units > 0 
                THEN round(toFloat(units_with_embeddings) / total_units * 100, 2) 
                ELSE 0.0 
            END as embedding_coverage_percent
        """
        
        result = self.neo4j.query(query)
        
        if result:
            return result[0]
        else:
            return {
                'total_units': 0,
                'units_with_embeddings': 0,
                'valid_embeddings': 0,
                'total_episodes': 0,
                'embedding_coverage_percent': 0.0
            }