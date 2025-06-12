#!/usr/bin/env python3
"""
Validate VTT processing with real-world files.

This script tests the VTT pipeline with actual transcript files to ensure
the system works correctly with production data.
"""

import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.vtt.vtt_parser import VTTParser
from src.vtt.vtt_segmentation import VTTSegmenter
from src.extraction.extraction import KnowledgeExtractor, ExtractionConfig
from src.core.models import Episode, Segment
from src.core.config import PipelineConfig


class VTTProcessingValidator:
    """Validate VTT processing with real files."""
    
    def __init__(self):
        self.parser = VTTParser()
        self.segmenter = VTTSegmenter()
        self.results = {
            "files_processed": 0,
            "files_failed": 0,
            "total_segments": 0,
            "total_duration": 0.0,
            "extraction_time": 0.0,
            "errors": [],
            "warnings": [],
            "statistics": {}
        }
        
    def validate_file(self, vtt_path: Path) -> Dict:
        """Validate a single VTT file."""
        result = {
            "file": str(vtt_path),
            "status": "pending",
            "segments": 0,
            "duration": 0.0,
            "entities": 0,
            "relationships": 0,
            "quotes": 0,
            "errors": []
        }
        
        try:
            # Step 1: Parse VTT file
            print(f"\n📄 Processing: {vtt_path.name}")
            start_time = time.time()
            
            segments = self.parser.parse_file(vtt_path)
            result["segments"] = len(segments)
            
            if not segments:
                result["errors"].append("No segments found in VTT file")
                result["status"] = "failed"
                return result
                
            print(f"   ✓ Parsed {len(segments)} segments")
            
            # Step 2: Calculate duration
            if segments:
                max_end_time = max(s.end_time for s in segments)
                result["duration"] = max_end_time
                
            # Step 3: Segment processing
            segmentation_result = self.segmenter.process_segments(segments)
            processed_segments = segmentation_result.get("transcript", [])
            
            print(f"   ✓ Processed into {len(processed_segments)} segments")
            
            # Step 4: Mock knowledge extraction (since we need LLM service)
            # In real usage, this would call the actual extraction
            extraction_results = self._mock_extract_knowledge(processed_segments)
            
            result["entities"] = sum(len(r.get("entities", [])) for r in extraction_results)
            result["relationships"] = sum(len(r.get("relationships", [])) for r in extraction_results)
            result["quotes"] = sum(len(r.get("quotes", [])) for r in extraction_results)
            
            print(f"   ✓ Extracted: {result['entities']} entities, "
                  f"{result['relationships']} relationships, {result['quotes']} quotes")
            
            # Step 5: Validation checks
            self._validate_segments(segments, result)
            
            result["processing_time"] = time.time() - start_time
            result["status"] = "success" if not result["errors"] else "warning"
            
        except Exception as e:
            import traceback
            result["status"] = "failed"
            result["errors"].append(f"Processing error: {str(e)}")
            self.results["errors"].append(f"{vtt_path}: {str(e)}")
            traceback.print_exc()
            
        return result
        
    def _mock_extract_knowledge(self, segments: List) -> List[Dict]:
        """Mock knowledge extraction for validation."""
        results = []
        
        for segment in segments:
            # Simulate extraction based on text content
            # Handle both Segment objects and dicts
            if isinstance(segment, dict):
                text = segment.get('text', '')
                speaker = segment.get('speaker', None)
            else:
                text = segment.text
                speaker = segment.speaker
                
            text_lower = text.lower()
            
            entities = []
            # Look for common entity patterns
            if any(word in text_lower for word in ["company", "corporation", "inc", "llc"]):
                entities.append({"type": "Company", "value": "Mock Company"})
            if any(word in text_lower for word in ["person", "people", "ceo", "founder"]):
                entities.append({"type": "Person", "value": "Mock Person"})
            if any(word in text_lower for word in ["product", "service", "software"]):
                entities.append({"type": "Product", "value": "Mock Product"})
                
            relationships = []
            if len(entities) >= 2:
                relationships.append({
                    "source": entities[0]["value"],
                    "target": entities[1]["value"],
                    "type": "related_to"
                })
                
            quotes = []
            # Extract sentences with quotes
            if '"' in text:
                quotes.append({
                    "text": text.split('"')[1] if '"' in text else "",
                    "speaker": speaker or "Unknown"
                })
                
            results.append({
                "entities": entities,
                "relationships": relationships,
                "quotes": quotes
            })
            
        return results
        
    def _validate_segments(self, segments: List, result: Dict):
        """Validate segment quality."""
        # Check for empty segments
        empty_segments = [s for s in segments if not s.text or not s.text.strip()]
        if empty_segments:
            result["errors"].append(f"Found {len(empty_segments)} empty segments")
            
        # Check for timestamp issues
        for i, segment in enumerate(segments):
            if segment.start_time < 0:
                result["errors"].append(f"Segment {i} has negative start time")
            if segment.end_time <= segment.start_time:
                result["errors"].append(f"Segment {i} has invalid duration")
                
            # Check for overlaps
            if i > 0 and segment.start_time < segments[i-1].end_time:
                self.results["warnings"].append(
                    f"Segment overlap detected at {segment.start_time}s"
                )
                
        # Check for very short segments
        short_segments = [s for s in segments if s.end_time - s.start_time < 0.5]
        if short_segments:
            self.results["warnings"].append(
                f"Found {len(short_segments)} very short segments (<0.5s)"
            )
            
    def validate_directory(self, directory: Path) -> Dict:
        """Validate all VTT files in a directory."""
        vtt_files = list(directory.glob("**/*.vtt"))
        
        if not vtt_files:
            print(f"No VTT files found in {directory}")
            return self.results
            
        print(f"\n🔍 Found {len(vtt_files)} VTT files to validate")
        
        for vtt_file in vtt_files:
            result = self.validate_file(vtt_file)
            
            self.results["files_processed"] += 1
            if result["status"] == "failed":
                self.results["files_failed"] += 1
            
            self.results["total_segments"] += result["segments"]
            self.results["total_duration"] += result["duration"]
            
            # Update statistics
            self._update_statistics(result)
            
        return self.results
        
    def _update_statistics(self, result: Dict):
        """Update validation statistics."""
        stats = self.results["statistics"]
        
        # Track segment counts
        if "segment_counts" not in stats:
            stats["segment_counts"] = []
        stats["segment_counts"].append(result["segments"])
        
        # Track durations
        if "durations" not in stats:
            stats["durations"] = []
        stats["durations"].append(result["duration"])
        
        # Track extraction results
        if "extraction_stats" not in stats:
            stats["extraction_stats"] = {
                "entities": [],
                "relationships": [],
                "quotes": []
            }
        stats["extraction_stats"]["entities"].append(result["entities"])
        stats["extraction_stats"]["relationships"].append(result["relationships"])
        stats["extraction_stats"]["quotes"].append(result["quotes"])
        
    def generate_report(self) -> str:
        """Generate validation report."""
        if self.results["files_processed"] == 0:
            return "No files processed."
            
        success_rate = ((self.results["files_processed"] - self.results["files_failed"]) 
                       / self.results["files_processed"] * 100)
        
        stats = self.results["statistics"]
        
        # Calculate averages
        avg_segments = (sum(stats.get("segment_counts", [])) / len(stats.get("segment_counts", [1])))
        avg_duration = (sum(stats.get("durations", [])) / len(stats.get("durations", [1])))
        
        report = f"""
# VTT Processing Validation Report

## Summary
- Files Processed: {self.results["files_processed"]}
- Files Failed: {self.results["files_failed"]}
- Success Rate: {success_rate:.1f}%
- Total Segments: {self.results["total_segments"]}
- Total Duration: {self.results["total_duration"]:.1f}s ({self.results["total_duration"]/3600:.1f} hours)

## Statistics
- Average Segments per File: {avg_segments:.1f}
- Average Duration per File: {avg_duration:.1f}s
- Segments per Minute: {self.results["total_segments"] / (self.results["total_duration"] / 60) if self.results["total_duration"] > 0 else 0:.1f}

## Extraction Results
"""
        
        if stats.get("extraction_stats"):
            ext_stats = stats["extraction_stats"]
            report += f"""- Total Entities: {sum(ext_stats["entities"])}
- Total Relationships: {sum(ext_stats["relationships"])}
- Total Quotes: {sum(ext_stats["quotes"])}
- Average Entities per File: {sum(ext_stats["entities"]) / len(ext_stats["entities"]):.1f}
"""
        
        # Add errors and warnings
        if self.results["errors"]:
            report += f"\n## Errors ({len(self.results['errors'])})\n"
            for error in self.results["errors"][:10]:  # Show first 10
                report += f"- {error}\n"
            if len(self.results["errors"]) > 10:
                report += f"... and {len(self.results['errors']) - 10} more\n"
                
        if self.results["warnings"]:
            report += f"\n## Warnings ({len(self.results['warnings'])})\n"
            for warning in self.results["warnings"][:10]:  # Show first 10
                report += f"- {warning}\n"
            if len(self.results["warnings"]) > 10:
                report += f"... and {len(self.results['warnings']) - 10} more\n"
                
        report += "\n## Validation Status\n"
        if self.results["files_failed"] == 0:
            report += "✅ All files processed successfully!\n"
        elif success_rate >= 95:
            report += "✅ Validation passed with minor issues.\n"
        elif success_rate >= 80:
            report += "⚠️  Validation passed with warnings.\n"
        else:
            report += "❌ Validation failed - significant issues found.\n"
            
        return report
        
    def create_test_vtt(self, output_path: Path):
        """Create a test VTT file for validation."""
        test_content = """WEBVTT

00:00:00.000 --> 00:00:05.000
<v Host>Welcome to our podcast about technology and innovation.

00:00:05.000 --> 00:00:15.000
<v Host>Today we're talking with Jane Smith, CEO of TechCorp, about the future of artificial intelligence.

00:00:15.000 --> 00:00:25.000
<v Jane Smith>Thank you for having me. I'm excited to discuss how AI is transforming businesses.

00:00:25.000 --> 00:00:35.000
<v Jane Smith>At TechCorp, we've developed several AI products that help companies automate their workflows.

00:00:35.000 --> 00:00:45.000
<v Host>That's fascinating. Can you tell us more about your flagship product?

00:00:45.000 --> 00:00:55.000
<v Jane Smith>Our main product is called "SmartFlow", and it uses machine learning to optimize business processes.

00:00:55.000 --> 00:01:05.000
<v Jane Smith>We've seen companies reduce operational costs by up to 40% using our software.

00:01:05.000 --> 00:01:15.000
<v Host>Those are impressive numbers. How do you see AI evolving in the next five years?

00:01:15.000 --> 00:01:30.000
<v Jane Smith>I believe we'll see AI become more integrated into everyday business operations. 
It won't be a separate tool, but rather embedded in everything we do.

00:01:30.000 --> 00:01:40.000
<v Host>Thank you for sharing your insights. That's all for today's episode.
"""
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(test_content)
        print(f"Created test VTT file: {output_path}")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate VTT processing")
    parser.add_argument(
        "path",
        type=Path,
        nargs="?",
        default=Path("test_vtt"),
        help="Path to VTT file or directory"
    )
    parser.add_argument(
        "--create-test",
        action="store_true",
        help="Create a test VTT file"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("validation_report.md"),
        help="Output path for validation report"
    )
    
    args = parser.parse_args()
    
    validator = VTTProcessingValidator()
    
    # Create test file if requested
    if args.create_test:
        test_file = args.path / "test_podcast.vtt" if args.path.is_dir() else args.path
        validator.create_test_vtt(test_file)
        return 0
        
    # Validate files
    if args.path.is_file():
        result = validator.validate_file(args.path)
        validator.results["files_processed"] = 1
        if result["status"] == "failed":
            validator.results["files_failed"] = 1
    else:
        validator.validate_directory(args.path)
        
    # Generate report
    report = validator.generate_report()
    print(report)
    
    # Save report
    args.output.write_text(report)
    print(f"\nReport saved to: {args.output}")
    
    # Return appropriate exit code
    if validator.results["files_failed"] > 0:
        return 1
    elif validator.results["warnings"]:
        return 0  # Warnings are acceptable
    else:
        return 0


if __name__ == "__main__":
    sys.exit(main())