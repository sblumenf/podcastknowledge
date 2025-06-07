"""VTT sample fixtures for testing the VTT knowledge extraction pipeline."""

from pathlib import Path
from typing import Optional, List, Dict, Any
import random
# VTT content constants
SIMPLE_VTT = """WEBVTT

00:00:00.000 --> 00:00:10.000
Welcome to our podcast. Today we're discussing artificial intelligence.

00:00:10.000 --> 00:00:20.000
AI has transformed many industries in recent years.

00:00:20.000 --> 00:00:30.000
Machine learning models can now understand and generate human language.

00:00:30.000 --> 00:00:40.000
This has led to breakthroughs in natural language processing.

00:00:40.000 --> 00:00:50.000
Thank you for listening to our discussion today.
"""

MULTI_SPEAKER_VTT = """WEBVTT

00:00:00.000 --> 00:00:08.000
<v Host>Welcome everyone. I'm joined today by Dr. Sarah Chen, an AI researcher.

00:00:08.000 --> 00:00:16.000
<v Dr. Chen>Thanks for having me. I'm excited to discuss recent AI developments.

00:00:16.000 --> 00:00:24.000
<v Host>Let's start with large language models. What's your take on their impact?

00:00:24.000 --> 00:00:32.000
<v Dr. Chen>They've revolutionized NLP. We're seeing unprecedented capabilities.

00:00:32.000 --> 00:00:40.000
<v Host>What about the ethical considerations?

00:00:40.000 --> 00:00:48.000
<v Dr. Chen>That's crucial. We need responsible AI development with proper safeguards.

00:00:48.000 --> 00:00:56.000
<v Host>Thank you for these insights, Dr. Chen.

00:00:56.000 --> 00:01:00.000
<v Dr. Chen>My pleasure. Thanks for the thoughtful questions.
"""

TECHNICAL_DISCUSSION_VTT = """WEBVTT

00:00:00.000 --> 00:00:15.000
Today we're diving deep into transformer architectures. The self-attention mechanism allows models to weigh the importance of different words in a sequence.

00:00:15.000 --> 00:00:30.000
BERT, or Bidirectional Encoder Representations from Transformers, uses masked language modeling to understand context from both directions.

00:00:30.000 --> 00:00:45.000
GPT models, on the other hand, use autoregressive training. They predict the next token based on previous tokens, making them excellent for generation tasks.

00:00:45.000 --> 00:01:00.000
The key innovation was the multi-head attention mechanism. It allows the model to attend to different representation subspaces simultaneously.

00:01:00.000 --> 00:01:15.000
Recent advances include techniques like LoRA for efficient fine-tuning and flash attention for improved computational efficiency.

00:01:15.000 --> 00:01:30.000
Quantization methods now allow us to run large models on consumer hardware by reducing precision from FP16 to INT8 or even INT4.
"""

CORRUPTED_VTT = """This is not a valid VTT file!
It doesn't have the WEBVTT header.
And it lacks proper timestamp formatting.
Random text without structure.
"""

EDGE_CASE_VTT = """WEBVTT

00:00:00.000 --> 00:00:05.000
Short segment.

00:00:05.000 --> 00:00:05.001
Very brief!

00:00:05.001 --> 00:00:10.000
Normal segment with some content.

00:00:10.000 --> 00:00:15.000


00:00:15.000 --> 00:00:20.000
Segment after empty cue.

00:00:20.000 --> 00:00:25.000
[INAUDIBLE]

00:00:25.000 --> 00:00:30.000
Segment with special characters: <>&"'

00:00:30.000 --> 00:00:35.000
Unicode test: 你好世界 🌍 مرحبا
"""


def create_simple_vtt(path: Path, duration_minutes: int = 5) -> Path:
    """Create a simple VTT file with single speaker content.
    
    Args:
        path: Path where the VTT file should be created
        duration_minutes: Duration of the content in minutes
        
    Returns:
        Path to the created VTT file
    """
    segments = []
    segments.append("WEBVTT\n")
    
    topics = [
        "artificial intelligence and machine learning",
        "natural language processing techniques",
        "computer vision applications",
        "robotics and automation",
        "data science methodologies",
        "cloud computing infrastructure",
        "cybersecurity best practices",
        "blockchain technology",
        "quantum computing basics",
        "edge computing solutions"
    ]
    
    seconds_per_segment = 10
    total_segments = (duration_minutes * 60) // seconds_per_segment
    
    for i in range(total_segments):
        start_time = i * seconds_per_segment
        end_time = start_time + seconds_per_segment
        
        start_str = f"{start_time // 60:02d}:{start_time % 60:02d}:00.000"
        end_str = f"{end_time // 60:02d}:{end_time % 60:02d}:00.000"
        
        topic = random.choice(topics)
        content = f"Now let's discuss {topic}. This is an important area of technology."
        
        segments.append(f"\n{start_str} --> {end_str}\n{content}\n")
    
    path.write_text(''.join(segments))
    return path


def create_multi_speaker_vtt(path: Path, speakers: int = 2) -> Path:
    """Create a VTT file with multiple speakers having a conversation.
    
    Args:
        path: Path where the VTT file should be created
        speakers: Number of speakers in the conversation
        
    Returns:
        Path to the created VTT file
    """
    if speakers < 2:
        speakers = 2
    if speakers > 5:
        speakers = 5
        
    speaker_names = ["Host", "Guest 1", "Guest 2", "Guest 3", "Guest 4"][:speakers]
    
    segments = []
    segments.append("WEBVTT\n")
    
    conversation_topics = [
        "What are your thoughts on the latest AI developments?",
        "How do you see this technology evolving?",
        "What challenges do you foresee?",
        "Can you share a specific example?",
        "What advice would you give to newcomers?",
        "How does this compare to traditional approaches?",
        "What's the most exciting application you've seen?",
        "Where do you think we'll be in 5 years?"
    ]
    
    responses = [
        "That's a great question. I think we're seeing unprecedented progress.",
        "The potential is enormous, but we need to be thoughtful about implementation.",
        "I've been working on this for years, and the recent advances are remarkable.",
        "Let me give you a concrete example from our recent project.",
        "The key is to start with the fundamentals and build from there.",
        "It's a paradigm shift in how we approach these problems.",
        "We're just scratching the surface of what's possible.",
        "The convergence of different technologies is creating new opportunities."
    ]
    
    time = 0
    for i in range(20):  # 20 exchanges
        speaker = speaker_names[i % len(speaker_names)]
        
        if i % 2 == 0:  # Question
            content = random.choice(conversation_topics)
        else:  # Response
            content = random.choice(responses)
            
        start_time = time
        duration = random.randint(5, 15)
        end_time = time + duration
        
        start_str = f"{start_time // 60:02d}:{start_time % 60:02d}:00.000"
        end_str = f"{end_time // 60:02d}:{end_time % 60:02d}:00.000"
        
        segments.append(f"\n{start_str} --> {end_str}\n<v {speaker}>{content}\n")
        
        time = end_time
    
    path.write_text(''.join(segments))
    return path


def create_technical_discussion_vtt(path: Path) -> Path:
    """Create a VTT file with detailed technical content.
    
    Args:
        path: Path where the VTT file should be created
        
    Returns:
        Path to the created VTT file
    """
    path.write_text(TECHNICAL_DISCUSSION_VTT)
    return path


def create_corrupted_vtt(path: Path) -> Path:
    """Create an invalid VTT file for error handling tests.
    
    Args:
        path: Path where the VTT file should be created
        
    Returns:
        Path to the created VTT file
    """
    path.write_text(CORRUPTED_VTT)
    return path


def create_edge_case_vtt(path: Path) -> Path:
    """Create a VTT file with edge cases for robust testing.
    
    Args:
        path: Path where the VTT file should be created
        
    Returns:
        Path to the created VTT file
    """
    path.write_text(EDGE_CASE_VTT)
    return path


def get_sample_vtt_content(sample_type: str = "simple") -> str:
    """Get VTT content string by type.
    
    Args:
        sample_type: Type of sample ("simple", "multi_speaker", "technical", "corrupted", "edge_case")
        
    Returns:
        VTT content string
    """
    samples = {
        "simple": SIMPLE_VTT,
        "multi_speaker": MULTI_SPEAKER_VTT,
        "technical": TECHNICAL_DISCUSSION_VTT,
        "corrupted": CORRUPTED_VTT,
        "edge_case": EDGE_CASE_VTT
    }
    return samples.get(sample_type, SIMPLE_VTT)


def create_vtt_batch(directory: Path, count: int = 5) -> List[Path]:
    """Create a batch of VTT files for testing batch processing.
    
    Args:
        directory: Directory where VTT files should be created
        count: Number of VTT files to create
        
    Returns:
        List of paths to created VTT files
    """
    directory.mkdir(exist_ok=True)
    paths = []
    
    for i in range(count):
        filename = f"episode_{i+1:03d}.vtt"
        filepath = directory / filename
        
        # Vary the types of content
        if i % 3 == 0:
            create_simple_vtt(filepath, duration_minutes=3)
        elif i % 3 == 1:
            create_multi_speaker_vtt(filepath, speakers=2 + (i % 3))
        else:
            create_technical_discussion_vtt(filepath)
            
        paths.append(filepath)
    
    return paths


# Metadata for test scenarios
VTT_METADATA = {
    "simple": {
        "description": "Basic single-speaker content",
        "duration": "50 seconds",
        "segments": 5,
        "speakers": 1
    },
    "multi_speaker": {
        "description": "Multi-speaker conversation",
        "duration": "60 seconds",
        "segments": 8,
        "speakers": 2
    },
    "technical": {
        "description": "Technical discussion with domain-specific terms",
        "duration": "90 seconds", 
        "segments": 6,
        "speakers": 1
    },
    "corrupted": {
        "description": "Invalid VTT format for error testing",
        "duration": "N/A",
        "segments": 0,
        "speakers": 0
    },
    "edge_case": {
        "description": "Edge cases including empty cues, special characters",
        "duration": "35 seconds",
        "segments": 8,
        "speakers": 1
    }
}