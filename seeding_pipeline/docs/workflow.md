# Development Workflow

This document describes the standard workflow for implementing features and improvements using Claude Code's custom commands.

## Complete Workflow

1. **`/project:01-planner`** → Create detailed implementation plan
   - Creates a comprehensive plan with phases and todos
   - Asks clarifying questions before planning
   - Saves plan to `docs/plans/[descriptive-name]-plan.md`
   - Uses ultrathink for thorough analysis

2. **`/project:02-executor`** → Implement each phase
   - Executes the plan phase by phase
   - Marks todos as complete as work progresses
   - Commits changes after each significant step
   - Works autonomously to solve problems

3. **`/project:03-validator`** → Validate phase implementation
   - Verifies actual code changes match the plan
   - Runs tests to confirm functionality
   - Reports readiness for next phase
   - Identifies any missing implementations

4. **`/project:04-finalizer`** → Complete and archive plan
   - Performs comprehensive validation
   - Verifies all success criteria are met
   - Moves completed plans to `docs/plans/completed/`
   - Provides final status summary

## Usage Examples

### Planning a New Feature
```
/project:01-planner "Add real-time monitoring dashboard"
```

### Implementing Phase 2
```
/project:02-executor 2
```

### Validating Phase 3
```
/project:03-validator 3
```

### Finalizing the Plan
```
/project:04-finalizer "monitoring-dashboard-plan"
```

## Best Practices

- Always start with the planner to ensure clear requirements
- Execute phases sequentially - don't skip ahead
- Validate each phase before moving to the next
- Use the finalizer only when all phases are complete
- Keep plans in version control for team collaboration

## Benefits

- **Structured Development**: Clear phases prevent scope creep
- **Progress Tracking**: Built-in todo management
- **Quality Assurance**: Validation at each step
- **Documentation**: Plans serve as implementation records
- **Team Alignment**: Shared workflow ensures consistency