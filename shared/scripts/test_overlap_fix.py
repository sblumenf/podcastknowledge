#!/usr/bin/env python3
"""Test script to demonstrate the overlapping units issue and fix."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'seeding_pipeline'))

from src.core.conversation_models.conversation import ConversationStructure, ConversationUnit, ConversationFlow, StructuralInsights

def test_current_validation():
    """Test that current validation incorrectly allows overlaps."""
    print("=== Testing Current Validation ===")
    
    # Create overlapping units
    units = [
        ConversationUnit(
            start_index=0,
            end_index=48,
            unit_type='topic_discussion',
            description='First unit',
            completeness='complete',
            confidence=0.8
        ),
        ConversationUnit(
            start_index=49,
            end_index=56,  # Ends at 56
            unit_type='topic_discussion', 
            description='Second unit',
            completeness='complete',
            confidence=0.8
        ),
        ConversationUnit(
            start_index=56,  # Starts at 56 - OVERLAP!
            end_index=60,
            unit_type='topic_discussion',
            description='Third unit',
            completeness='complete',
            confidence=0.8
        )
    ]
    
    try:
        structure = ConversationStructure(
            units=units,
            themes=[],
            boundaries=[],
            flow=ConversationFlow(
                opening='Test',
                development='Test',
                conclusion='Test'
            ),
            insights=StructuralInsights(
                fragmentation_issues=[],
                missing_context=[],
                natural_boundaries=[],
                overall_coherence=0.8
            ),
            total_segments=100
        )
        print("❌ PROBLEM: Overlapping units were allowed! No error raised.")
        print(f"   Unit 1 ends at: {units[1].end_index}")
        print(f"   Unit 2 starts at: {units[2].start_index}")
        print("   These should not be allowed to overlap!\n")
        return False
    except ValueError as e:
        print("✅ Good: Validation caught the overlap")
        print(f"   Error: {e}\n")
        return True

def demonstrate_fix_invalid_indices():
    """Show how to fix overlapping units in _fix_invalid_indices."""
    print("=== Demonstrating Fix for Overlapping Units ===")
    
    def fix_overlapping_units(units_list):
        """Fix overlapping units by adjusting end indices."""
        if not units_list:
            return units_list
            
        # Sort by start index
        sorted_units = sorted(units_list, key=lambda u: u['start_index'])
        
        # Fix overlaps
        for i in range(1, len(sorted_units)):
            prev_unit = sorted_units[i-1]
            curr_unit = sorted_units[i]
            
            if prev_unit['end_index'] >= curr_unit['start_index']:
                old_end = prev_unit['end_index']
                prev_unit['end_index'] = curr_unit['start_index'] - 1
                print(f"Fixed overlap: Unit {i-1} end_index changed from {old_end} to {prev_unit['end_index']}")
        
        return sorted_units
    
    # Test data with overlaps
    units = [
        {
            'start_index': 0,
            'end_index': 48,
            'unit_type': 'topic_discussion',
            'description': 'First unit',
            'completeness': 'complete',
            'confidence': 0.8
        },
        {
            'start_index': 49,
            'end_index': 56,  # Overlaps with next
            'unit_type': 'topic_discussion', 
            'description': 'Second unit',
            'completeness': 'complete',
            'confidence': 0.8
        },
        {
            'start_index': 56,  # Starts where previous ends
            'end_index': 60,
            'unit_type': 'topic_discussion',
            'description': 'Third unit',
            'completeness': 'complete',
            'confidence': 0.8
        }
    ]
    
    print("Original units:")
    for i, unit in enumerate(units):
        print(f"  Unit {i}: segments {unit['start_index']}-{unit['end_index']}")
    
    print("\nFixing overlaps...")
    fixed_units = fix_overlapping_units(units)
    
    print("\nFixed units:")
    for i, unit in enumerate(fixed_units):
        print(f"  Unit {i}: segments {unit['start_index']}-{unit['end_index']}")
    
    # Verify no overlaps
    print("\nVerifying no overlaps remain:")
    has_overlap = False
    for i in range(1, len(fixed_units)):
        if fixed_units[i-1]['end_index'] >= fixed_units[i]['start_index']:
            print(f"  ❌ Still has overlap between units {i-1} and {i}")
            has_overlap = True
    
    if not has_overlap:
        print("  ✅ All overlaps fixed!")

def show_correct_validation():
    """Show what the correct validation should look like."""
    print("\n=== Correct Validation Logic ===")
    print("Current code (WRONG):")
    print("  if prev_unit.end_index > curr_unit.start_index:")
    print("      raise ValueError(...)")
    print("\nShould be (CORRECT):")
    print("  if prev_unit.end_index >= curr_unit.start_index:")
    print("      raise ValueError(...)")
    print("\nThe >= operator catches the edge case where one unit ends")
    print("at the same index where the next begins.")

if __name__ == "__main__":
    # Test current validation
    current_validation_correct = test_current_validation()
    
    # Show how to fix overlaps
    demonstrate_fix_invalid_indices()
    
    # Show correct validation
    show_correct_validation()
    
    print("\n=== Summary ===")
    if not current_validation_correct:
        print("⚠️  The current validation has a bug that allows overlapping units.")
        print("This causes failures later in the pipeline when the overlap is detected.")
        print("The fix is simple: change > to >= in the validation check.")