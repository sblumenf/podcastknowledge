# Claude Workflow Instructions

This directory contains custom workflow commands for Claude Code to execute systematic development processes.

## Workflow Stages

The development workflow consists of 5 sequential stages:

1. **01-planner.md** - Plans the implementation approach
2. **02-implementor.md** - Executes the implementation plan
3. **03-validator.md** - Validates the implementation and identifies issues
4. **04-resolver.md** - Fixes issues found during validation
5. **05-finalizer.md** - Completes documentation and prepares handoff

## Usage

To use these workflows, reference them in your Claude Code conversation:
- "Use the planner workflow to design a solution for X"
- "Run the validator to check the implementation"
- "Use the resolver to fix the validation issues"

Each stage builds upon the previous one, creating a systematic approach to development tasks.