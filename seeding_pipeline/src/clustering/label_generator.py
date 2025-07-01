"""
Cluster label generator module.

Generates human-readable labels for clusters by analyzing representative MeaningfulUnits.
Uses cosine similarity to find units closest to cluster centroid and LLM to generate 
concise, descriptive labels.

Follows KISS principle - simple selection and prompt approach.
"""

import numpy as np
from typing import Dict, List, Any, Optional
from sklearn.metrics.pairwise import cosine_similarity
from src.utils.logging import get_logger
from src.services.llm import LLMService

logger = get_logger(__name__)


class ClusterLabeler:
    """
    Generates human-readable labels for clusters using LLM analysis.
    
    Process:
    1. Select representative units closest to cluster centroid
    2. Generate concise label using LLM prompt
    3. Validate and clean label format
    4. Handle fallbacks for generation failures
    """
    
    def __init__(self, llm_service: LLMService):
        """
        Initialize cluster labeler.
        
        Args:
            llm_service: LLM service for label generation
        """
        self.llm_service = llm_service
        self.used_labels = set()  # Track used labels to avoid duplicates
        self.banned_terms = ["Topics", "Discussion", "General", "Conversation", "Content", "Units"]
        
        # Validation statistics
        self.validation_stats = {
            'total_generated': 0,
            'fallback_used': 0,
            'banned_terms': 0,
            'generic_terms': 0,
            'too_short': 0,
            'numbers_only': 0,
            'duplicates_resolved': 0,
            'truncated': 0
        }
        
        logger.info("Initialized ClusterLabeler")
    
    def generate_labels(self, cluster_results: Dict[str, Any], embeddings_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate labels for all clusters.
        
        Args:
            cluster_results: Results from clustering with centroids
            embeddings_data: Embeddings and metadata from extractor
            
        Returns:
            Dictionary with cluster_id -> label mappings
        """
        logger.info(f"Generating labels for {cluster_results['n_clusters']} clusters")
        
        labeled_clusters = {}
        self.used_labels.clear()  # Reset for new labeling run
        
        for cluster_id, cluster_centroid in cluster_results['centroids'].items():
            try:
                # Get units assigned to this cluster
                cluster_units = cluster_results['clusters'].get(cluster_id, [])
                
                if not cluster_units:
                    logger.warning(f"No units found for cluster {cluster_id}")
                    labeled_clusters[cluster_id] = f"Cluster_{cluster_id}"
                    continue
                
                # Select representative units
                representative_units = self._get_representative_units(
                    cluster_units, cluster_centroid, embeddings_data
                )
                
                # Generate label using LLM
                label = self._generate_single_label(representative_units)
                
                # Validate and clean label
                label = self._validate_and_clean_label(label, cluster_id)
                
                labeled_clusters[cluster_id] = label
                self.used_labels.add(label)
                
                logger.debug(f"Generated label '{label}' for cluster {cluster_id}")
                
            except Exception as e:
                logger.warning(f"Label generation failed for cluster {cluster_id}: {e}")
                fallback_label = f"Cluster_{cluster_id}"
                labeled_clusters[cluster_id] = fallback_label
                self.used_labels.add(fallback_label)
        
        logger.info(f"Generated {len(labeled_clusters)} cluster labels")
        
        # Log validation statistics
        self._log_validation_summary()
        
        return labeled_clusters
    
    def _get_representative_units(self, cluster_units: List[Dict[str, Any]], 
                                 centroid: np.ndarray, embeddings_data: Dict[str, Any],
                                 n_representatives: int = 5) -> List[Dict[str, Any]]:
        """
        Select most representative units from cluster using cosine similarity to centroid.
        
        Args:
            cluster_units: List of units in the cluster
            centroid: Cluster centroid embedding
            embeddings_data: All embeddings and metadata
            n_representatives: Number of representative units to select
            
        Returns:
            List of representative units with summaries and metadata
        """
        if not cluster_units:
            return []
        
        # Get embeddings for cluster units
        unit_similarities = []
        for unit in cluster_units:
            unit_id = unit['unit_id']
            try:
                unit_index = embeddings_data['unit_ids'].index(unit_id)
                unit_embedding = embeddings_data['embeddings'][unit_index]
                
                # Calculate cosine similarity to centroid
                similarity = cosine_similarity([centroid], [unit_embedding])[0][0]
                
                # Get unit metadata
                unit_summary = embeddings_data['metadata'][unit_index].get('summary', 'No summary available')
                
                unit_similarities.append({
                    'unit_id': unit_id,
                    'summary': unit_summary,
                    'similarity': similarity,
                    'metadata': embeddings_data['metadata'][unit_index]
                })
                
            except (ValueError, IndexError) as e:
                logger.warning(f"Could not find embedding for unit {unit_id}: {e}")
                continue
        
        if not unit_similarities:
            logger.warning("No valid embeddings found for cluster units")
            return []
        
        # Sort by similarity and select top N
        unit_similarities.sort(key=lambda x: x['similarity'], reverse=True)
        n_select = min(n_representatives, len(unit_similarities))
        selected_units = unit_similarities[:n_select]
        
        logger.debug(f"Selected {len(selected_units)} representative units with similarities: "
                    f"{[u['similarity'] for u in selected_units]}")
        
        return selected_units
    
    def _generate_single_label(self, representative_units: List[Dict[str, Any]]) -> str:
        """
        Use LLM to generate a concise cluster label from representative units.
        
        Args:
            representative_units: List of representative units with summaries
            
        Returns:
            Generated label string
        """
        if not representative_units:
            return "Empty Cluster"
        
        # Build context from representative units
        summaries = []
        for unit in representative_units[:5]:  # Use top 5 units max
            summary = unit['summary']
            if summary and summary.strip():
                summaries.append(f"- {summary.strip()}")
        
        if not summaries:
            return "No Content"
        
        context = "\n".join(summaries)
        
        # Create prompt following the comprehensive report specification
        prompt = f"""Analyze these related discussion summaries and provide a concise topic label.

Summaries:
{context}

Requirements:
- Maximum 3 words
- Specific and descriptive  
- Title case
- Capture the common theme

Good examples: "Machine Learning", "Climate Change", "Startup Funding", "Electric Vehicles"
Bad examples: "Discussion", "Topics", "General", "Content"

Label:"""
        
        try:
            # Generate label with low temperature for consistency
            response = self.llm_service.generate(prompt, temperature=0.3)
            label = response.strip().strip('"').strip("'")
            
            logger.debug(f"LLM generated label: '{label}'")
            return label
            
        except Exception as e:
            logger.error(f"LLM label generation failed: {e}")
            raise
    
    def _validate_and_clean_label(self, label: str, cluster_id: int) -> str:
        """
        Validate and clean generated label according to quality standards.
        
        Args:
            label: Raw label from LLM
            cluster_id: Cluster ID for fallback naming
            
        Returns:
            Validated and cleaned label
        """
        self.validation_stats['total_generated'] += 1
        
        if not label or not label.strip():
            self.validation_stats['fallback_used'] += 1
            return f"Cluster_{cluster_id}"
        
        # Clean the label
        label = label.strip()
        original_raw_label = label
        
        # Ensure title case
        label = label.title()
        
        # Limit to 3 words
        words = label.split()
        if len(words) > 3:
            label = " ".join(words[:3])
            self.validation_stats['truncated'] += 1
            logger.debug(f"Truncated label to 3 words: '{label}'")
        
        # Check banned terms
        if label in self.banned_terms:
            self.validation_stats['banned_terms'] += 1
            self.validation_stats['fallback_used'] += 1
            logger.debug(f"Label '{label}' is banned, using fallback")
            return f"Cluster_{cluster_id}"
        
        # Additional validation checks
        # Check for overly generic terms
        generic_terms = ["Things", "Stuff", "Items", "Various", "Multiple", "Different"]
        if any(term in label for term in generic_terms):
            self.validation_stats['generic_terms'] += 1
            self.validation_stats['fallback_used'] += 1
            logger.debug(f"Label '{label}' contains generic terms, using fallback")
            return f"Cluster_{cluster_id}"
        
        # Check for single character or very short labels
        if len(label.replace(" ", "")) < 3:
            self.validation_stats['too_short'] += 1
            self.validation_stats['fallback_used'] += 1
            logger.debug(f"Label '{label}' is too short, using fallback")
            return f"Cluster_{cluster_id}"
        
        # Check for numbers-only labels
        if label.replace(" ", "").isdigit():
            self.validation_stats['numbers_only'] += 1
            self.validation_stats['fallback_used'] += 1
            logger.debug(f"Label '{label}' is numbers-only, using fallback")
            return f"Cluster_{cluster_id}"
        
        # Handle duplicates
        original_label = label
        counter = 2
        while label in self.used_labels:
            label = f"{original_label} {counter}"
            counter += 1
            if counter > 10:  # Prevent infinite loop
                self.validation_stats['fallback_used'] += 1
                label = f"Cluster_{cluster_id}"
                break
        
        if label != original_label:
            self.validation_stats['duplicates_resolved'] += 1
            logger.debug(f"Avoided duplicate: '{original_label}' -> '{label}'")
        
        return label
    
    def _log_validation_summary(self):
        """Log validation statistics summary."""
        stats = self.validation_stats
        total = stats['total_generated']
        
        if total == 0:
            return
        
        success_rate = ((total - stats['fallback_used']) / total) * 100
        
        logger.info("Label validation summary:")
        logger.info(f"  Total labels generated: {total}")
        logger.info(f"  Success rate: {success_rate:.1f}%")
        logger.info(f"  Fallbacks used: {stats['fallback_used']}")
        
        if stats['banned_terms'] > 0:
            logger.info(f"  Banned terms detected: {stats['banned_terms']}")
        if stats['generic_terms'] > 0:
            logger.info(f"  Generic terms detected: {stats['generic_terms']}")
        if stats['too_short'] > 0:
            logger.info(f"  Too short labels: {stats['too_short']}")
        if stats['numbers_only'] > 0:
            logger.info(f"  Numbers-only labels: {stats['numbers_only']}")
        if stats['duplicates_resolved'] > 0:
            logger.info(f"  Duplicates resolved: {stats['duplicates_resolved']}")
        if stats['truncated'] > 0:
            logger.info(f"  Labels truncated: {stats['truncated']}")
    
    def get_validation_stats(self) -> Dict[str, Any]:
        """
        Get validation statistics.
        
        Returns:
            Dictionary with validation statistics
        """
        stats = self.validation_stats.copy()
        total = stats['total_generated']
        
        if total > 0:
            stats['success_rate'] = ((total - stats['fallback_used']) / total) * 100
            stats['fallback_rate'] = (stats['fallback_used'] / total) * 100
        else:
            stats['success_rate'] = 0.0
            stats['fallback_rate'] = 0.0
            
        return stats