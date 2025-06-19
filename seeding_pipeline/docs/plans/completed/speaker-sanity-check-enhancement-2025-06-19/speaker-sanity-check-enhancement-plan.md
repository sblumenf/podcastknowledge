# Speaker Sanity Check Enhancement Plan

**Status**: ✅ COMPLETED  
**Completion Date**: 2025-06-19

## Overview
Enhance the post-processing pipeline with simple, maintainable sanity checks to improve speaker data quality by filtering non-names, merging duplicates, and validating speaker contributions.

## Design Principles
- **KISS (Keep It Simple, Stupid)**: Prioritize simplicity and maintainability
- **Minimal Dependencies**: Use existing infrastructure where possible
- **Automated Resolution**: Auto-merge duplicates without manual intervention
- **Fail-Safe**: Don't break existing functionality

## Implementation Approach

### 1. Integration Strategy
Add sanity checks as a new step in the existing `SpeakerMapper.process_episode()` method, after initial speaker identification but before database updates.

**Rationale**: Keeps all speaker-related logic in one place, maintains simplicity.

### 2. Core Components

#### A. Non-Name Filter
```python
def _is_valid_speaker_name(self, name: str) -> bool:
    """Check if a string is a valid speaker name."""
    # Simple blacklist approach - KISS principle
    invalid_patterns = [
        'you know what',
        'um', 'uh', 'ah',
        'yeah', 'okay', 'alright',
        # Add more as discovered
    ]
    
    name_lower = name.lower().strip()
    
    # Check blacklist
    if name_lower in invalid_patterns:
        return False
    
    # Basic sanity: must have at least 2 characters
    if len(name) < 2:
        return False
    
    # Must contain at least one letter
    if not any(c.isalpha() for c in name):
        return False
    
    return True
```

#### B. Duplicate Detection and Auto-Merge
```python
def _find_duplicate_speakers(self, speakers: List[str]) -> Dict[str, str]:
    """Find likely duplicate speakers in the same episode."""
    duplicates = {}
    
    # Simple rule-based approach
    for i, speaker1 in enumerate(speakers):
        for speaker2 in speakers[i+1:]:
            # Case 1: Role variations of same person
            # "Brief Family Member" vs "Mel Robbins' Son (Introducer)"
            if self._are_likely_same_person(speaker1, speaker2):
                # Keep the more specific name
                if len(speaker2) > len(speaker1):
                    duplicates[speaker1] = speaker2
                else:
                    duplicates[speaker2] = speaker1
    
    return duplicates

def _are_likely_same_person(self, name1: str, name2: str) -> bool:
    """Simple heuristic to detect if two names refer to the same person."""
    # Extract base names and roles
    base1, role1 = self._extract_name_and_role(name1)
    base2, role2 = self._extract_name_and_role(name2)
    
    # If one contains "Family" and other contains "Son/Daughter/Child"
    family_keywords = ['family', 'son', 'daughter', 'child', 'relative']
    if any(kw in name1.lower() for kw in family_keywords) and \
       any(kw in name2.lower() for kw in family_keywords):
        return True
    
    # If base names are similar (fuzzy match)
    if base1 and base2:
        # Simple character overlap check
        overlap = len(set(base1.lower()) & set(base2.lower()))
        if overlap > min(len(base1), len(base2)) * 0.7:
            return True
    
    return False
```

#### C. Value Contribution Check
```python
def _has_meaningful_contribution(self, episode_id: str, speaker: str) -> bool:
    """Check if speaker has meaningful knowledge contributions."""
    # Query for units attributed to this speaker
    query = """
    MATCH (mu:MeaningfulUnit)-[:PART_OF]->(e:Episode {id: $episode_id})
    WHERE mu.speaker_distribution IS NOT NULL
    WITH mu, mu.speaker_distribution as dist
    WHERE dist CONTAINS $speaker
    RETURN COUNT(mu) as unit_count, 
           AVG(SIZE(mu.text)) as avg_text_length
    """
    
    result = self.storage.neo4j_service.run_query(
        query, 
        episode_id=episode_id, 
        speaker=speaker
    )
    
    if result:
        record = result[0]
        unit_count = record['unit_count']
        avg_length = record['avg_text_length'] or 0
        
        # Simple thresholds
        if unit_count < 2 or avg_length < 50:
            return False
    
    return True
```

### 3. Integration Flow

Update `SpeakerMapper.process_episode()`:

```python
def process_episode(self, episode_id: str) -> Dict[str, str]:
    """Process episode with enhanced sanity checks."""
    # ... existing identification logic ...
    
    # NEW: Apply sanity checks before database updates
    if mappings:
        # 1. Filter out non-names
        valid_mappings = {
            k: v for k, v in mappings.items() 
            if self._is_valid_speaker_name(v)
        }
        
        # 2. Check for duplicates and merge
        all_speakers = self._get_all_episode_speakers(episode_id)
        duplicates = self._find_duplicate_speakers(all_speakers)
        
        # Apply duplicate merging to mappings
        for old_name, new_name in valid_mappings.items():
            if new_name in duplicates:
                valid_mappings[old_name] = duplicates[new_name]
        
        # 3. Log speakers with low contributions (but keep them)
        for speaker in all_speakers:
            if not self._has_meaningful_contribution(episode_id, speaker):
                logger.warning(
                    f"Speaker '{speaker}' has minimal contributions "
                    f"in episode {episode_id}"
                )
        
        # Update with sanitized mappings
        if valid_mappings:
            self._update_speakers_in_database(episode_id, valid_mappings)
            self._log_speaker_changes(episode_id, valid_mappings)
    
    return mappings
```

### 4. Database Updates

Add method to merge duplicate speakers:

```python
def _merge_duplicate_speakers(self, episode_id: str, duplicates: Dict[str, str]):
    """Merge duplicate speakers in database."""
    for old_name, new_name in duplicates.items():
        query = """
        MATCH (mu:MeaningfulUnit)-[:PART_OF]->(e:Episode {id: $episode_id})
        WHERE mu.speaker_distribution CONTAINS $old_name
        SET mu.speaker_distribution = 
            REPLACE(mu.speaker_distribution, $old_name, $new_name)
        """
        
        self.storage.neo4j_service.run_query(
            query,
            episode_id=episode_id,
            old_name=f'"{old_name}"',
            new_name=f'"{new_name}"'
        )
```

### 5. Configuration

Add minimal configuration to `PipelineConfig`:

```python
# Speaker sanity check settings
SPEAKER_MIN_NAME_LENGTH = 2
SPEAKER_MIN_UNITS = 2
SPEAKER_MIN_AVG_TEXT_LENGTH = 50
```

### 6. Testing Strategy

1. **Unit Tests**: Test each sanity check function independently
2. **Integration Test**: Process a known problematic episode
3. **Regression Test**: Ensure existing functionality unchanged

### 7. Rollout Plan

1. **Phase 1**: Implement and test locally
2. **Phase 2**: Run on existing episodes in read-only mode (log only)
3. **Phase 3**: Apply fixes to existing data
4. **Phase 4**: Enable for new episode processing

## Benefits

1. **Simplicity**: Rule-based approach, no complex ML models
2. **Maintainability**: Clear, documented rules easy to update
3. **Safety**: Non-destructive, logs all changes
4. **Automated**: No manual intervention required

## Future Enhancements (if needed)

1. LLM-based validation for edge cases
2. Configurable thresholds
3. More sophisticated duplicate detection
4. Speaker contribution quality metrics

## Success Metrics

1. Reduction in non-name "speakers" to zero
2. Automatic resolution of obvious duplicates
3. No false positives (valid speakers removed)
4. Minimal performance impact (<5% processing time increase)

## Implementation Timeline

- Core implementation: 2 hours
- Testing: 1 hour
- Documentation: 30 minutes
- Total: ~3.5 hours

## Notes

- Follows KISS principle throughout
- Uses existing infrastructure (Neo4j, logging)
- Fail-safe design won't break on edge cases
- Easy to extend with new rules as needed