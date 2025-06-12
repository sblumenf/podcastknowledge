"""Service for managing cached prompt templates."""

import logging
from typing import Dict, Any, Optional, List
import json

from src.extraction.prompts import PromptBuilder, PromptTemplate
from src.services.cache_manager import CacheManager
from src.services.llm_gemini_direct import GeminiDirectService

logger = logging.getLogger(__name__)


class CachedPromptService:
    """Service for managing and using cached prompt templates."""
    
    # Define which prompts should be cached
    CACHEABLE_PROMPTS = [
        'entity_extraction_large',
        'entity_extraction_small',
        'insight_extraction_large',
        'insight_extraction_small',
        'quote_extraction_large',
        'complexity_analysis',
        'information_density'
    ]
    
    def __init__(self, 
                 llm_service: GeminiDirectService,
                 cache_manager: CacheManager,
                 use_large_context: bool = True):
        """Initialize cached prompt service.
        
        Args:
            llm_service: The Gemini Direct service
            cache_manager: Cache manager instance
            use_large_context: Whether to use large context prompts
        """
        self.llm_service = llm_service
        self.cache_manager = cache_manager
        self.prompt_builder = PromptBuilder(use_large_context)
        self._cached_templates: Dict[str, str] = {}
        
    def warm_caches(self) -> List[str]:
        """Warm up prompt caches on startup.
        
        Returns:
            List of successfully cached prompt names
        """
        logger.info("Warming prompt template caches...")
        
        # Get cacheable templates
        templates_to_cache = {}
        for template_name in self.CACHEABLE_PROMPTS:
            if template_name in self.prompt_builder._templates:
                template = self.prompt_builder._templates[template_name]
                
                # Create a sample prompt with dummy data
                sample_prompt = self._create_sample_prompt(template)
                if sample_prompt and self.cache_manager.estimate_tokens(sample_prompt) >= 1024:
                    templates_to_cache[template_name] = sample_prompt
                    
        # Warm caches using cache manager
        cached = self.cache_manager.warm_prompt_caches(self.llm_service, templates_to_cache)
        
        # Store cache references
        for template_name in cached:
            cache_name = self.cache_manager.get_prompt_cache(template_name)
            if cache_name:
                self._cached_templates[template_name] = cache_name
                
        logger.info(f"Successfully cached {len(cached)} prompt templates")
        return cached
        
    def _create_sample_prompt(self, template: PromptTemplate) -> Optional[str]:
        """Create a sample prompt for caching.
        
        Args:
            template: The prompt template
            
        Returns:
            Sample prompt or None if cannot create
        """
        # Create dummy data for each variable
        dummy_data = {
            'text': 'Sample transcript content for caching. ' * 50,  # Make it substantial
            'entity_context': '\nKnown entities: Person1, Company1, Product1\n',
            'entities': json.dumps([{'name': 'Sample', 'type': 'Person'}]),
            'insights': json.dumps([{'content': 'Sample insight'}])
        }
        
        # Only include variables that the template needs
        template_vars = {var: dummy_data.get(var, '') for var in template.variables}
        
        try:
            return template.format(**template_vars)
        except Exception as e:
            logger.warning(f"Could not create sample prompt for {template.name}: {e}")
            return None
            
    def extract_entities(self, 
                        text: str,
                        episode_cache_name: Optional[str] = None) -> str:
        """Extract entities using cached prompts if available.
        
        Args:
            text: Text to extract entities from
            episode_cache_name: Optional episode cache to use
            
        Returns:
            LLM response with extracted entities
        """
        # Choose appropriate template
        template_name = ('entity_extraction_large' if self.prompt_builder.use_large_context 
                        else 'entity_extraction_small')
        
        # Get the template
        template = self.prompt_builder._templates.get(template_name)
        if not template:
            raise ValueError(f"Template {template_name} not found")
            
        # Format the prompt
        prompt = template.format(text=text)
        
        # Check for cached prompt template
        prompt_cache_name = self._cached_templates.get(template_name)
        
        # If we have both episode and prompt cache, use episode cache
        # (it's more specific and likely more beneficial)
        cache_to_use = episode_cache_name or prompt_cache_name
        
        # Make the LLM call
        return self.llm_service.complete(prompt, cached_content_name=cache_to_use)
        
    def extract_insights(self,
                        text: str,
                        entity_context: str = "",
                        episode_cache_name: Optional[str] = None) -> str:
        """Extract insights using cached prompts if available.
        
        Args:
            text: Text to extract insights from
            entity_context: Context about known entities
            episode_cache_name: Optional episode cache to use
            
        Returns:
            LLM response with extracted insights
        """
        # Choose appropriate template
        template_name = ('insight_extraction_large' if self.prompt_builder.use_large_context 
                        else 'insight_extraction_small')
        
        # Get the template
        template = self.prompt_builder._templates.get(template_name)
        if not template:
            raise ValueError(f"Template {template_name} not found")
            
        # Format the prompt
        prompt = template.format(text=text, entity_context=entity_context)
        
        # Check for cached prompt template
        prompt_cache_name = self._cached_templates.get(template_name)
        
        # Use episode cache if available, otherwise prompt cache
        cache_to_use = episode_cache_name or prompt_cache_name
        
        # Make the LLM call
        return self.llm_service.complete(prompt, cached_content_name=cache_to_use)
        
    def extract_quotes(self,
                      text: str,
                      episode_cache_name: Optional[str] = None) -> str:
        """Extract quotes using cached prompts if available.
        
        Args:
            text: Text to extract quotes from
            episode_cache_name: Optional episode cache to use
            
        Returns:
            LLM response with extracted quotes
        """
        template_name = 'quote_extraction_large'
        
        # Get the template
        template = self.prompt_builder._templates.get(template_name)
        if not template:
            raise ValueError(f"Template {template_name} not found")
            
        # Format the prompt
        prompt = template.format(text=text)
        
        # Check for cached prompt template
        prompt_cache_name = self._cached_templates.get(template_name)
        
        # Use episode cache if available, otherwise prompt cache
        cache_to_use = episode_cache_name or prompt_cache_name
        
        # Make the LLM call
        return self.llm_service.complete(prompt, cached_content_name=cache_to_use)
        
    def analyze_complexity(self,
                          text: str,
                          episode_cache_name: Optional[str] = None) -> str:
        """Analyze text complexity using cached prompts if available.
        
        Args:
            text: Text to analyze
            episode_cache_name: Optional episode cache to use
            
        Returns:
            LLM response with complexity analysis
        """
        template_name = 'complexity_analysis'
        
        # Get the template
        template = self.prompt_builder._templates.get(template_name)
        if not template:
            raise ValueError(f"Template {template_name} not found")
            
        # Format the prompt
        prompt = template.format(text=text)
        
        # Check for cached prompt template
        prompt_cache_name = self._cached_templates.get(template_name)
        
        # Use episode cache if available, otherwise prompt cache
        cache_to_use = episode_cache_name or prompt_cache_name
        
        # Make the LLM call
        return self.llm_service.complete(prompt, cached_content_name=cache_to_use)
        
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get statistics about prompt caching.
        
        Returns:
            Dict with cache statistics
        """
        return {
            'cached_templates': list(self._cached_templates.keys()),
            'cache_count': len(self._cached_templates),
            'manager_stats': self.cache_manager.get_cache_stats()
        }