# Sentiment Analysis Implementation Plan

## Overview
Implement comprehensive sentiment analysis for MeaningfulUnits in the podcast knowledge pipeline. This will analyze emotional tone, speaker attitudes, and conversation dynamics.

## Design Principles
1. **Multi-dimensional Analysis**: Beyond positive/negative - capture nuanced emotions
2. **Speaker-aware**: Track sentiment by speaker and interactions
3. **Context-sensitive**: Consider conversation type and themes
4. **Temporal Tracking**: Monitor sentiment changes over time
5. **Schema-less Integration**: Allow dynamic emotion types like entities

## Component Structure

### 1. Core Sentiment Analyzer (`sentiment_analyzer.py`)
**Location**: `/src/extraction/sentiment_analyzer.py`

**Key Classes**:
- `SentimentAnalyzer`: Main analyzer class
- `SentimentResult`: Result dataclass
- `EmotionalDimension`: Emotion categories
- `SentimentConfig`: Configuration

**Core Methods**:
- `analyze_meaningful_unit()`: Main analysis method
- `analyze_speaker_sentiment()`: Per-speaker analysis
- `analyze_interaction_sentiment()`: Inter-speaker dynamics
- `detect_sentiment_shifts()`: Temporal changes
- `extract_emotional_moments()`: Key emotional points

### 2. Sentiment Types (Schema-less)
**Base Dimensions**:
- Polarity: positive, negative, neutral, mixed
- Emotions: joy, sadness, anger, fear, surprise, disgust, trust, anticipation
- Attitudes: skeptical, enthusiastic, critical, supportive, curious, defensive
- Energy: high-energy, calm, tense, relaxed
- Engagement: engaged, disengaged, passionate, indifferent

**Dynamic Discovery**: Allow LLM to discover context-specific sentiments

### 3. Analysis Levels

#### Level 1: Unit-level Sentiment
- Overall emotional tone of MeaningfulUnit
- Dominant emotions present
- Sentiment distribution

#### Level 2: Speaker-level Sentiment
- Individual speaker emotional states
- Speaker sentiment evolution
- Emotional consistency/variability

#### Level 3: Interaction Sentiment
- Sentiment between speakers
- Agreement/disagreement patterns
- Emotional contagion effects

#### Level 4: Temporal Sentiment
- Sentiment trajectory across unit
- Emotional peaks and valleys
- Sentiment shift triggers

### 4. Integration Points

#### With MeaningfulUnits
- Access to full context via unit.text
- Use speaker_distribution for speaker analysis
- Leverage themes for context
- Consider unit_type for appropriate analysis

#### With Knowledge Extraction
- Link sentiments to entities (e.g., positive sentiment toward a product)
- Connect sentiments to insights
- Relate sentiments to quotes

#### With Pipeline
- Add to `_extract_knowledge()` method
- Store sentiment data with MeaningfulUnits
- Include in extraction results

## Implementation Steps

### Phase 1: Core Infrastructure
1. Create `sentiment_analyzer.py` with base classes
2. Define sentiment data structures
3. Implement configuration system
4. Add logging and error handling

### Phase 2: Basic Analysis
1. Implement polarity detection (positive/negative/neutral)
2. Add emotion detection (8 basic emotions)
3. Create unit-level analysis method
4. Add confidence scoring

### Phase 3: Advanced Features
1. Implement speaker-level analysis
2. Add interaction sentiment detection
3. Create temporal analysis
4. Add sentiment shift detection

### Phase 4: Schema-less Enhancement
1. Allow dynamic sentiment discovery
2. Implement context-specific sentiment types
3. Add domain adaptation
4. Create sentiment relationship detection

### Phase 5: Integration
1. Update `extraction.py` to include sentiment
2. Modify `unified_pipeline.py` to process sentiments
3. Update storage for sentiment data
4. Add sentiment to extraction results

## Data Structures

### SentimentResult
```python
@dataclass
class SentimentResult:
    unit_id: str
    overall_sentiment: SentimentScore
    speaker_sentiments: Dict[str, SpeakerSentiment]
    emotional_moments: List[EmotionalMoment]
    sentiment_flow: SentimentFlow
    interaction_dynamics: InteractionDynamics
    discovered_sentiments: List[DiscoveredSentiment]
    confidence: float
    metadata: Dict[str, Any]
```

### SentimentScore
```python
@dataclass
class SentimentScore:
    polarity: str  # positive, negative, neutral, mixed
    score: float  # -1.0 to 1.0
    emotions: Dict[str, float]  # emotion -> intensity
    attitudes: Dict[str, float]  # attitude -> intensity
    energy_level: float  # 0.0 to 1.0
    engagement_level: float  # 0.0 to 1.0
```

## Success Criteria
1. Accurately identifies sentiment in various conversation types
2. Handles multi-speaker dynamics
3. Discovers context-specific sentiments
4. Integrates seamlessly with existing pipeline
5. Provides actionable insights
6. Performs efficiently on MeaningfulUnits

## Testing Strategy
1. Unit tests for each analysis method
2. Integration tests with MeaningfulUnits
3. Validation against known emotional content
4. Performance testing with large units
5. Schema-less discovery validation

## Future Enhancements
1. Sentiment reasoning chains
2. Cultural sentiment adaptation
3. Sarcasm and irony detection
4. Emotional intelligence metrics
5. Sentiment prediction