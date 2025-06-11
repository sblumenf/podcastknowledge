# Speaker Identification Prompt Engineering Guide

This guide helps you customize and optimize the speaker identification prompt for different podcast formats and requirements.

## Understanding the Default Prompt

The default prompt template is designed to work across various podcast formats:

```python
template="""Identify the actual names or descriptive roles of speakers in this podcast transcript.

METADATA:
{metadata}

SPEAKER STATISTICS:
{speaker_stats}

OPENING CONVERSATION (first 10 minutes):
{opening_segments}

Based on the metadata, conversation patterns, and content:
1. Identify actual speaker names from:
   - Self-introductions (e.g., "I'm John", "this is Sarah")
   - Address patterns (e.g., "Welcome, Dr. Smith")
   - Host/guest patterns (hosts typically introduce guests)
   - Episode metadata (podcast name, description)

2. For unidentified speakers, assign descriptive roles based on:
   - Speaking patterns (questions vs answers)
   - Conversation dominance (hosts typically speak more)
   - Topic expertise demonstrated
   - Relationship dynamics

Format your response as a valid JSON object...
"""
```

## Customization Strategies

### 1. Interview-Style Podcasts

For podcasts with clear interviewer/interviewee dynamics:

```python
interview_template = """Identify speakers in this interview podcast.

METADATA:
{metadata}

SPEAKER STATISTICS:
{speaker_stats}

OPENING CONVERSATION:
{opening_segments}

This is an interview-format podcast. Focus on:
1. The interviewer (likely asks questions, higher word count)
2. The interviewee (likely gives longer answers, may be introduced)
3. Look for phrases like:
   - "Our guest today is..."
   - "Thanks for joining us..."
   - "Tell us about..."

Interviewers often:
- Ask short questions
- Guide the conversation
- Have consistent presence throughout

Interviewees often:
- Give detailed responses
- Share personal experiences
- Are introduced by name/title

JSON Response format...
"""
```

### 2. Panel Discussion Podcasts

For multi-speaker panel formats:

```python
panel_template = """Identify speakers in this panel discussion.

METADATA:
{metadata}

SPEAKER STATISTICS:
{speaker_stats}

CONVERSATION SAMPLE:
{opening_segments}

This appears to be a panel discussion. Look for:
1. A moderator (guides discussion, asks questions to others)
2. Panelists (contribute expertise, engage in debate)
3. Patterns like:
   - "What do you think, [Name]?"
   - "[Name], would you like to respond?"
   - "I agree/disagree with [Name]"

Moderators typically:
- Have moderate speaking time (20-40%)
- Direct questions to specific people
- Summarize points

Panelists typically:
- Have variable speaking time
- Reference each other
- Provide expert opinions

JSON Response format...
"""
```

### 3. Educational/Lecture Podcasts

For educational content with primary educator:

```python
educational_template = """Identify the educator and any students/guests in this educational podcast.

METADATA:
{metadata}

STATISTICS:
{speaker_stats}

OPENING:
{opening_segments}

This is educational content. Identify:
1. The primary educator/lecturer (likely 70%+ speaking time)
2. Students asking questions (brief interventions)
3. Guest experts (moderate speaking time on specific topics)

Look for educational patterns:
- "Today's lesson..."
- "Can you explain..."
- "Great question..."
- Technical explanations

The educator usually:
- Dominates speaking time
- Provides structured content
- Responds to questions

JSON Response format...
"""
```

### 4. Conversational/Friends Podcasts

For casual conversation between friends/co-hosts:

```python
conversational_template = """Identify speakers in this conversational podcast.

METADATA:
{metadata}

STATISTICS:
{speaker_stats}

CONVERSATION:
{opening_segments}

This appears to be a casual conversation between friends/co-hosts. Note:
1. Speaking time may be more balanced (30-70% split)
2. Informal introductions or none at all
3. Inside jokes and references
4. Natural conversation flow

Look for:
- Casual name usage
- Shared experiences mentioned
- Equal participation
- Friendly banter

Since formal introductions may be rare, use:
- Any casual name drops
- Consistent speech patterns
- Role in conversation dynamic

JSON Response format...
"""
```

## Advanced Customization Techniques

### 1. Domain-Specific Templates

For specialized podcasts (medical, legal, technical):

```python
def create_domain_template(domain: str, terminology: List[str]) -> str:
    """Create domain-specific template."""
    
    term_list = "\n".join(f"- {term}" for term in terminology)
    
    return f"""Identify speakers in this {domain} podcast.

METADATA:
{{metadata}}

STATISTICS:
{{speaker_stats}}

CONVERSATION:
{{opening_segments}}

This is a specialized {domain} podcast. Domain-specific indicators:
{term_list}

Identify:
1. Domain experts (use technical terminology correctly)
2. Hosts/moderators (may ask clarifying questions)
3. Guests (vary in expertise level)

Look for {domain}-specific introductions:
- Professional titles (Dr., Professor, Attorney, etc.)
- Institutional affiliations
- Credentials mentioned

JSON Response format...
"""
```

### 2. Multi-Language Support

For non-English or multilingual podcasts:

```python
multilingual_template = """Identify speakers in this multilingual podcast.

METADATA:
{metadata}

STATISTICS:
{speaker_stats}

CONVERSATION:
{opening_segments}

Note: This podcast may contain multiple languages. Look for:
1. Names in any language
2. Titles/honorifics in local language
3. Code-switching patterns

Common introduction patterns:
- English: "I'm...", "My name is..."
- Spanish: "Soy...", "Me llamo..."
- French: "Je suis...", "Je m'appelle..."
- German: "Ich bin...", "Mein Name ist..."

Assign roles considering cultural context.

JSON Response format...
"""
```

### 3. Dynamic Prompt Building

Build prompts dynamically based on podcast characteristics:

```python
class DynamicPromptBuilder:
    def build_speaker_prompt(self, segments, metadata):
        """Build customized prompt based on content analysis."""
        
        # Analyze podcast characteristics
        stats = self._analyze_segments(segments)
        
        # Select template components
        components = []
        
        # Add base instruction
        components.append("Identify speakers in this podcast transcript.")
        
        # Add format-specific guidance
        if stats['balanced_speaking']:  # Similar speaking times
            components.append(self._get_balanced_guidance())
        elif stats['single_dominant']:  # One speaker dominates
            components.append(self._get_monologue_guidance())
        else:  # Traditional host/guest
            components.append(self._get_interview_guidance())
        
        # Add language-specific guidance if needed
        if stats['non_english_detected']:
            components.append(self._get_multilingual_guidance())
        
        # Add domain-specific guidance
        if stats['technical_terms'] > 0.3:  # High technical density
            components.append(self._get_technical_guidance())
        
        # Combine components
        prompt = "\n\n".join(components)
        
        # Add standard format requirements
        prompt += "\n\nJSON Response format..."
        
        return prompt
```

## Testing and Optimization

### 1. A/B Testing Prompts

Test different prompts on the same content:

```python
def test_prompt_variations(segments, metadata, prompt_templates):
    """Test multiple prompt templates and compare results."""
    
    results = {}
    
    for name, template in prompt_templates.items():
        # Update prompt in identifier
        identifier.prompt_builder._templates['speaker_identification'] = template
        
        # Run identification
        result = identifier.identify_speakers(segments, metadata)
        
        # Collect metrics
        results[name] = {
            'mappings': result['speaker_mappings'],
            'avg_confidence': sum(result['confidence_scores'].values()) / len(result['confidence_scores']),
            'unresolved': len(result['unresolved_speakers'])
        }
    
    # Compare results
    print("Prompt Comparison:")
    for name, metrics in results.items():
        print(f"\n{name}:")
        print(f"  - Average confidence: {metrics['avg_confidence']:.2f}")
        print(f"  - Unresolved speakers: {metrics['unresolved']}")
```

### 2. Confidence Calibration

Adjust prompts to improve confidence calibration:

```python
confidence_calibrated_template = """...

Rate your confidence for each identification:
- 0.9-1.0: Explicit self-introduction or very clear evidence
- 0.7-0.9: Strong patterns and multiple indicators
- 0.5-0.7: Probable based on patterns
- 0.3-0.5: Educated guess based on role
- 0.0-0.3: Very uncertain

Be conservative with confidence scores. When in doubt, assign lower confidence.

JSON Response format...
"""
```

### 3. Error Analysis

Analyze common identification errors:

```python
def analyze_identification_errors(ground_truth, predictions):
    """Analyze where identification goes wrong."""
    
    errors = []
    
    for speaker_id, true_name in ground_truth.items():
        pred_name = predictions.get(speaker_id, "Not identified")
        
        if true_name.lower() not in pred_name.lower():
            errors.append({
                'speaker': speaker_id,
                'true': true_name,
                'predicted': pred_name,
                'confidence': predictions.get('confidence_scores', {}).get(speaker_id, 0)
            })
    
    # Categorize errors
    error_types = {
        'missed_introduction': [],
        'wrong_role': [],
        'low_confidence': [],
        'complete_miss': []
    }
    
    for error in errors:
        if error['confidence'] < 0.5:
            error_types['low_confidence'].append(error)
        elif 'Host' in error['predicted'] and 'Host' not in error['true']:
            error_types['wrong_role'].append(error)
        # ... more categorization
    
    return error_types
```

## Best Practices

### 1. Prompt Structure

- **Be explicit**: Clearly state what you want
- **Provide examples**: Show desired output format
- **Set boundaries**: Specify what NOT to do
- **Order matters**: Put most important instructions first

### 2. Context Management

```python
# Optimize context window usage
def optimize_context(segments, max_chars=5000):
    """Select most informative segments for context."""
    
    selected = []
    char_count = 0
    
    # Prioritize segments with:
    # 1. Self-introductions
    # 2. Name mentions
    # 3. Role indicators
    
    intro_patterns = ['my name', "i'm", 'i am', 'this is']
    
    for segment in segments:
        text_lower = segment.text.lower()
        
        # High priority if contains introduction
        if any(pattern in text_lower for pattern in intro_patterns):
            selected.insert(0, segment)  # Add to front
        else:
            selected.append(segment)
        
        char_count += len(segment.text)
        
        if char_count > max_chars:
            break
    
    return selected[:50]  # Max 50 segments
```

### 3. Iterative Refinement

1. Start with the default prompt
2. Collect failure cases
3. Analyze why identification failed
4. Add specific guidance for those cases
5. Test on broader dataset
6. Repeat

### 4. Prompt Versioning

```python
class PromptVersion:
    """Track prompt versions and performance."""
    
    def __init__(self):
        self.versions = {}
        self.performance = {}
    
    def add_version(self, version_id, template, description):
        """Add a new prompt version."""
        self.versions[version_id] = {
            'template': template,
            'description': description,
            'created': datetime.now(),
            'test_results': []
        }
    
    def log_performance(self, version_id, success_rate, avg_confidence):
        """Log performance metrics for a version."""
        if version_id not in self.performance:
            self.performance[version_id] = []
        
        self.performance[version_id].append({
            'date': datetime.now(),
            'success_rate': success_rate,
            'avg_confidence': avg_confidence
        })
    
    def get_best_version(self):
        """Get the best performing version."""
        best_version = None
        best_score = 0
        
        for version_id, metrics in self.performance.items():
            if metrics:
                avg_success = sum(m['success_rate'] for m in metrics) / len(metrics)
                if avg_success > best_score:
                    best_score = avg_success
                    best_version = version_id
        
        return best_version, best_score
```

## Common Pitfalls to Avoid

1. **Over-specificity**: Don't make prompts too specific to one podcast format
2. **Assumption bias**: Avoid assuming all podcasts follow Western naming conventions
3. **Length creep**: Longer prompts aren't always better
4. **Format rigidity**: Allow for variations in JSON response format
5. **Context overload**: Don't include too much transcript context

## Conclusion

Effective prompt engineering for speaker identification requires:
- Understanding your podcast formats
- Iterative testing and refinement
- Balancing specificity with generalization
- Monitoring performance metrics
- Regular updates based on failure analysis

Remember: The best prompt is one that works reliably for YOUR specific use case.