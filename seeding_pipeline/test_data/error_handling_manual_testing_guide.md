
MANUAL ERROR HANDLING TESTING GUIDE
===================================

This guide provides step-by-step instructions for manually testing error handling
and complete episode rejection in the unified pipeline.

## Prerequisites
1. Neo4j database running and accessible
2. Pipeline properly configured
3. Test VTT files created (see created files in test_data/)

## Test Scenario 1: Speaker Identification Failure

### Setup:
- Use: test_data/speaker_identification_fail.vtt
- Episode ID: test_speaker_identification_fail

### Steps:
1. Clear any existing data for test episode ID
2. Run pipeline on speaker_identification_fail.vtt
3. Verify pipeline returns failed status
4. Check logs for SpeakerIdentificationError
5. Query Neo4j to confirm NO data stored

### Expected Results:
✅ Pipeline status: failed
✅ Error logged: SpeakerIdentificationError
✅ Episode count in Neo4j: 0
✅ MeaningfulUnit count: 0
✅ Entity count: 0
✅ No partial data exists

### Neo4j Verification Queries:
```cypher
MATCH (e:Episode {id: 'test_speaker_identification_fail'}) RETURN COUNT(e);
MATCH (e:Episode {id: 'test_speaker_identification_fail'})-[:PART_OF]->(mu) RETURN COUNT(mu);
MATCH (e:Episode {id: 'test_speaker_identification_fail'})-[:MENTIONS]->(entity) RETURN COUNT(entity);
```
All queries should return 0.

## Test Scenario 2: Conversation Analysis Failure

### Setup:
- Use: test_data/conversation_analysis_fail.vtt
- Episode ID: test_conversation_analysis_fail

### Steps:
1. Clear any existing data for test episode ID
2. Run pipeline on conversation_analysis_fail.vtt
3. Verify pipeline returns failed status
4. Check logs for ConversationAnalysisError
5. Query Neo4j to confirm NO data stored

### Expected Results:
✅ Pipeline status: failed
✅ Error logged: ConversationAnalysisError
✅ All Neo4j queries return 0 (no partial data)

## Test Scenario 3: Extraction Error Handling

### Setup:
- Use: test_data/extraction_error_fail.vtt
- Episode ID: test_extraction_error_fail

### Steps:
1. Clear any existing data for test episode ID
2. Run pipeline on extraction_error_fail.vtt
3. Verify pipeline returns failed status
4. Check logs for ExtractionError
5. Query Neo4j to confirm NO data stored

### Expected Results:
✅ Pipeline status: failed
✅ Error logged: ExtractionError
✅ Complete episode rejection confirmed
✅ No orphaned data in database

## Critical Validation Points

### 1. Complete Episode Rejection
- NO partial data should ever exist for failed episodes
- Database should be completely clean after failures
- Transaction rollback should work properly

### 2. Error Logging Verification
- Check application logs for proper error messages
- Verify error severity levels are appropriate
- Confirm episode IDs and context are included

### 3. No Data Persistence
- Failed episodes should leave NO trace in Neo4j
- All node types should have zero counts
- All relationship types should have zero counts

## Debugging Failed Tests

If error handling tests fail:

1. **Partial Data Found**: Check transaction boundaries and rollback logic
2. **Missing Error Logs**: Verify logging configuration and levels
3. **Wrong Error Types**: Check exception handling hierarchy
4. **Cleanup Issues**: Verify error cleanup routines

## Success Criteria Summary

✅ All failure scenarios properly reject episodes
✅ No partial data persists in any failure case
✅ Appropriate error messages logged
✅ Database remains clean after failures
✅ Pipeline status correctly indicates failure
✅ Transaction rollback works correctly

## Manual Testing Commands

### Clear Test Data:
```cypher
MATCH (e:Episode) WHERE e.id STARTS WITH 'test_' DETACH DELETE e;
```

### Verify Clean Database:
```cypher
MATCH (e:Episode) WHERE e.id STARTS WITH 'test_' RETURN COUNT(e);
```

### Check All Test Episodes:
```cypher
MATCH (e:Episode) WHERE e.id IN [
  'test_speaker_identification_fail',
  'test_conversation_analysis_fail', 
  'test_extraction_error_fail'
] RETURN e.id, COUNT(e);
```

All counts should be 0 after failed processing attempts.
