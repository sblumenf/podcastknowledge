"""Cache management for Gemini prompt caching optimization."""

import logging
import hashlib
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CachedContent:
    """Represents cached content information."""
    cache_name: str
    episode_id: str
    content_hash: str
    created_at: datetime
    ttl_seconds: int
    token_count: int
    
    @property
    def is_expired(self) -> bool:
        """Check if cache has expired."""
        return (datetime.now() - self.created_at).total_seconds() > self.ttl_seconds


class CacheManager:
    """Manages transcript and prompt caching for Gemini API optimization."""
    
    def __init__(self, default_ttl: int = 3600):
        """Initialize cache manager.
        
        Args:
            default_ttl: Default TTL for caches in seconds (default: 1 hour)
        """
        self.default_ttl = default_ttl
        self._episode_caches: Dict[str, CachedContent] = {}
        self._prompt_caches: Dict[str, CachedContent] = {}
        self._cache_stats = {
            'hits': 0,
            'misses': 0,
            'creates': 0,
            'evictions': 0
        }
        
    def get_content_hash(self, content: str) -> str:
        """Generate hash for content."""
        return hashlib.sha256(content.encode()).hexdigest()[:16]
        
    def estimate_tokens(self, content: str) -> int:
        """Estimate token count for content."""
        # Rough estimation: 1 token per 4 characters
        return len(content) // 4
        
    def should_cache_transcript(self, transcript: str, episode_id: str) -> bool:
        """Determine if transcript should be cached based on size and usage.
        
        Args:
            transcript: The transcript content
            episode_id: Episode identifier
            
        Returns:
            True if transcript should be cached
        """
        # Check if already cached
        if episode_id in self._episode_caches:
            cache = self._episode_caches[episode_id]
            if not cache.is_expired:
                return False  # Already cached
                
        # Check minimum size requirements
        token_count = self.estimate_tokens(transcript)
        
        # Gemini 2.5 Flash requires minimum 1024 tokens
        # Gemini 2.5 Pro requires minimum 2048 tokens
        if token_count < 1024:
            logger.debug(f"Episode {episode_id} too small for caching: {token_count} tokens")
            return False
            
        # Prioritize caching for larger transcripts (>5000 tokens)
        if token_count > 5000:
            logger.info(f"Episode {episode_id} recommended for caching: {token_count} tokens")
            return True
            
        return True  # Cache medium-sized transcripts too
        
    def register_episode_cache(self, 
                             episode_id: str, 
                             cache_name: str,
                             content: str,
                             ttl: Optional[int] = None) -> CachedContent:
        """Register a cached episode transcript.
        
        Args:
            episode_id: Episode identifier
            cache_name: Gemini cache name/ID
            content: The cached content
            ttl: TTL in seconds (uses default if not specified)
            
        Returns:
            CachedContent object
        """
        ttl = ttl or self.default_ttl
        
        cached_content = CachedContent(
            cache_name=cache_name,
            episode_id=episode_id,
            content_hash=self.get_content_hash(content),
            created_at=datetime.now(),
            ttl_seconds=ttl,
            token_count=self.estimate_tokens(content)
        )
        
        self._episode_caches[episode_id] = cached_content
        self._cache_stats['creates'] += 1
        
        logger.info(f"Registered cache for episode {episode_id}: {cache_name} "
                   f"({cached_content.token_count} tokens, TTL: {ttl}s)")
        
        return cached_content
        
    def get_episode_cache(self, episode_id: str) -> Optional[str]:
        """Get cached content name for episode if available.
        
        Args:
            episode_id: Episode identifier
            
        Returns:
            Cache name if available and not expired, None otherwise
        """
        if episode_id not in self._episode_caches:
            self._cache_stats['misses'] += 1
            return None
            
        cache = self._episode_caches[episode_id]
        
        if cache.is_expired:
            # Remove expired cache
            del self._episode_caches[episode_id]
            self._cache_stats['evictions'] += 1
            self._cache_stats['misses'] += 1
            logger.debug(f"Cache expired for episode {episode_id}")
            return None
            
        self._cache_stats['hits'] += 1
        return cache.cache_name
        
    def register_prompt_cache(self,
                            template_name: str,
                            cache_name: str,
                            content: str,
                            version: str = "1.0") -> CachedContent:
        """Register a cached prompt template.
        
        Args:
            template_name: Name of the prompt template
            cache_name: Gemini cache name/ID
            content: The cached prompt content
            version: Template version
            
        Returns:
            CachedContent object
        """
        cache_key = f"{template_name}_v{version}"
        
        cached_content = CachedContent(
            cache_name=cache_name,
            episode_id=cache_key,  # Reuse episode_id field for prompt key
            content_hash=self.get_content_hash(content),
            created_at=datetime.now(),
            ttl_seconds=86400,  # 24 hours for prompt templates
            token_count=self.estimate_tokens(content)
        )
        
        self._prompt_caches[cache_key] = cached_content
        self._cache_stats['creates'] += 1
        
        logger.info(f"Registered prompt cache {cache_key}: {cache_name} "
                   f"({cached_content.token_count} tokens)")
        
        return cached_content
        
    def get_prompt_cache(self, template_name: str, version: str = "1.0") -> Optional[str]:
        """Get cached prompt template if available.
        
        Args:
            template_name: Name of the prompt template
            version: Template version
            
        Returns:
            Cache name if available and not expired, None otherwise
        """
        cache_key = f"{template_name}_v{version}"
        
        if cache_key not in self._prompt_caches:
            return None
            
        cache = self._prompt_caches[cache_key]
        
        if cache.is_expired:
            del self._prompt_caches[cache_key]
            self._cache_stats['evictions'] += 1
            return None
            
        return cache.cache_name
        
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics.
        
        Returns:
            Dict with cache statistics
        """
        total_requests = self._cache_stats['hits'] + self._cache_stats['misses']
        hit_rate = self._cache_stats['hits'] / total_requests if total_requests > 0 else 0
        
        return {
            'hits': self._cache_stats['hits'],
            'misses': self._cache_stats['misses'],
            'hit_rate': hit_rate,
            'creates': self._cache_stats['creates'],
            'evictions': self._cache_stats['evictions'],
            'active_episode_caches': len(self._episode_caches),
            'active_prompt_caches': len(self._prompt_caches),
            'total_cached_tokens': sum(c.token_count for c in self._episode_caches.values())
        }
        
    def estimate_cost_savings(self) -> Dict[str, float]:
        """Estimate cost savings from caching.
        
        Returns:
            Dict with cost estimates
        """
        # Gemini 2.5 Flash pricing: $0.10 per 1M input tokens
        # With caching: 75% discount = $0.025 per 1M cached tokens
        
        total_cached_tokens = sum(c.token_count for c in self._episode_caches.values())
        cache_uses = self._cache_stats['hits']
        
        # Estimate tokens saved
        tokens_saved = total_cached_tokens * cache_uses * 0.75  # 75% discount
        
        # Convert to cost
        cost_per_million = 0.10  # $0.10 per 1M tokens
        savings = (tokens_saved / 1_000_000) * cost_per_million
        
        return {
            'total_cached_tokens': total_cached_tokens,
            'cache_uses': cache_uses,
            'tokens_saved': tokens_saved,
            'estimated_savings_usd': savings,
            'savings_percentage': 0.75 if cache_uses > 0 else 0
        }
        
    def cleanup_expired(self):
        """Remove all expired caches."""
        # Clean episode caches
        expired_episodes = [
            eid for eid, cache in self._episode_caches.items()
            if cache.is_expired
        ]
        for eid in expired_episodes:
            del self._episode_caches[eid]
            self._cache_stats['evictions'] += 1
            
        # Clean prompt caches
        expired_prompts = [
            pid for pid, cache in self._prompt_caches.items()
            if cache.is_expired
        ]
        for pid in expired_prompts:
            del self._prompt_caches[pid]
            self._cache_stats['evictions'] += 1
            
        if expired_episodes or expired_prompts:
            logger.info(f"Cleaned up {len(expired_episodes)} episode caches "
                       f"and {len(expired_prompts)} prompt caches")
            
    def warm_prompt_caches(self, llm_service, prompt_templates: Dict[str, str]) -> List[str]:
        """Warm up prompt caches on startup.
        
        Args:
            llm_service: The Gemini Direct service instance
            prompt_templates: Dict of template name to content
            
        Returns:
            List of successfully cached template names
        """
        cached_templates = []
        
        for template_name, content in prompt_templates.items():
            # Check if already cached
            existing_cache = self.get_prompt_cache(template_name)
            if existing_cache:
                cached_templates.append(template_name)
                continue
                
            # Check if content is large enough
            if self.estimate_tokens(content) < 1024:
                logger.debug(f"Prompt template {template_name} too small for caching")
                continue
                
            try:
                # Create cache using the service
                cache_name = llm_service.create_cached_content(
                    content=content,
                    episode_id=f"prompt_{template_name}",
                    system_instruction="You are a knowledge extraction assistant."
                )
                
                if cache_name:
                    self.register_prompt_cache(template_name, cache_name, content)
                    cached_templates.append(template_name)
                    
            except Exception as e:
                logger.error(f"Failed to cache prompt template {template_name}: {e}")
                
        logger.info(f"Warmed {len(cached_templates)} prompt caches")
        return cached_templates