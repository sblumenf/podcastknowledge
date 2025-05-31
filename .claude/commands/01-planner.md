# Create Implementation Plan: $ARGUMENTS

Generate a detailed implementation plan using "ultrathink" for: $ARGUMENTS

1. **Clarify requirements first**:
   - Ask 3-5 specific questions about the request to ensure understanding
   - Wait for answers before proceeding
   - Focus on: scope boundaries, expected outcomes, constraints, success metrics

2. **Confirm understanding**:
   - Provide a plain language summary: "Based on your answers, this plan will achieve: [clear description]"
   - Get confirmation before creating the detailed plan

3. **Save to**: `docs/plans/[descriptive-name]-plan.md`

4. **Required structure**:
   - Executive Summary (plain language outcome)
   - Phases with todo lists
   - Each task must include:
     - [ ] Task description (micro-process detail)
     - Purpose: What this achieves
     - Steps: Explicit substeps Claude Code can execute
     - Validation: How to verify done
   - Success Criteria (measurable outcomes)
   - Technology Requirements (flag any new tech for approval)

5. **Detail level**: Over-engineer for Claude Code execution - every action must be explicit, no assumptions

6. **Self-review**: After drafting, critically verify:
   - Tasks are unambiguous
   - No hidden steps requiring human intuition  
   - Each task independently executable
   - New technologies clearly marked
   - Plan achieves the confirmed understanding from step 2

7. **New tech rule**: Any new frameworks/databases/models require explicit human confirmation

8. **Documentation review**: Make sure that there is an explicit reference to use the context7 MCP tool for documenation for each task.

Think hard about the entire plan - the architecture, implementation sequence, potential challenges, and how all pieces fit together. Create the plan for: $ARGUMENTS