#!/usr/bin/env python3
"""Diagnose why only 1 meaningful unit was created from 313 segments."""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'seeding_pipeline'))

from pathlib import Path
import json

def analyze_conversation_analyzer_prompt():
    """Analyze the conversation analyzer prompt to understand the issue."""
    
    print("=== MEANINGFUL UNIT CREATION DIAGNOSIS ===\n")
    
    print("ISSUE SUMMARY:")
    print("- 313 segments were processed from the MFM episode")
    print("- Only 1 meaningful unit was created")
    print("- This suggests the LLM grouped ALL segments into a single unit")
    print()
    
    print("PROMPT ANALYSIS:")
    print("The conversation analyzer prompt includes these guidelines:")
    print('- "A conversation unit should typically span multiple segments (average 5-10)"')
    print('- "Group segments that belong together semantically"')
    print('- "Identify clear natural boundaries where new topics begin"')
    print()
    
    print("LIKELY CAUSES:")
    print("1. The LLM may have interpreted the entire episode as one continuous topic")
    print("2. The prompt might not be explicit enough about creating MULTIPLE units")
    print("3. The LLM might be overly conservative in identifying topic boundaries")
    print("4. The transcript might genuinely be a single long discussion without clear breaks")
    print()
    
    print("CONFIGURATION INSIGHTS:")
    print("- No explicit minimum or maximum number of units is specified")
    print("- No hard limit on unit size (segments per unit)")
    print("- The prompt says 'average 5-10' but doesn't enforce this")
    print()
    
    print("RECOMMENDATIONS:")
    print("1. Add explicit guidance to create multiple units:")
    print('   "IMPORTANT: Create multiple conversation units (typically 10-50 for a full episode)"')
    print()
    print("2. Add a maximum unit size constraint:")
    print('   "No single unit should contain more than 30-40 segments"')
    print()
    print("3. Add more specific boundary detection criteria:")
    print('   "Create a new unit when: topic shifts, speaker changes for extended time, ')
    print('    story/example ends, Q&A pair completes, or after ~5-10 minutes of discussion"')
    print()
    print("4. Consider adding a fallback mechanism:")
    print("   If only 1 unit is created from >100 segments, retry with more explicit instructions")
    print()
    
    # Check if there's a configuration file
    config_path = Path("seeding_pipeline/src/core/config.py")
    if config_path.exists():
        print("CONFIGURATION FILE:")
        print(f"- Found at: {config_path}")
        print("- Check for any unit-related settings")
    
    print("\nNEXT STEPS:")
    print("1. Review the actual conversation structure returned by the LLM")
    print("2. Check if the episode genuinely has unclear boundaries")
    print("3. Consider enhancing the prompt with more explicit unit creation guidance")
    print("4. Test with a known multi-topic episode to verify the fix works")

if __name__ == "__main__":
    analyze_conversation_analyzer_prompt()