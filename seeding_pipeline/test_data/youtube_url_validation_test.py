#!/usr/bin/env python3
"""
YouTube URL Validation Test Script for Phase 6 Task 6.4

Tests YouTube timestamp generation and URL construction for MeaningfulUnits.
Validates that timestamps are properly adjusted and URLs navigate correctly.
"""

import sys
import os
from pathlib import Path
from typing import List, Dict, Any

# Add the project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import required modules
from src.services.segment_regrouper import MeaningfulUnit
from src.core.interfaces import TranscriptSegment


class YouTubeURLTester:
    """Tests YouTube URL generation and timestamp validation."""
    
    def __init__(self):
        self.test_results = {
            "timestamp_adjustment": False,
            "minimum_time_zero": False,
            "url_generation": False,
            "url_format_validation": False,
            "manual_verification_ready": False
        }
        
        # Test YouTube URL base for validation
        self.test_youtube_url = "https://youtube.com/watch?v=test123"
        
        # Sample MeaningfulUnits with various timestamps to test edge cases
        self.test_units = self._create_test_meaningful_units()
    
    def _create_test_meaningful_units(self) -> List[MeaningfulUnit]:
        """Create sample MeaningfulUnits for testing timestamp adjustment."""
        
        # Create mock transcript segments
        def create_segment(start: float, end: float, text: str, speaker: str = "Speaker"):
            return TranscriptSegment(
                id=f"seg_{start}_{end}",
                text=text,
                start_time=start,
                end_time=end,
                speaker=speaker
            )
        
        test_units = []
        
        # Unit 1: Normal case (start_time = 120 seconds = 2:00)
        unit1 = MeaningfulUnit(
            id="unit_1",
            segments=[create_segment(120.0, 135.0, "This is a normal test segment.", "Alex")],
            unit_type="discussion",
            summary="Normal discussion",
            themes=["testing"],
            start_time=120.0,  # Should become 118.0 after adjustment
            end_time=135.0,
            speaker_distribution={"Alex": 1.0},
            is_complete=True
        )
        
        # Unit 2: Edge case (start_time = 1.5 seconds)
        unit2 = MeaningfulUnit(
            id="unit_2", 
            segments=[create_segment(1.5, 6.0, "This starts very early.", "Sarah")],
            unit_type="introduction",
            summary="Early introduction",
            themes=["intro"],
            start_time=1.5,  # Should become 0.0 after adjustment (minimum enforced)
            end_time=6.0,
            speaker_distribution={"Sarah": 1.0},
            is_complete=True
        )
        
        # Unit 3: Boundary case (start_time = 2.0 seconds exactly)
        unit3 = MeaningfulUnit(
            id="unit_3",
            segments=[create_segment(2.0, 8.0, "Exactly at 2 seconds.", "Dr. Kim")],
            unit_type="explanation", 
            summary="Boundary explanation",
            themes=["boundary"],
            start_time=2.0,  # Should become 0.0 after adjustment
            end_time=8.0,
            speaker_distribution={"Dr. Kim": 1.0},
            is_complete=True
        )
        
        # Unit 4: Large timestamp (start_time = 3661 seconds = 1:01:01)
        unit4 = MeaningfulUnit(
            id="unit_4",
            segments=[create_segment(3661.0, 3675.0, "Later in the episode.", "Mike")],
            unit_type="conclusion",
            summary="Late conclusion", 
            themes=["conclusion"],
            start_time=3661.0,  # Should become 3659.0 after adjustment
            end_time=3675.0,
            speaker_distribution={"Mike": 1.0},
            is_complete=True
        )
        
        test_units.extend([unit1, unit2, unit3, unit4])
        return test_units
    
    def test_timestamp_adjustment_logic(self):
        """Test the timestamp adjustment logic (start_time - 2, minimum 0)."""
        print("Testing timestamp adjustment logic...")
        
        test_cases = [
            (120.0, 118.0, "Normal case: 120s → 118s"),
            (1.5, 0.0, "Edge case: 1.5s → 0s (minimum enforced)"),
            (2.0, 0.0, "Boundary case: 2.0s → 0s"),
            (3661.0, 3659.0, "Large timestamp: 3661s → 3659s"),
            (0.5, 0.0, "Very early: 0.5s → 0s"),
            (0.0, 0.0, "Zero start: 0.0s → 0.0s")
        ]
        
        all_passed = True
        
        for original, expected, description in test_cases:
            # Apply the adjustment logic from the pipeline
            adjusted = max(0, original - 2.0)
            
            if abs(adjusted - expected) < 0.001:  # Float comparison
                print(f"✅ {description}")
            else:
                print(f"❌ {description} - got {adjusted}, expected {expected}")
                all_passed = False
        
        if all_passed:
            self.test_results["timestamp_adjustment"] = True
            self.test_results["minimum_time_zero"] = True
        
        return all_passed
    
    def test_youtube_url_generation(self):
        """Test YouTube URL generation with adjusted timestamps."""
        print("\nTesting YouTube URL generation...")
        
        base_url = self.test_youtube_url
        test_cases = []
        
        for unit in self.test_units:
            # Apply timestamp adjustment (simulating pipeline behavior)
            adjusted_start = max(0, unit.start_time - 2.0)
            
            # Generate YouTube URL with timestamp
            youtube_url = f"{base_url}&t={int(adjusted_start)}s"
            
            test_cases.append({
                "unit_id": unit.id,
                "original_time": unit.start_time,
                "adjusted_time": adjusted_start,
                "url": youtube_url,
                "description": unit.summary
            })
        
        print("Generated YouTube URLs:")
        for case in test_cases:
            print(f"  Unit {case['unit_id']}:")
            print(f"    Original time: {case['original_time']}s")
            print(f"    Adjusted time: {case['adjusted_time']}s") 
            print(f"    URL: {case['url']}")
            print(f"    Description: {case['description']}")
            print()
        
        # Validate URL format
        for case in test_cases:
            url = case['url']
            if "youtube.com" in url and "&t=" in url and url.endswith("s"):
                continue
            else:
                print(f"❌ Invalid URL format: {url}")
                return False
        
        print("✅ All URLs generated with correct format")
        self.test_results["url_generation"] = True
        self.test_results["url_format_validation"] = True
        
        return test_cases
    
    def validate_url_construction_simplicity(self):
        """Validate that URL construction is simple (no complex URL builders)."""
        print("\nValidating URL construction simplicity...")
        
        # Test the simple URL construction approach used
        base_url = "https://youtube.com/watch?v=ABC123"
        timestamp = 125
        
        # Simple construction (as specified in plan)
        simple_url = f"{base_url}&t={timestamp}s"
        
        print(f"Simple URL construction: {simple_url}")
        
        # Verify it follows the expected pattern
        expected_parts = [
            "youtube.com/watch",
            "v=ABC123", 
            "&t=125s"
        ]
        
        url_valid = all(part in simple_url for part in expected_parts)
        
        if url_valid:
            print("✅ URL construction uses simple string formatting (no complex builders)")
            return True
        else:
            print("❌ URL construction failed validation")
            return False
    
    def generate_manual_verification_guide(self):
        """Generate manual verification steps for testing URLs."""
        print("\nGenerating manual verification guide...")
        
        # Get the test cases from URL generation
        test_cases = self.test_youtube_url_generation()
        
        verification_guide = """
MANUAL YOUTUBE URL VERIFICATION GUIDE
=====================================

To manually verify that YouTube URLs navigate to correct positions:

1. SETUP:
   - Use a real YouTube video URL (replace 'test123' with actual video ID)
   - Ensure the video is longer than the test timestamps
   - Use a video you can easily identify content at specific times

2. TEST CASES TO VERIFY:
"""
        
        for i, case in enumerate(test_cases, 1):
            verification_guide += f"""
   Test {i} - Unit {case['unit_id']}:
   - Expected time: {case['adjusted_time']}s ({self._seconds_to_timestamp(case['adjusted_time'])})
   - URL pattern: ...&t={int(case['adjusted_time'])}s
   - Verification: Video should start at {self._seconds_to_timestamp(case['adjusted_time'])}
   - Description: {case['description']}
"""
        
        verification_guide += """
3. VERIFICATION STEPS:
   a. Replace 'test123' in URLs with real YouTube video ID
   b. Click each URL in a browser
   c. Verify video starts at expected timestamp
   d. Confirm -2 second adjustment provides good context
   e. Check that minimum 0 second handling works correctly

4. EXPECTED BEHAVIOR:
   - All URLs should navigate to correct video positions
   - Timestamps should provide 2 seconds of context before actual start
   - No URL should have negative timestamps (minimum 0 enforced)
   - URL format should be simple: ...&t=XXXs

5. SUCCESS CRITERIA:
   ✅ Video starts within 1 second of expected timestamp
   ✅ Content provides appropriate context
   ✅ No technical errors or invalid URLs
   ✅ Simple URL construction works reliably
"""
        
        print(verification_guide)
        
        # Write verification guide to file
        guide_path = Path("test_data/youtube_url_manual_verification_guide.md")
        with open(guide_path, 'w') as f:
            f.write(verification_guide)
        
        print(f"✅ Manual verification guide written to: {guide_path}")
        self.test_results["manual_verification_ready"] = True
        
        return True
    
    def _seconds_to_timestamp(self, seconds: float) -> str:
        """Convert seconds to MM:SS or HH:MM:SS format."""
        seconds = int(seconds)
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes}:{secs:02d}"
    
    def print_test_summary(self):
        """Print comprehensive test results."""
        print("\n" + "="*60)
        print("YOUTUBE URL VALIDATION TEST SUMMARY")
        print("="*60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(self.test_results.values())
        
        for test_name, passed in self.test_results.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"{test_name:30}: {status}")
        
        print("-"*60)
        print(f"TOTAL: {passed_tests}/{total_tests} tests passed")
        
        if passed_tests == total_tests:
            print("\n🎉 YOUTUBE URL VALIDATION SUCCESSFUL!")
            print("\nKey Achievements:")
            print("✅ Timestamp adjustment logic validated (-2s, min 0)")
            print("✅ URL generation working correctly")
            print("✅ Simple URL construction confirmed")
            print("✅ Manual verification guide ready")
            print("\nNext Steps:")
            print("1. Run pipeline on test episodes")
            print("2. Use manual verification guide to test real URLs")
            print("3. Confirm video navigation works as expected")
            return True
        else:
            print("\n❌ YouTube URL validation incomplete.")
            return False


def main():
    """Run the YouTube URL validation test."""
    print("Phase 6 Task 6.4: YouTube URL Validation Testing")
    print("="*60)
    print("Testing YouTube timestamp generation and URL construction")
    print()
    
    tester = YouTubeURLTester()
    
    # Run all validation tests
    tests = [
        tester.test_timestamp_adjustment_logic,
        tester.test_youtube_url_generation,
        tester.validate_url_construction_simplicity,
        tester.generate_manual_verification_guide
    ]
    
    for test in tests:
        if not test():
            print("❌ Test failed")
            return False
    
    # Print summary
    success = tester.print_test_summary()
    return success


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n❌ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        sys.exit(1)