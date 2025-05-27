#!/usr/bin/env python3
"""
Validate audio module by comparing with monolithic implementation.

This script runs both the monolithic and modular audio processing
implementations side-by-side and compares their outputs.
"""

import sys
import os
import json
import time
import tempfile
from pathlib import Path
from typing import Dict, Any, List
import argparse

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import modular version
from src.providers.audio import WhisperAudioProvider, MockAudioProvider
from src.core import TranscriptSegment, DiarizationSegment

# Add monolith parent to path
monolith_root = project_root.parent
sys.path.insert(0, str(monolith_root))


def compare_transcripts(monolith_segments: List[Dict], modular_segments: List[TranscriptSegment]) -> Dict[str, Any]:
    """Compare transcript segments from both implementations."""
    comparison = {
        "segment_count_match": len(monolith_segments) == len(modular_segments),
        "monolith_count": len(monolith_segments),
        "modular_count": len(modular_segments),
        "text_differences": [],
        "timing_differences": [],
        "average_text_similarity": 0.0,
    }
    
    # Compare segments
    min_segments = min(len(monolith_segments), len(modular_segments))
    total_similarity = 0.0
    
    for i in range(min_segments):
        mono_seg = monolith_segments[i]
        mod_seg = modular_segments[i]
        
        # Compare text
        mono_text = mono_seg.get("text", "").strip()
        mod_text = mod_seg.text.strip()
        
        if mono_text != mod_text:
            # Calculate similarity
            from difflib import SequenceMatcher
            similarity = SequenceMatcher(None, mono_text, mod_text).ratio()
            total_similarity += similarity
            
            if similarity < 0.95:  # Only report significant differences
                comparison["text_differences"].append({
                    "segment": i,
                    "monolith": mono_text[:100] + "..." if len(mono_text) > 100 else mono_text,
                    "modular": mod_text[:100] + "..." if len(mod_text) > 100 else mod_text,
                    "similarity": similarity
                })
        else:
            total_similarity += 1.0
            
        # Compare timing
        mono_start = mono_seg.get("start", 0)
        mono_end = mono_seg.get("end", 0)
        mod_start = mod_seg.start_time
        mod_end = mod_seg.end_time
        
        timing_diff = abs(mono_start - mod_start) + abs(mono_end - mod_end)
        if timing_diff > 0.1:  # More than 100ms difference
            comparison["timing_differences"].append({
                "segment": i,
                "monolith_timing": f"{mono_start:.2f}-{mono_end:.2f}",
                "modular_timing": f"{mod_start:.2f}-{mod_end:.2f}",
                "difference": timing_diff
            })
            
    comparison["average_text_similarity"] = total_similarity / min_segments if min_segments > 0 else 0.0
    
    return comparison


def compare_diarization(monolith_map: Dict, modular_segments: List[DiarizationSegment]) -> Dict[str, Any]:
    """Compare diarization results from both implementations."""
    # Convert modular segments to map format for comparison
    modular_map = {}
    for segment in modular_segments:
        step = 0.1
        current = segment.start_time
        while current <= segment.end_time:
            modular_map[current] = segment.speaker
            current += step
            
    comparison = {
        "monolith_speakers": len(set(monolith_map.values())) if monolith_map else 0,
        "modular_speakers": len(set(s.speaker for s in modular_segments)) if modular_segments else 0,
        "total_time_points": len(monolith_map),
        "matching_assignments": 0,
        "mismatch_rate": 0.0,
    }
    
    if monolith_map and modular_map:
        # Compare speaker assignments at common time points
        matches = 0
        total = 0
        
        for time_point, mono_speaker in monolith_map.items():
            if time_point in modular_map:
                total += 1
                # Just check if both assigned a speaker (not exact match due to different naming)
                if modular_map[time_point] is not None:
                    matches += 1
                    
        comparison["matching_assignments"] = matches
        comparison["mismatch_rate"] = 1.0 - (matches / total) if total > 0 else 0.0
        
    return comparison


def run_monolith_processing(audio_path: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Run the monolithic audio processing."""
    try:
        # Import monolithic functions
        from podcast_knowledge_system_enhanced import (
            transcribe_audio,
            diarize_speakers,
            align_transcript_with_diarization
        )
        
        print("Running monolithic audio processing...")
        start_time = time.time()
        
        # Transcribe
        transcript_segments = transcribe_audio(
            audio_path,
            use_faster_whisper=config.get("use_faster_whisper", True),
            whisper_model_size=config.get("whisper_model_size", "large-v3")
        )
        
        # Diarize
        speaker_map = diarize_speakers(
            audio_path,
            min_speakers=config.get("min_speakers", 1),
            max_speakers=config.get("max_speakers", 10)
        )
        
        # Align
        aligned_segments = align_transcript_with_diarization(transcript_segments, speaker_map)
        
        processing_time = time.time() - start_time
        
        return {
            "success": True,
            "transcript_segments": aligned_segments,
            "speaker_map": speaker_map,
            "processing_time": processing_time,
            "error": None
        }
        
    except Exception as e:
        return {
            "success": False,
            "transcript_segments": [],
            "speaker_map": {},
            "processing_time": 0,
            "error": str(e)
        }


def run_modular_processing(audio_path: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Run the modular audio processing."""
    try:
        print("Running modular audio processing...")
        start_time = time.time()
        
        # Create provider
        provider = WhisperAudioProvider(config)
        
        # Transcribe
        transcript_segments = provider.transcribe(audio_path)
        
        # Diarize
        diarization_segments = provider.diarize(audio_path)
        
        # Align
        aligned_segments = provider.align_transcript_with_diarization(
            transcript_segments,
            diarization_segments
        )
        
        processing_time = time.time() - start_time
        
        # Clean up resources
        provider.cleanup_resources()
        
        return {
            "success": True,
            "transcript_segments": aligned_segments,
            "diarization_segments": diarization_segments,
            "processing_time": processing_time,
            "health_check": provider.health_check(),
            "error": None
        }
        
    except Exception as e:
        return {
            "success": False,
            "transcript_segments": [],
            "diarization_segments": [],
            "processing_time": 0,
            "health_check": {},
            "error": str(e)
        }


def validate_audio_module(audio_path: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Main validation function."""
    print(f"Validating audio module with file: {audio_path}")
    print(f"Configuration: {json.dumps(config, indent=2)}")
    print("-" * 80)
    
    # Run both implementations
    monolith_result = run_monolith_processing(audio_path, config)
    modular_result = run_modular_processing(audio_path, config)
    
    # Compare results
    validation_result = {
        "audio_file": audio_path,
        "config": config,
        "monolith": {
            "success": monolith_result["success"],
            "processing_time": monolith_result["processing_time"],
            "error": monolith_result["error"],
        },
        "modular": {
            "success": modular_result["success"],
            "processing_time": modular_result["processing_time"],
            "error": modular_result["error"],
            "health_check": modular_result.get("health_check", {})
        },
        "comparison": {}
    }
    
    # Only compare if both succeeded
    if monolith_result["success"] and modular_result["success"]:
        # Compare transcripts
        transcript_comparison = compare_transcripts(
            monolith_result["transcript_segments"],
            modular_result["transcript_segments"]
        )
        
        # Compare diarization
        diarization_comparison = compare_diarization(
            monolith_result["speaker_map"],
            modular_result.get("diarization_segments", [])
        )
        
        validation_result["comparison"] = {
            "transcripts": transcript_comparison,
            "diarization": diarization_comparison,
            "performance_ratio": modular_result["processing_time"] / monolith_result["processing_time"]
                if monolith_result["processing_time"] > 0 else None
        }
        
    return validation_result


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Validate audio module implementation")
    parser.add_argument("audio_file", help="Path to audio file for testing")
    parser.add_argument("--model-size", default="base", help="Whisper model size")
    parser.add_argument("--use-faster-whisper", action="store_true", help="Use faster-whisper")
    parser.add_argument("--device", default="cpu", help="Device to use (cpu/cuda)")
    parser.add_argument("--output", help="Output JSON file for results")
    parser.add_argument("--use-mock", action="store_true", help="Use mock provider for testing")
    
    args = parser.parse_args()
    
    # Prepare configuration
    config = {
        "whisper_model_size": args.model_size,
        "use_faster_whisper": args.use_faster_whisper,
        "device": args.device,
        "enable_diarization": True,
    }
    
    # Validate
    if args.use_mock:
        print("Using mock provider for testing...")
        # Create a mock validation
        mock_provider = MockAudioProvider()
        segments = mock_provider.transcribe("fake.mp3")
        print(f"Mock transcription produced {len(segments)} segments")
        validation_result = {"mock_test": "success", "segments": len(segments)}
    else:
        validation_result = validate_audio_module(args.audio_file, config)
    
    # Print results
    print("\n" + "=" * 80)
    print("VALIDATION RESULTS")
    print("=" * 80)
    print(json.dumps(validation_result, indent=2))
    
    # Save results if requested
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(validation_result, f, indent=2)
        print(f"\nResults saved to: {args.output}")
        
    # Return success/failure
    if validation_result.get("monolith", {}).get("success") and \
       validation_result.get("modular", {}).get("success"):
        
        # Check similarity
        similarity = validation_result.get("comparison", {}).get("transcripts", {}).get("average_text_similarity", 0)
        if similarity > 0.9:
            print("\n✅ VALIDATION PASSED: Outputs are similar enough")
            return 0
        else:
            print(f"\n⚠️  VALIDATION WARNING: Low similarity ({similarity:.2%})")
            return 1
    else:
        print("\n❌ VALIDATION FAILED: One or both implementations failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())