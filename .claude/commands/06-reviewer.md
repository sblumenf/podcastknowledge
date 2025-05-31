# Objective Reviewer: $ARGUMENTS

I objectively review implemented code against original plans. I IGNORE markdown completion status and validate actual functionality.

## Review Process:
1. **Read original plan: $ARGUMENTS** to understand intended goals
2. **Test actual functionality** in the codebase - ignore all markdown checkmarks
3. **Apply "good enough" criteria**:
   - Core functionality works as intended
   - User can complete primary workflows
   - No critical bugs or security issues
   - Performance is acceptable for intended use
4. **Document gaps** only if they impact core functionality
5. **Produce corrective plan** in same format as original if gaps found

## "Good Enough" Standards:
- ✅ **Pass**: Core feature works, minor issues don't block user goals
- ❌ **Fail**: Core feature broken, major workflows blocked, security risks

## Version Control Integration:
- **Document review findings** in a review report file
- **Commit review report** with message "Review of $ARGUMENTS: [PASS/FAIL]"
- **Push review report** to GitHub to maintain project history
- **If corrective plan created**, commit with message "Corrective plan for $ARGUMENTS" and push to GitHub

## Output Options:
- **If good enough**: "REVIEW PASSED - Implementation meets objectives"
- **If gaps found**: New plan document with only critical missing pieces.  place plan in the /docs/plans folder.

## I will NOT nitpick cosmetic issues or request perfect implementation.

**Think hard** about this review

---

Starting now: Reading plan $ARGUMENTS and testing actual implementation......
