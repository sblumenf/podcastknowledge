"""
Tests for entity resolution functionality
"""
import pytest
from unittest.mock import Mock, MagicMock
from typing import List

from src.core.models import Entity, EntityType
from src.core.interfaces import EmbeddingProvider
from src.processing.entity_resolution import (
    EntityResolver, EntityMatch, EntityRelationship,
    VectorEntityMatcher
)


class TestEntityResolver:
    """Test suite for EntityResolver class"""
    
    @pytest.fixture
    def resolver(self):
        """Create an EntityResolver instance"""
        return EntityResolver(similarity_threshold=0.85)
    
    @pytest.fixture
    def sample_entities(self):
        """Create sample entities for testing"""
        return [
            Entity(
                id="1",
                name="Apple Inc.",
                entity_type=EntityType.ORGANIZATION,
                confidence=0.9,
                description="Technology company"
            ),
            Entity(
                id="2",
                name="Apple",
                entity_type=EntityType.ORGANIZATION,
                confidence=0.85,
                description="Also known as Apple Computer"
            ),
            Entity(
                id="3",
                name="Microsoft Corporation",
                entity_type=EntityType.ORGANIZATION,
                confidence=0.95,
                description="Software company"
            ),
            Entity(
                id="4",
                name="Steve Jobs",
                entity_type=EntityType.PERSON,
                confidence=0.9,
                description="Co-founder of Apple"
            )
        ]
    
    def test_normalize_entity_name(self, resolver):
        """Test entity name normalization"""
        # Test suffix removal
        assert resolver.normalize_entity_name("Apple Inc.") == "apple"
        assert resolver.normalize_entity_name("Microsoft Corporation") == "microsoft"
        assert resolver.normalize_entity_name("Google LLC") == "google"
        
        # Test abbreviation expansion
        assert resolver.normalize_entity_name("AT&T") == "atandt"
        assert resolver.normalize_entity_name("U.S. Government") == "us government"
        
        # Test whitespace handling
        assert resolver.normalize_entity_name("  Apple   Inc  ") == "apple"
        
        # Test empty/None
        assert resolver.normalize_entity_name("") == ""
        assert resolver.normalize_entity_name(None) == ""
    
    def test_calculate_name_similarity(self, resolver):
        """Test name similarity calculation"""
        # Exact match (normalized)
        similarity = resolver.calculate_name_similarity("Apple Inc.", "Apple")
        assert similarity > 0.9
        
        # Similar names
        similarity = resolver.calculate_name_similarity("Microsoft", "Microsofd")
        assert 0.8 < similarity < 0.95
        
        # Different names
        similarity = resolver.calculate_name_similarity("Apple", "Google")
        assert similarity < 0.5
        
        # Empty strings
        similarity = resolver.calculate_name_similarity("", "")
        assert similarity == 1.0
    
    def test_extract_entity_aliases(self, resolver):
        """Test alias extraction from descriptions"""
        # Test various alias patterns
        description = "Apple Inc., also known as Apple Computer, formerly Apple Computer, Inc."
        aliases = resolver.extract_entity_aliases("Apple Inc.", description)
        assert "Apple Computer" in aliases
        assert "Apple Computer, Inc." in aliases
        
        # Test aka pattern
        description = "International Business Machines (IBM), aka Big Blue"
        aliases = resolver.extract_entity_aliases("IBM", description)
        assert "Big Blue" in aliases
        
        # Test parentheses
        description = "Alphabet Inc. (Google)"
        aliases = resolver.extract_entity_aliases("Alphabet Inc.", description)
        assert "Google" in aliases
        
        # Test quoted names
        description = 'Microsoft or "MSFT" on the stock market'
        aliases = resolver.extract_entity_aliases("Microsoft", description)
        assert "MSFT" in aliases
        
        # No aliases
        aliases = resolver.extract_entity_aliases("Apple", "A technology company")
        assert len(aliases) == 0
        
        # None description
        aliases = resolver.extract_entity_aliases("Apple", None)
        assert len(aliases) == 0
    
    def test_find_potential_matches(self, resolver, sample_entities):
        """Test finding potential entity matches"""
        new_entity = Entity(
            id="5",
            name="Apple Computer",
            entity_type=EntityType.ORGANIZATION,
            confidence=0.8
        )
        
        matches = resolver.find_potential_matches(new_entity, sample_entities)
        
        # Should find Apple Inc. and Apple as matches
        assert len(matches) >= 2
        assert matches[0].match_type == "exact_normalized"
        assert matches[0].similarity == 1.0
        
        # Should not match different entity types
        person_entity = Entity(
            id="6",
            name="Apple",
            entity_type=EntityType.PERSON,
            confidence=0.8
        )
        matches = resolver.find_potential_matches(person_entity, sample_entities)
        assert len(matches) == 0
    
    def test_merge_entities(self, resolver):
        """Test entity merging"""
        primary = Entity(
            id="1",
            name="Apple Inc.",
            entity_type=EntityType.ORGANIZATION,
            confidence=0.9,
            description="Technology company"
        )
        
        duplicate = Entity(
            id="2",
            name="Apple Computer",
            entity_type=EntityType.ORGANIZATION,
            confidence=0.85,
            description="Computer manufacturer"
        )
        
        # Add aliases to test merging
        setattr(primary, 'aliases', ["AAPL"])
        setattr(duplicate, 'aliases', ["Apple Computer Inc."])
        
        merged = resolver.merge_entities(primary, duplicate)
        
        # Check merged properties
        assert merged.name == "Apple Inc."
        assert merged.confidence == 0.9
        assert "Technology company" in merged.description
        assert "Computer manufacturer" in merged.description
        
        # Check aliases
        aliases = getattr(merged, 'aliases', [])
        assert "Apple Computer" in aliases
        assert "AAPL" in aliases
        assert "Apple Computer Inc." in aliases
    
    def test_resolve_entities(self, resolver):
        """Test entity resolution process"""
        entities = [
            Entity(id="1", name="Apple Inc.", entity_type=EntityType.ORGANIZATION, confidence=0.9),
            Entity(id="2", name="Apple", entity_type=EntityType.ORGANIZATION, confidence=0.85),
            Entity(id="3", name="Microsoft", entity_type=EntityType.ORGANIZATION, confidence=0.95),
            Entity(id="4", name="Apple Computer", entity_type=EntityType.ORGANIZATION, confidence=0.8),
            Entity(id="5", name="Steve Jobs", entity_type=EntityType.PERSON, confidence=0.9)
        ]
        
        resolved = resolver.resolve_entities(entities)
        
        # Should merge Apple entities
        org_entities = [e for e in resolved if e.entity_type == EntityType.ORGANIZATION]
        assert len(org_entities) == 2  # Apple (merged) and Microsoft
        
        # Should keep person entity separate
        person_entities = [e for e in resolved if e.entity_type == EntityType.PERSON]
        assert len(person_entities) == 1
    
    def test_extract_entity_relationships(self, resolver, sample_entities):
        """Test relationship extraction"""
        text = """
        Steve Jobs co-founded Apple Inc. with Steve Wozniak. 
        Apple competed with Microsoft Corporation in the personal computer market.
        Jobs returned to Apple in 1997.
        """
        
        relationships = resolver.extract_entity_relationships(text, sample_entities)
        
        # Should find relationships between entities mentioned in text
        assert len(relationships) > 0
        
        # Check specific relationships
        jobs_apple_rel = None
        for rel in relationships:
            if (rel.source_id == "4" and rel.target_id in ["1", "2"]) or \
               (rel.target_id == "4" and rel.source_id in ["1", "2"]):
                jobs_apple_rel = rel
                break
        
        assert jobs_apple_rel is not None
        assert jobs_apple_rel.confidence > 0.5
        assert jobs_apple_rel.context is not None
    
    def test_relationship_confidence_calculation(self, resolver):
        """Test relationship confidence based on proximity"""
        # Entities close together
        text1 = "Steve Jobs founded Apple."
        entities = [
            Entity(id="1", name="Steve Jobs", entity_type=EntityType.PERSON, confidence=0.9),
            Entity(id="2", name="Apple", entity_type=EntityType.ORGANIZATION, confidence=0.9)
        ]
        
        relationships1 = resolver.extract_entity_relationships(text1, entities)
        assert len(relationships1) == 1
        assert relationships1[0].confidence > 0.8
        
        # Entities far apart
        text2 = "Steve Jobs was born in 1955. " + " ".join(["word"] * 100) + " Apple was founded in 1976."
        relationships2 = resolver.extract_entity_relationships(text2, entities)
        
        if relationships2:  # May not find relationship due to distance
            assert relationships2[0].confidence < relationships1[0].confidence


class TestVectorEntityMatcher:
    """Test suite for VectorEntityMatcher class"""
    
    @pytest.fixture
    def mock_embedding_provider(self):
        """Create mock embedding provider"""
        provider = Mock(spec=EmbeddingProvider)
        
        # Define embeddings for different entities
        embeddings = {
            "ORGANIZATION: Apple Inc.": [0.1, 0.2, 0.3, 0.4],
            "ORGANIZATION: Apple": [0.1, 0.2, 0.3, 0.4],
            "ORGANIZATION: Microsoft Corporation": [0.5, 0.6, 0.7, 0.8],
            "PERSON: Steve Jobs": [0.2, 0.3, 0.4, 0.5],
            "TECHNOLOGY: Machine Learning": [0.3, 0.4, 0.5, 0.6],
            "CONCEPT: Artificial Intelligence": [0.35, 0.45, 0.55, 0.65]
        }
        
        def embed_side_effect(text):
            # Find matching key
            for key in embeddings:
                if key in text:
                    return embeddings[key]
            # Default embedding
            return [0.0, 0.0, 0.0, 0.0]
        
        provider.embed.side_effect = embed_side_effect
        return provider
    
    @pytest.fixture
    def matcher(self, mock_embedding_provider):
        """Create VectorEntityMatcher instance"""
        return VectorEntityMatcher(
            embedding_provider=mock_embedding_provider,
            similarity_threshold=0.8
        )
    
    @pytest.fixture
    def sample_entities(self):
        """Create sample entities"""
        return [
            Entity(id="1", name="Apple Inc.", entity_type=EntityType.ORGANIZATION, confidence=0.9),
            Entity(id="2", name="Microsoft Corporation", entity_type=EntityType.ORGANIZATION, confidence=0.95),
            Entity(id="3", name="Steve Jobs", entity_type=EntityType.PERSON, confidence=0.9),
            Entity(id="4", name="Machine Learning", entity_type=EntityType.TECHNOLOGY, confidence=0.85),
            Entity(id="5", name="Artificial Intelligence", entity_type=EntityType.CONCEPT, confidence=0.88)
        ]
    
    def test_get_entity_embedding(self, matcher, sample_entities):
        """Test entity embedding generation"""
        entity = sample_entities[0]
        embedding = matcher.get_entity_embedding(entity)
        
        assert isinstance(embedding, list)
        assert len(embedding) == 4
        assert embedding == [0.1, 0.2, 0.3, 0.4]
        
        # Test caching
        embedding2 = matcher.get_entity_embedding(entity)
        assert embedding == embedding2
        # Should use cache, not call provider again
        assert matcher.embedding_provider.embed.call_count == 1
    
    def test_calculate_cosine_similarity(self, matcher):
        """Test cosine similarity calculation"""
        # Identical vectors
        vec1 = [1.0, 0.0, 0.0]
        similarity = matcher.calculate_cosine_similarity(vec1, vec1)
        assert similarity == 1.0
        
        # Orthogonal vectors
        vec2 = [0.0, 1.0, 0.0]
        similarity = matcher.calculate_cosine_similarity(vec1, vec2)
        assert similarity == 0.0
        
        # Similar vectors
        vec3 = [1.0, 0.1, 0.0]
        similarity = matcher.calculate_cosine_similarity(vec1, vec3)
        assert 0.9 < similarity < 1.0
        
        # Different dimensions should raise error
        vec4 = [1.0, 0.0]
        with pytest.raises(ValueError):
            matcher.calculate_cosine_similarity(vec1, vec4)
    
    def test_find_similar_entities(self, matcher, sample_entities):
        """Test finding similar entities using embeddings"""
        query = Entity(
            id="6",
            name="Apple",
            entity_type=EntityType.ORGANIZATION,
            confidence=0.8
        )
        
        similar = matcher.find_similar_entities(query, sample_entities, top_k=3)
        
        # Should find Apple Inc. as most similar
        assert len(similar) > 0
        assert similar[0][0].name == "Apple Inc."
        assert similar[0][1] == 1.0  # Perfect match due to same embedding
    
    def test_cluster_entities(self, matcher, sample_entities):
        """Test entity clustering"""
        # Add another tech entity that should cluster with ML
        tech_entity = Entity(
            id="6",
            name="Machine Learning",
            entity_type=EntityType.TECHNOLOGY,
            confidence=0.82
        )
        entities = sample_entities + [tech_entity]
        
        clusters = matcher.cluster_entities(entities, min_cluster_size=1)
        
        # Should create clusters
        assert len(clusters) > 0
        
        # ML entities should be in same cluster
        ml_cluster = None
        for cluster in clusters:
            if any(e.id == "4" for e in cluster):
                ml_cluster = cluster
                break
        
        assert ml_cluster is not None
        assert len(ml_cluster) == 2  # Both ML entities
    
    def test_find_cross_type_relationships(self, matcher, sample_entities):
        """Test finding relationships between different entity types"""
        relationships = matcher.find_cross_type_relationships(sample_entities)
        
        # Should find some relationships
        assert len(relationships) > 0
        
        # Check that relationships are between different types
        for rel in relationships:
            source = next(e for e in sample_entities if e.id == rel.source_id)
            target = next(e for e in sample_entities if e.id == rel.target_id)
            assert source.entity_type != target.entity_type
    
    def test_merge_entity_clusters(self, matcher):
        """Test merging entity clusters"""
        resolver = EntityResolver()
        
        clusters = [
            [
                Entity(id="1", name="Apple Inc.", entity_type=EntityType.ORGANIZATION, confidence=0.9),
                Entity(id="2", name="Apple", entity_type=EntityType.ORGANIZATION, confidence=0.85)
            ],
            [
                Entity(id="3", name="Microsoft", entity_type=EntityType.ORGANIZATION, confidence=0.95)
            ]
        ]
        
        merged = matcher.merge_entity_clusters(clusters, resolver)
        
        assert len(merged) == 2
        
        # First cluster should be merged into one entity
        apple_entity = next(e for e in merged if "Apple" in e.name)
        assert apple_entity.confidence == 0.9  # Should keep higher confidence
        
        # Single entity cluster should remain unchanged
        ms_entity = next(e for e in merged if "Microsoft" in e.name)
        assert ms_entity.id == "3"
    
    def test_empty_inputs(self, matcher):
        """Test handling of empty inputs"""
        # Empty entity list
        similar = matcher.find_similar_entities(
            Entity(id="1", name="Test", entity_type=EntityType.CONCEPT, confidence=0.8),
            []
        )
        assert len(similar) == 0
        
        # Empty clustering
        clusters = matcher.cluster_entities([])
        assert len(clusters) == 0
        
        # Empty relationships
        relationships = matcher.find_cross_type_relationships([])
        assert len(relationships) == 0