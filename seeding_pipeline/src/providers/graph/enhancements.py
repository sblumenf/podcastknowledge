"""Graph enhancement functions for Neo4j provider."""

import logging
from typing import Dict, Any, Optional, List
import os

from src.core.exceptions import ProviderError


logger = logging.getLogger(__name__)


class GraphEnhancements:
    """Collection of graph enhancement functions."""
    
    @staticmethod
    def add_sentiment_to_knowledge_graph(neo4j_session, episode_id: str, segments: List[Dict[str, Any]]) -> None:
        """
        Add sentiment information to the knowledge graph.
        
        Args:
            neo4j_session: Neo4j session
            episode_id: Episode ID
            segments: List of segments with sentiment scores
        """
        try:
            for segment in segments:
                if 'sentiment' not in segment:
                    continue
                    
                # Update segment sentiment
                neo4j_session.run("""
                MATCH (s:Segment {id: $segment_id})
                SET s.sentiment = $sentiment,
                    s.sentiment_score = $sentiment_score
                """, {
                    'segment_id': segment['id'],
                    'sentiment': segment['sentiment'],
                    'sentiment_score': segment.get('sentiment_score', 0.0)
                })
                
                # Create sentiment relationships to entities mentioned in segment
                if 'entities' in segment:
                    for entity_name in segment['entities']:
                        neo4j_session.run("""
                        MATCH (s:Segment {id: $segment_id})
                        MATCH (e:Entity {name: $entity_name, episode_id: $episode_id})
                        MERGE (e)-[r:HAS_SENTIMENT]->(s)
                        SET r.score = $sentiment_score,
                            r.polarity = $sentiment
                        """, {
                            'segment_id': segment['id'],
                            'entity_name': entity_name,
                            'episode_id': episode_id,
                            'sentiment_score': segment.get('sentiment_score', 0.0),
                            'sentiment': segment['sentiment']
                        })
                        
            logger.info(f"Added sentiment information for episode {episode_id}")
            
        except Exception as e:
            logger.error(f"Failed to add sentiment to knowledge graph: {e}")
            raise ProviderError(f"Failed to add sentiment: {e}")
            
    @staticmethod
    def enhance_speaker_information(neo4j_session, episode_id: str, speaker_data: Dict[str, Any]) -> None:
        """
        Enhance speaker information in the knowledge graph.
        
        Args:
            neo4j_session: Neo4j session
            episode_id: Episode ID
            speaker_data: Dictionary with speaker information
        """
        try:
            # Create or update speaker nodes
            for speaker_name, speaker_info in speaker_data.items():
                # Create speaker node if it doesn't exist
                neo4j_session.run("""
                MERGE (sp:Speaker {name: $name})
                ON CREATE SET 
                    sp.id = $speaker_id,
                    sp.created_timestamp = datetime(),
                    sp.role = $role
                ON MATCH SET
                    sp.updated_timestamp = datetime()
                """, {
                    'name': speaker_name,
                    'speaker_id': f"speaker_{speaker_name.lower().replace(' ', '_')}",
                    'role': speaker_info.get('role', 'guest')
                })
                
                # Link speaker to episode
                neo4j_session.run("""
                MATCH (sp:Speaker {name: $name})
                MATCH (ep:Episode {id: $episode_id})
                MERGE (sp)-[r:SPEAKS_IN]->(ep)
                SET r.segment_count = $segment_count,
                    r.total_duration = $duration
                """, {
                    'name': speaker_name,
                    'episode_id': episode_id,
                    'segment_count': speaker_info.get('segment_count', 0),
                    'duration': speaker_info.get('total_duration', 0)
                })
                
                # Link speaker to their segments
                if 'segment_ids' in speaker_info:
                    for segment_id in speaker_info['segment_ids']:
                        neo4j_session.run("""
                        MATCH (sp:Speaker {name: $name})
                        MATCH (s:Segment {id: $segment_id})
                        MERGE (sp)-[:SPEAKS]->(s)
                        """, {
                            'name': speaker_name,
                            'segment_id': segment_id
                        })
                        
                # Track entities discussed by speaker
                if 'discussed_entities' in speaker_info:
                    for entity_name, count in speaker_info['discussed_entities'].items():
                        neo4j_session.run("""
                        MATCH (sp:Speaker {name: $speaker_name})
                        MATCH (e:Entity {name: $entity_name, episode_id: $episode_id})
                        MERGE (sp)-[r:DISCUSSES]->(e)
                        SET r.count = $count
                        """, {
                            'speaker_name': speaker_name,
                            'entity_name': entity_name,
                            'episode_id': episode_id,
                            'count': count
                        })
                        
            logger.info(f"Enhanced speaker information for episode {episode_id}")
            
        except Exception as e:
            logger.error(f"Failed to enhance speaker information: {e}")
            raise ProviderError(f"Failed to enhance speaker information: {e}")
            
    @staticmethod
    def improve_embeddings(neo4j_session, episode_id: str, embedding_provider) -> None:
        """
        Improve embeddings for knowledge graph nodes.
        
        Args:
            neo4j_session: Neo4j session
            episode_id: Episode ID
            embedding_provider: Embedding provider instance
        """
        try:
            # Get segments without embeddings
            result = neo4j_session.run("""
            MATCH (ep:Episode {id: $episode_id})-[:HAS_SEGMENT]->(s:Segment)
            WHERE s.embedding IS NULL OR size(s.embedding) = 0
            RETURN s.id as id, s.text as text
            LIMIT 100
            """, {"episode_id": episode_id})
            
            segments_to_embed = []
            for record in result:
                segments_to_embed.append({
                    'id': record['id'],
                    'text': record['text']
                })
                
            # Generate embeddings in batch
            if segments_to_embed:
                texts = [s['text'] for s in segments_to_embed]
                embeddings = embedding_provider.generate_embeddings(texts)
                
                # Update segments with embeddings
                for segment, embedding in zip(segments_to_embed, embeddings):
                    neo4j_session.run("""
                    MATCH (s:Segment {id: $segment_id})
                    SET s.embedding = $embedding,
                        s.embedding_model = $model
                    """, {
                        'segment_id': segment['id'],
                        'embedding': embedding,
                        'model': embedding_provider.model_name
                    })
                    
            # Get entities without embeddings
            result = neo4j_session.run("""
            MATCH (e:Entity {episode_id: $episode_id})
            WHERE e.embedding IS NULL OR size(e.embedding) = 0
            RETURN e.id as id, e.name as name, e.description as description
            LIMIT 100
            """, {"episode_id": episode_id})
            
            entities_to_embed = []
            for record in result:
                text = f"{record['name']}: {record.get('description', '')}"
                entities_to_embed.append({
                    'id': record['id'],
                    'text': text
                })
                
            # Generate embeddings for entities
            if entities_to_embed:
                texts = [e['text'] for e in entities_to_embed]
                embeddings = embedding_provider.generate_embeddings(texts)
                
                # Update entities with embeddings
                for entity, embedding in zip(entities_to_embed, embeddings):
                    neo4j_session.run("""
                    MATCH (e:Entity {id: $entity_id})
                    SET e.embedding = $embedding,
                        e.embedding_model = $model
                    """, {
                        'entity_id': entity['id'],
                        'embedding': embedding,
                        'model': embedding_provider.model_name
                    })
                    
            logger.info(f"Improved embeddings for episode {episode_id}")
            
        except Exception as e:
            logger.error(f"Failed to improve embeddings: {e}")
            raise ProviderError(f"Failed to improve embeddings: {e}")
            
    @staticmethod
    def enrich_metadata(neo4j_session, episode_id: str, metadata: Dict[str, Any]) -> None:
        """
        Enrich metadata for episode and related nodes.
        
        Args:
            neo4j_session: Neo4j session
            episode_id: Episode ID
            metadata: Additional metadata to add
        """
        try:
            # Update episode metadata
            if 'episode' in metadata:
                props = []
                params = {'episode_id': episode_id}
                
                for key, value in metadata['episode'].items():
                    if value is not None:
                        props.append(f"e.{key} = ${key}")
                        params[key] = value
                        
                if props:
                    neo4j_session.run(f"""
                    MATCH (e:Episode {{id: $episode_id}})
                    SET {', '.join(props)}
                    """, params)
                    
            # Update segment metadata (e.g., topics, keywords)
            if 'segments' in metadata:
                for segment_id, segment_meta in metadata['segments'].items():
                    props = []
                    params = {'segment_id': segment_id}
                    
                    for key, value in segment_meta.items():
                        if value is not None:
                            props.append(f"s.{key} = ${key}")
                            params[key] = value
                            
                    if props:
                        neo4j_session.run(f"""
                        MATCH (s:Segment {{id: $segment_id}})
                        SET {', '.join(props)}
                        """, params)
                        
            # Add topic relationships
            if 'topics' in metadata:
                for topic_data in metadata['topics']:
                    # Create topic node
                    neo4j_session.run("""
                    MERGE (t:Topic {name: $name})
                    ON CREATE SET
                        t.id = $topic_id,
                        t.description = $description,
                        t.created_timestamp = datetime()
                    """, {
                        'name': topic_data['name'],
                        'topic_id': f"topic_{topic_data['name'].lower().replace(' ', '_')}",
                        'description': topic_data.get('description', '')
                    })
                    
                    # Link topic to episode
                    neo4j_session.run("""
                    MATCH (e:Episode {id: $episode_id})
                    MATCH (t:Topic {name: $topic_name})
                    MERGE (e)-[r:HAS_TOPIC]->(t)
                    SET r.relevance = $relevance
                    """, {
                        'episode_id': episode_id,
                        'topic_name': topic_data['name'],
                        'relevance': topic_data.get('relevance', 1.0)
                    })
                    
            logger.info(f"Enriched metadata for episode {episode_id}")
            
        except Exception as e:
            logger.error(f"Failed to enrich metadata: {e}")
            raise ProviderError(f"Failed to enrich metadata: {e}")
            
    @staticmethod
    def establish_entity_relationships(neo4j_session, episode_id: str, relationship_data: Dict[str, Any]) -> None:
        """
        Establish relationships between entities based on co-occurrence and semantic similarity.
        
        Args:
            neo4j_session: Neo4j session
            episode_id: Episode ID
            relationship_data: Data about entity relationships
        """
        try:
            # Create co-occurrence relationships
            if 'co_occurrences' in relationship_data:
                for (entity1, entity2), weight in relationship_data['co_occurrences'].items():
                    neo4j_session.run("""
                    MATCH (e1:Entity {name: $entity1, episode_id: $episode_id})
                    MATCH (e2:Entity {name: $entity2, episode_id: $episode_id})
                    MERGE (e1)-[r:CO_OCCURS_WITH]-(e2)
                    SET r.weight = $weight,
                        r.updated_at = datetime()
                    """, {
                        'entity1': entity1,
                        'entity2': entity2,
                        'episode_id': episode_id,
                        'weight': weight
                    })
                    
            # Create semantic similarity relationships
            if 'semantic_similarities' in relationship_data:
                for (entity1, entity2), similarity in relationship_data['semantic_similarities'].items():
                    if similarity > 0.7:  # Threshold for semantic similarity
                        neo4j_session.run("""
                        MATCH (e1:Entity {name: $entity1, episode_id: $episode_id})
                        MATCH (e2:Entity {name: $entity2, episode_id: $episode_id})
                        MERGE (e1)-[r:SEMANTICALLY_SIMILAR]-(e2)
                        SET r.similarity = $similarity,
                            r.updated_at = datetime()
                        """, {
                            'entity1': entity1,
                            'entity2': entity2,
                            'episode_id': episode_id,
                            'similarity': similarity
                        })
                        
            # Create entity-to-insight relationships
            if 'entity_insights' in relationship_data:
                for entity_name, insight_ids in relationship_data['entity_insights'].items():
                    for insight_id in insight_ids:
                        neo4j_session.run("""
                        MATCH (e:Entity {name: $entity_name, episode_id: $episode_id})
                        MATCH (i:Insight {id: $insight_id})
                        MERGE (e)-[r:CONTRIBUTES_TO]->(i)
                        SET r.updated_at = datetime()
                        """, {
                            'entity_name': entity_name,
                            'episode_id': episode_id,
                            'insight_id': insight_id
                        })
                        
            logger.info(f"Established entity relationships for episode {episode_id}")
            
        except Exception as e:
            logger.error(f"Failed to establish entity relationships: {e}")
            raise ProviderError(f"Failed to establish entity relationships: {e}")