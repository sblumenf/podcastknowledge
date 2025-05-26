"""Pattern matching utilities for efficient text analysis."""

import re
import logging
from typing import List, Dict, Any, Pattern, Optional, Tuple
from dataclasses import dataclass, field
from functools import lru_cache
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class PatternMatch:
    """Represents a pattern match result."""
    pattern_name: str
    pattern_type: str
    text: str
    start: int
    end: int
    groups: Tuple[str, ...] = field(default_factory=tuple)
    metadata: Dict[str, Any] = field(default_factory=dict)


class PatternLibrary:
    """Library of common patterns for various use cases."""
    
    # Technical term patterns
    TECHNICAL_PATTERNS = {
        'medical_suffix': r'\b\w+(?:ology|itis|osis|ase|ide|ine)\b',
        'medical_prefix': r'\b(?:neuro|cardio|hypo|anti|meta|poly)\w+\b',
        'acronym': r'\b[A-Z]{2,}\b',
        'measurement': r'\b\d+\s*(?:mg|ml|μg|ng|mol|mM|μM|kg|g|L|mL)\b',
        'p_value': r'\bp\s*[<>=]\s*0\.\d+\b',
        'greek_letters': r'\b(?:alpha|beta|gamma|delta|epsilon|theta|lambda|sigma)\b',
        'bio_terms': r'\b(?:receptor|enzyme|protein|gene|pathway|mechanism|cell|tissue)\b',
        'research_terms': r'\b(?:hypothesis|theory|model|analysis|correlation|methodology)\b',
        'chemical_formula': r'\b[A-Z][a-z]?\d*(?:[A-Z][a-z]?\d*)*\b',
        'dna_sequence': r'\b[ATCG]{4,}\b',
    }
    
    # Fact and data patterns
    FACT_PATTERNS = {
        'percentage': r'\b\d+(?:\.\d+)?%\b',
        'number': r'\b\d+(?:,\d{3})*(?:\.\d+)?\b',
        'study_findings': r'\b(?:study|research|survey|report|trial|experiment) (?:shows?|finds?|suggests?|indicates?|demonstrates?|reveals?)\b',
        'citation': r'\b(?:according to|based on|as per|cited in|reported by)\b',
        'evidence_words': r'\b(?:statistic|data|evidence|finding|result|outcome|conclusion)\b',
        'proof_words': r'\b(?:proven|demonstrated|established|confirmed|validated|verified)\b',
        'comparison': r'\b(?:compared to|versus|vs\.?|relative to|in contrast to)\b',
        'correlation': r'\b(?:correlated? with|associated with|linked to|related to)\b',
        'statistical': r'\b(?:significant|p-value|confidence interval|standard deviation|mean|median)\b',
    }
    
    # Quote and insight patterns
    QUOTE_PATTERNS = {
        'key_phrase': r'\b(?:the key|the secret|the most important|the main)\b',
        'absolute_terms': r'\b(?:always|never|every|all|none|nothing|everything)\b',
        'success_failure': r'\b(?:success|failure|mistake|lesson|achievement|accomplishment)\b',
        'belief_words': r'\b(?:believe|think|know|realize|understand|feel|assume)\b',
        'advice_pattern': r'\b(?:if you|when you|you should|you must|you need to|you can)\b',
        'transformation': r'\b(?:changed my|transformed|revolutionized|disrupted|shifted)\b',
        'quoted_text': r'"[^"]{10,200}"',  # Quoted text between 10-200 chars
        'definition': r'\b(?:is|are|means?|refers? to|defined? as)\s+(?:that|to|when)?\b',
        'insight_intro': r'\b(?:what I learned|the insight|I realized|it turns out)\b',
    }
    
    # Entity patterns
    ENTITY_PATTERNS = {
        'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        'url': r'https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&//=]*)',
        'phone': r'\b(?:\+?1[-.]?)?\(?[0-9]{3}\)?[-.]?[0-9]{3}[-.]?[0-9]{4}\b',
        'date': r'\b(?:\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}[-/]\d{1,2}[-/]\d{1,2})\b',
        'time': r'\b\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?\b',
        'money': r'\$\d+(?:,\d{3})*(?:\.\d{2})?(?:\s*(?:million|billion|trillion|thousand|k|m|b))?\b',
        'person_name': r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b',  # Simple name pattern
        'company_suffix': r'\b\w+\s*(?:Inc\.?|Corp\.?|LLC|Ltd\.?|Company|Co\.?)\b',
        'hashtag': r'#\w+',
        'mention': r'@\w+',
    }
    
    # Domain-specific patterns
    DOMAIN_PATTERNS = {
        'medical': {
            'diagnosis': r'\b(?:diagnosed with|diagnosis of|suffering from)\b',
            'symptoms': r'\b(?:symptoms?|signs?|presents? with|complains? of)\b',
            'treatment': r'\b(?:treated with|therapy|medication|procedure|surgery)\b',
            'dosage': r'\b\d+\s*(?:mg|ml|mcg|units?)\s*(?:daily|twice|three times|QD|BID|TID)\b',
        },
        'tech': {
            'programming': r'\b(?:API|SDK|framework|library|algorithm|function|method|class)\b',
            'architecture': r'\b(?:microservice|monolith|serverless|cloud|distributed|scalable)\b',
            'performance': r'\b(?:latency|throughput|bandwidth|optimization|cache|memory)\b',
            'version': r'\bv?\d+\.\d+(?:\.\d+)?(?:-[a-zA-Z0-9]+)?\b',
        },
        'business': {
            'metrics': r'\b(?:ROI|KPI|revenue|profit|margin|growth|market share)\b',
            'finance': r'\b(?:investment|valuation|equity|debt|capital|funding|IPO)\b',
            'strategy': r'\b(?:strategy|competitive advantage|market position|disruption)\b',
            'growth': r'\b\d+(?:\.\d+)?%\s*(?:growth|increase|decrease|decline)\b',
        }
    }


class OptimizedPatternMatcher:
    """Pre-compiled regex patterns for better performance with caching."""
    
    def __init__(self, cache_size: int = 1000):
        """
        Initialize pattern matcher with caching.
        
        Args:
            cache_size: Maximum number of cached compiled patterns
        """
        self._pattern_cache: Dict[str, Pattern] = {}
        self._match_cache = lru_cache(maxsize=cache_size)(self._find_matches_cached)
        self._library = PatternLibrary()
        
        # Pre-compile common patterns
        self._precompile_patterns()
    
    def _precompile_patterns(self):
        """Pre-compile all library patterns for performance."""
        # Technical patterns
        self.technical_patterns = [
            self._compile_pattern(pattern, f"technical_{name}")
            for name, pattern in self._library.TECHNICAL_PATTERNS.items()
        ]
        
        # Fact patterns
        self.fact_patterns = [
            self._compile_pattern(pattern, f"fact_{name}")
            for name, pattern in self._library.FACT_PATTERNS.items()
        ]
        
        # Quote patterns
        self.quotable_patterns = [
            self._compile_pattern(pattern, f"quote_{name}")
            for name, pattern in self._library.QUOTE_PATTERNS.items()
        ]
        
        # Entity patterns
        self.entity_patterns = {
            name: self._compile_pattern(pattern, f"entity_{name}")
            for name, pattern in self._library.ENTITY_PATTERNS.items()
        }
        
        # Domain patterns
        self.domain_patterns = {}
        for domain, patterns in self._library.DOMAIN_PATTERNS.items():
            self.domain_patterns[domain] = {
                name: self._compile_pattern(pattern, f"{domain}_{name}")
                for name, pattern in patterns.items()
            }
    
    def _compile_pattern(self, pattern: str, name: str, flags: int = re.IGNORECASE) -> Pattern:
        """
        Compile and cache a regex pattern.
        
        Args:
            pattern: Regex pattern string
            name: Name for the pattern (for caching)
            flags: Regex flags
            
        Returns:
            Compiled pattern
        """
        cache_key = f"{name}:{pattern}:{flags}"
        if cache_key not in self._pattern_cache:
            try:
                self._pattern_cache[cache_key] = re.compile(pattern, flags)
            except re.error as e:
                logger.error(f"Failed to compile pattern '{name}': {e}")
                # Return a pattern that never matches
                self._pattern_cache[cache_key] = re.compile(r'(?!.*)')
        
        return self._pattern_cache[cache_key]
    
    def count_technical_terms(self, text: str) -> int:
        """Count technical terms using pre-compiled patterns."""
        count = 0
        for pattern in self.technical_patterns:
            count += len(pattern.findall(text))
        return count
    
    def count_facts(self, text: str) -> int:
        """Count factual statements using pre-compiled patterns."""
        count = 0
        for pattern in self.fact_patterns:
            count += len(pattern.findall(text))
        return count
    
    def get_quotability_score(self, text: str) -> float:
        """
        Calculate quotability score for text.
        
        Args:
            text: Text to analyze
            
        Returns:
            Quotability score (0.0 to 1.0)
        """
        if not text:
            return 0.0
            
        matches = 0
        for pattern in self.quotable_patterns:
            if pattern.search(text):
                matches += 1
        
        # Normalize to 0-1 range
        max_possible = len(self.quotable_patterns)
        return min(1.0, matches / max(max_possible * 0.3, 1))  # 30% of patterns is high quotability
    
    def extract_entities(self, text: str) -> List[PatternMatch]:
        """
        Extract entities from text using patterns.
        
        Args:
            text: Text to analyze
            
        Returns:
            List of entity matches
        """
        matches = []
        
        for entity_type, pattern in self.entity_patterns.items():
            for match in pattern.finditer(text):
                matches.append(PatternMatch(
                    pattern_name=entity_type,
                    pattern_type='entity',
                    text=match.group(),
                    start=match.start(),
                    end=match.end(),
                    groups=match.groups(),
                    metadata={'entity_type': entity_type}
                ))
        
        return matches
    
    def analyze_domain(self, text: str, domain: str) -> Dict[str, List[PatternMatch]]:
        """
        Analyze text for domain-specific patterns.
        
        Args:
            text: Text to analyze
            domain: Domain to analyze ('medical', 'tech', 'business')
            
        Returns:
            Dictionary of pattern matches by pattern type
        """
        if domain not in self.domain_patterns:
            logger.warning(f"Unknown domain: {domain}")
            return {}
        
        results = defaultdict(list)
        
        for pattern_name, pattern in self.domain_patterns[domain].items():
            for match in pattern.finditer(text):
                results[pattern_name].append(PatternMatch(
                    pattern_name=pattern_name,
                    pattern_type=f'{domain}_pattern',
                    text=match.group(),
                    start=match.start(),
                    end=match.end(),
                    groups=match.groups(),
                    metadata={'domain': domain}
                ))
        
        return dict(results)
    
    def find_all_patterns(self, text: str) -> Dict[str, List[PatternMatch]]:
        """
        Find all pattern matches in text.
        
        Args:
            text: Text to analyze
            
        Returns:
            Dictionary of matches organized by pattern type
        """
        results = {
            'technical': [],
            'facts': [],
            'quotes': [],
            'entities': self.extract_entities(text)
        }
        
        # Technical terms
        for i, pattern in enumerate(self.technical_patterns):
            pattern_name = list(self._library.TECHNICAL_PATTERNS.keys())[i]
            for match in pattern.finditer(text):
                results['technical'].append(PatternMatch(
                    pattern_name=pattern_name,
                    pattern_type='technical',
                    text=match.group(),
                    start=match.start(),
                    end=match.end(),
                    groups=match.groups()
                ))
        
        # Facts
        for i, pattern in enumerate(self.fact_patterns):
            pattern_name = list(self._library.FACT_PATTERNS.keys())[i]
            for match in pattern.finditer(text):
                results['facts'].append(PatternMatch(
                    pattern_name=pattern_name,
                    pattern_type='fact',
                    text=match.group(),
                    start=match.start(),
                    end=match.end(),
                    groups=match.groups()
                ))
        
        # Quotable content
        for i, pattern in enumerate(self.quotable_patterns):
            pattern_name = list(self._library.QUOTE_PATTERNS.keys())[i]
            for match in pattern.finditer(text):
                results['quotes'].append(PatternMatch(
                    pattern_name=pattern_name,
                    pattern_type='quote',
                    text=match.group(),
                    start=match.start(),
                    end=match.end(),
                    groups=match.groups()
                ))
        
        return results
    
    @lru_cache(maxsize=1000)
    def _find_matches_cached(self, text: str, pattern_str: str, flags: int = 0) -> Tuple[Tuple[str, ...], ...]:
        """
        Cached pattern matching for frequently used patterns.
        
        Args:
            text: Text to search
            pattern_str: Pattern string
            flags: Regex flags
            
        Returns:
            Tuple of match tuples for caching
        """
        pattern = self._compile_pattern(pattern_str, f"cached_{hash(pattern_str)}", flags)
        return tuple((m.group(), m.start(), m.end()) for m in pattern.finditer(text))
    
    def find_pattern(self, text: str, pattern: str, flags: int = re.IGNORECASE) -> List[PatternMatch]:
        """
        Find all matches of a custom pattern.
        
        Args:
            text: Text to search
            pattern: Regex pattern
            flags: Regex flags
            
        Returns:
            List of pattern matches
        """
        matches = []
        cached_results = self._find_matches_cached(text, pattern, flags)
        
        for match_text, start, end in cached_results:
            matches.append(PatternMatch(
                pattern_name='custom',
                pattern_type='custom',
                text=match_text,
                start=start,
                end=end
            ))
        
        return matches
    
    def get_pattern_library(self) -> PatternLibrary:
        """Get the pattern library for direct access."""
        return self._library
    
    def clear_cache(self):
        """Clear pattern and match caches."""
        self._pattern_cache.clear()
        self._match_cache.cache_clear()
        logger.info("Pattern matcher caches cleared")


# Global instance for convenience
pattern_matcher = OptimizedPatternMatcher()


def create_custom_pattern_matcher(patterns: Dict[str, str], flags: int = re.IGNORECASE) -> OptimizedPatternMatcher:
    """
    Create a custom pattern matcher with user-defined patterns.
    
    Args:
        patterns: Dictionary of pattern names to regex strings
        flags: Default regex flags
        
    Returns:
        Configured pattern matcher
    """
    matcher = OptimizedPatternMatcher()
    
    # Add custom patterns
    for name, pattern_str in patterns.items():
        compiled = matcher._compile_pattern(pattern_str, name, flags)
        # Store in a custom category
        if not hasattr(matcher, 'custom_patterns'):
            matcher.custom_patterns = {}
        matcher.custom_patterns[name] = compiled
    
    return matcher