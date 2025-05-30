# Cleanup Tasks for VTT Knowledge Pipeline

## Speaker Diarization and Attribution Cleanup

### Problem
Speaker diarization inconsistencies create data cleanliness issues in the knowledge graph:
- The same speaker may be labeled inconsistently across segments (e.g., "Speaker 1" and "Speaker 3")
- Some dialogue may lack speaker attribution entirely
- Varying confidence levels in speaker identification lead to unreliable attribution

### Impact
- Reduces reliability of speaker-based queries
- Creates confusion in UI/UX when displaying "who said what"
- Compromises relationship accuracy between speakers and entities/topics

### Proposed Solution
1. **Speaker Reconciliation Process**
   - Implement post-processing to merge likely identical speakers
   - Use linguistic patterns and topic consistency to improve speaker matching
   - Add confidence scores to speaker attributions

2. **UI Transparency**
   - Flag uncertain speaker attributions in the UI
   - Allow manual correction of speaker identities
   - Provide clear indication when speaker is unknown or uncertain

3. **Schema Updates**
   - Add confidence property to SPOKE_ABOUT relationships
   - Create speaker reconciliation table to track merged identities
   - Add metadata about diarization quality

### Success Criteria
- Reduced number of duplicate speaker entities
- Improved consistency in speaker attribution
- Clear indication of attribution confidence in the graph
- UI components that appropriately handle uncertain attributions