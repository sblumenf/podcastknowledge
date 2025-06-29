# Model Configuration Standardization Plan

## Executive Summary

This plan implements a simple, maintainable configuration system that moves all hardcoded model names (Gemini flash, pro, and embeddings) to environment variables, validates them once at startup, and fails fast with clear errors if models are unavailable - strictly following KISS principles without any over-engineering, auto-discovery, or complex fallback mechanisms.

**Core Principle**: Every task in this plan must adhere to KISS (Keep It Simple, Stupid) principles. No over-engineering. No complex abstractions. No intuition-based decisions.

## Phase 1: Discovery and Documentation

### Task 1.1: Document All Hardcoded Model References
- [ ] **Task**: Search the entire codebase for all hardcoded model name strings including variations of "gemini", model names in configs, and embedded model references. This search must be exhaustive, covering all Python files, configuration files, and documentation. The search should identify not just direct string literals but also default parameters in function signatures and class definitions. NO INTUITION: Use explicit grep/ripgrep commands with specific patterns, do not assume you know where models are defined.
- **Purpose**: Create a complete inventory of all model references to ensure none are missed during the update
- **Steps**: 
  1. Use ripgrep to search for pattern "gemini" in all .py files
  2. Use ripgrep to search for pattern "model" in all .py files  
  3. Use ripgrep to search for "embedding" in all .py files
  4. Check all .env, .yaml, .json configuration files
  5. Document findings in a structured format showing file:line:content
  6. Use context7 MCP tool to check Gemini documentation for current valid model names
- **Reference**: This task establishes the baseline for all Phase 2 updates. Review Executive Summary before starting to ensure focus on SIMPLE documentation, not complex analysis.
- **Validation**: A complete list of all model references with no hardcoded models missed

### Task 1.2: Identify Current Environment Variables
- [ ] **Task**: Document all existing model-related environment variables currently in use, including their current names and values. This includes checking .env files, .env.template files, env_config.py, and any docker or deployment configurations. The search must capture the exact variable names to ensure we don't change them per requirement #5. NO INTUITION: Check every file that could contain environment variables, do not assume standard locations.
- **Purpose**: Ensure we don't change existing variable names and understand current configuration patterns
- **Steps**:
  1. Check .env.template for all environment variables
  2. Check env_config.py for how variables are loaded
  3. Search for os.getenv() and os.environ usage in codebase
  4. Document current MODEL/GEMINI related variables
  5. Note any naming patterns (e.g., GEMINI_API_KEY pattern)
  6. Use context7 MCP tool to check for environment variable best practices
- **Reference**: This inventory supports Phase 2 implementation while adhering to requirement #5 (don't change variable names). Review Executive Summary to ensure SIMPLE documentation approach.
- **Validation**: Complete list of existing environment variables with their current usage patterns

### Task 1.3: Document Model Usage Patterns
- [ ] **Task**: Analyze how each hardcoded model is currently used - which services use which models, what the defaults are, and how models are passed between components. This documentation should capture the simple flow of model names through the system without creating complex dependency graphs. Focus on understanding WHERE models are specified and HOW they flow to the LLM services. NO INTUITION: Document exactly what the code shows, do not infer architectural patterns.
- **Purpose**: Understand the simple paths model names take through the system to ensure our updates don't break existing flows
- **Steps**:
  1. For each hardcoded model found in 1.1, trace its usage
  2. Document which functions/classes use each model
  3. Note how model names are passed (parameters, config objects, etc.)
  4. Identify the final LLM service calls that use these models
  5. Create a simple text diagram showing model flow
  6. Use context7 MCP tool to understand Gemini model selection best practices
- **Reference**: This documentation ensures Phase 2 changes maintain existing behavior. Review Executive Summary - keep documentation SIMPLE, no over-engineered architecture diagrams.
- **Validation**: Clear documentation showing each model's path from configuration to API call

## Phase 2: Environment Variable Implementation

### Task 2.1: Add Model Environment Variables to .env.template
- [ ] **Task**: Add environment variable entries for all models to .env.template with clear comments explaining each variable's purpose. Variables should follow existing naming patterns (likely GEMINI_* based on GEMINI_API_KEY pattern) and include the current working model names as defaults. Each variable must have a descriptive comment that explains what the model is used for (LLM generation, embeddings, etc.). NO INTUITION: Use the exact model names found in discovery phase, do not guess at "better" names.
- **Purpose**: Establish the canonical source for model configuration following existing patterns
- **Steps**:
  1. Open .env.template file
  2. Add GEMINI_FLASH_MODEL with current working model name
  3. Add GEMINI_PRO_MODEL with current working model name  
  4. Add GEMINI_EMBEDDING_MODEL with current working model name
  5. Add clear comments above each explaining usage
  6. Ensure consistent formatting with existing variables
  7. Use context7 MCP tool to verify current Gemini model names
- **Reference**: Based on findings from Task 1.2, maintaining existing patterns. Review Executive Summary - SIMPLE variable names, no complex hierarchies.
- **Validation**: .env.template contains all model variables with clear documentation

### Task 2.2: Update env_config.py to Load Model Variables
- [ ] **Task**: Modify env_config.py to load the new model environment variables using the existing patterns in that file. The implementation should follow the exact same pattern as other environment variables (like GEMINI_API_KEY) for consistency. Each variable should have a fallback to the current working default to ensure the system works even without environment variables set. NO INTUITION: Copy the exact pattern used for existing variables, do not create new patterns.
- **Purpose**: Make model names available to the application through the standard configuration system
- **Steps**:
  1. Open src/core/env_config.py
  2. Add property for GEMINI_FLASH_MODEL following existing patterns
  3. Add property for GEMINI_PRO_MODEL following existing patterns
  4. Add property for GEMINI_EMBEDDING_MODEL following existing patterns
  5. Use os.getenv() with default values matching current working models
  6. Ensure consistent code style with rest of file
  7. Use context7 MCP tool to check Python os.getenv best practices
- **Reference**: Implementation must match patterns found in Task 1.2. Review Executive Summary - SIMPLE getenv calls, no complex validation at this layer.
- **Validation**: env_config.py successfully loads all model variables with appropriate defaults

### Task 2.3: Create Simple Model Configuration Access
- [ ] **Task**: Add a simple method or property to the Config class that provides access to model names from environment variables. This should be a straightforward addition that returns the model names without any complex logic, validation, or transformation. The interface should be as simple as config.gemini_flash_model. NO INTUITION: Make the simplest possible addition, do not add configuration frameworks or abstraction layers.
- **Purpose**: Provide a clean, simple interface for code to access model configuration
- **Steps**:
  1. Open src/core/config.py
  2. Add properties that return env_config model values
  3. Keep property names simple and descriptive
  4. No validation logic in these properties (KISS principle)
  5. Ensure consistent style with existing Config properties
  6. Add brief docstring for each property
  7. Use context7 MCP tool to check Python property best practices
- **Reference**: This provides the interface for Phase 3 replacements. Review Executive Summary - SIMPLE properties only, no over-engineering.
- **Validation**: Config class has simple properties returning model names from environment

## Phase 3: Replace Hardcoded Models

### Task 3.1: Replace Hardcoded Models in main.py
- [ ] **Task**: Replace all hardcoded model names in main.py with references to the configuration properties created in Task 2.3. This includes the flash and pro model names currently hardcoded in the pipeline initialization. Each replacement should be a simple substitution of the string literal with config.property_name. NO INTUITION: Replace only the exact strings found in Task 1.1, do not refactor surrounding code.
- **Purpose**: Remove the primary source of hardcoded model names that override service defaults
- **Steps**:
  1. Open main.py
  2. Locate each hardcoded model string from Task 1.1 findings
  3. Replace with config.gemini_flash_model (or appropriate property)
  4. Do not change any other code structure
  5. Ensure imports are added for Config if needed
  6. Test that replacements are syntactically correct
  7. Use context7 MCP tool to verify no Python syntax errors
- **Reference**: Using the interface created in Task 2.3 to replace findings from Task 1.1. Review Executive Summary - SIMPLE replacements only, no architectural changes.
- **Validation**: No hardcoded model strings remain in main.py

### Task 3.2: Replace Hardcoded Models in Service Defaults
- [ ] **Task**: Replace hardcoded model default values in service classes (LLMService, GeminiDirectService, etc.) with configuration references. Default parameters in __init__ methods should reference config values rather than string literals. This ensures all model names come from configuration even when not explicitly passed. NO INTUITION: Only replace the default parameter values found in Task 1.1, do not redesign service interfaces.
- **Purpose**: Ensure service layer defaults also come from configuration rather than hardcoded strings
- **Steps**:
  1. For each service file with hardcoded model defaults from Task 1.1
  2. Import Config at module level
  3. Create module-level config instance
  4. Replace default parameter values with config properties
  5. Maintain exact same parameter signatures
  6. Do not add new parameters or change interfaces
  7. Use context7 MCP tool to check Python default parameter best practices
- **Reference**: Applying configuration to all locations found in Task 1.3. Review Executive Summary - SIMPLE default replacements, no service redesign.
- **Validation**: All service defaults reference configuration instead of hardcoded strings

### Task 3.3: Replace Hardcoded Models in Extraction Components  
- [ ] **Task**: Replace hardcoded model names in extraction components (cached_extraction.py, etc.) with configuration references. This includes any model names used for entity extraction, insight extraction, or other specialized extraction tasks. Each replacement should maintain the existing code structure while only changing the source of the model name. NO INTUITION: Replace only literal strings, do not refactor extraction logic.
- **Purpose**: Ensure extraction components use configured models rather than hardcoded values
- **Steps**:
  1. Open each extraction file with hardcoded models from Task 1.1
  2. Import Config and create instance as needed
  3. Replace string literals with config property references  
  4. Maintain all existing logic and flow
  5. Do not change extraction algorithms or patterns
  6. Ensure no hardcoded fallbacks remain
  7. Use context7 MCP tool to verify changes maintain functionality
- **Reference**: Completing replacements for all findings from Task 1.1. Review Executive Summary - SIMPLE string replacements in existing code structure.
- **Validation**: No hardcoded model strings in extraction components

### Task 3.4: Update Factory Pattern Model Handling
- [ ] **Task**: Update LLMServiceFactory to use configuration for any model name transformations or defaults. The factory currently adds version suffixes (e.g., converting "gemini-1.5-flash" to "gemini-1.5-flash-001") which should be removed in favor of using exact configured names. This change ensures the configuration specifies exact model names without hidden transformations. NO INTUITION: Remove transformations to use exact configured values, do not add new logic.
- **Purpose**: Ensure factory uses exact model names from configuration without hidden modifications
- **Steps**:
  1. Open src/services/llm_factory.py
  2. Find any code that transforms model names
  3. Remove version suffix additions
  4. Use model names exactly as provided from configuration
  5. Update any factory defaults to use config values
  6. Keep factory interface unchanged
  7. Use context7 MCP tool to check factory pattern best practices
- **Reference**: Ensuring Task 1.3 model flows use exact configured names. Review Executive Summary - SIMPLE pass-through of configured names, no smart transformations.
- **Validation**: Factory passes model names through without modification

## Phase 4: Startup Validation

### Task 4.1: Create Simple Model Validation Function
- [ ] **Task**: Create a simple validation function that checks if configured models are valid by making a minimal API call at startup. The function should attempt to use each configured model and fail fast with a clear error message if any model is invalid. This should be a standalone function that can be called early in the startup sequence. NO INTUITION: Make the simplest possible validation call, do not create complex validation frameworks.
- **Purpose**: Detect invalid model names at startup rather than during processing
- **Steps**:
  1. Create validate_models() function in main.py or a utils file
  2. Get each model name from config
  3. Make a minimal LLM call with each model (e.g., "test")
  4. Catch specific exceptions for invalid models
  5. Print clear error with model name and exit if invalid
  6. Keep validation simple - just test model exists
  7. Use context7 MCP tool to check Gemini API error handling
- **Reference**: Implements startup validation per requirement #4. Review Executive Summary - SIMPLE validation only, not a complex health check system.
- **Validation**: Function successfully detects invalid model names

### Task 4.2: Add Validation to Startup Sequence
- [ ] **Task**: Add the model validation function to the application startup sequence, ensuring it runs before any processing begins. The validation should be one of the first operations after loading configuration. If validation fails, the application should exit with a clear error message indicating which model is invalid. NO INTUITION: Add the call in the most straightforward location, do not restructure startup flow.
- **Purpose**: Ensure invalid models are caught before any processing attempts
- **Steps**:
  1. Open main.py
  2. Find the startup sequence (likely in main() or similar)
  3. Add validate_models() call after config is loaded
  4. Ensure it runs before any pipeline initialization
  5. Let validation function handle errors and exit
  6. Add simple log message "Validating configured models..."
  7. Use context7 MCP tool to check Python startup best practices
- **Reference**: Integrating Task 4.1 validation into startup. Review Executive Summary - SIMPLE addition to existing startup, no architectural changes.
- **Validation**: Application exits cleanly with clear error for invalid models

### Task 4.3: Update Error Messages for Clarity
- [ ] **Task**: Ensure all model-related error messages clearly indicate the invalid model name and suggest checking environment variables. Error messages should be actionable, telling users exactly which environment variable to check and what the current value is. Messages should be simple and direct without technical jargon. NO INTUITION: Update only model validation errors, do not create a general error handling system.
- **Purpose**: Make model configuration errors immediately actionable for operators
- **Steps**:
  1. In validation function, craft clear error messages
  2. Include the invalid model name
  3. Include the environment variable name  
  4. Show current value that failed
  5. Suggest checking .env file
  6. Keep messages concise and actionable
  7. Use context7 MCP tool for error message best practices
- **Reference**: Enhancing Task 4.1 validation with clear errors. Review Executive Summary - SIMPLE, actionable error messages only.
- **Validation**: Error messages clearly identify problem and solution

## Phase 5: Testing and Documentation

### Task 5.1: Test All Model Configurations
- [ ] **Task**: Manually test the system with valid and invalid model names to ensure configuration works correctly and validation catches errors. Testing should cover each model type (flash, pro, embeddings) with both valid current names and invalid names. Document the results to confirm the system behaves as expected. NO INTUITION: Test exact scenarios listed, do not create complex test suites.
- **Purpose**: Verify the configuration system works as intended with simple manual tests
- **Steps**:
  1. Set valid model names in .env and run application
  2. Verify successful startup and processing
  3. Set invalid flash model name and verify clear error
  4. Set invalid pro model name and verify clear error  
  5. Set invalid embedding model and verify clear error
  6. Test with missing environment variables (use defaults)
  7. Document each test result
  8. Use context7 MCP tool to check testing best practices
- **Reference**: Validating all changes from Phases 2-4 work correctly. Review Executive Summary - SIMPLE manual tests, no test frameworks.
- **Validation**: All tests pass with expected behavior documented

### Task 5.2: Update Configuration Documentation
- [ ] **Task**: Update README or configuration documentation to explain the new model environment variables. Documentation should be brief and clear, explaining what each variable controls and providing example valid values. Include a note about where to find current Gemini model names. NO INTUITION: Document only the new variables, do not rewrite entire configuration guides.
- **Purpose**: Ensure users understand how to configure models correctly
- **Steps**:
  1. Find existing configuration documentation
  2. Add section on model configuration
  3. List each environment variable with purpose
  4. Provide example valid values
  5. Add link to Gemini model documentation
  6. Keep documentation concise and practical
  7. Use context7 MCP tool to verify Gemini documentation links
- **Reference**: Documenting the configuration system from Phases 2-4. Review Executive Summary - SIMPLE, practical documentation only.
- **Validation**: Documentation clearly explains model configuration

### Task 5.3: Add Configuration Example to .env.example
- [ ] **Task**: Ensure .env.example (or .env.template) contains working examples of all model environment variables with valid current model names. Comments should explain what each model is used for. This provides a working starting point for new deployments. NO INTUITION: Use current valid model names, do not guess at future models.
- **Purpose**: Provide a working configuration template for deployments
- **Steps**:
  1. Open .env.example or .env.template
  2. Ensure all model variables have valid examples
  3. Use currently working model names
  4. Add brief comment for each variable's purpose
  5. Ensure consistency with Task 5.2 documentation
  6. Format consistently with rest of file
  7. Use context7 MCP tool to verify current model names
- **Reference**: Providing template for configuration from Phase 2. Review Executive Summary - SIMPLE working examples, not complex configurations.
- **Validation**: .env.example provides working configuration template

## Success Criteria

1. **No hardcoded model names** remain in the codebase - all models come from environment variables
2. **Startup validation** detects invalid models with clear, actionable error messages
3. **Existing functionality** unchanged - only the source of model names has changed
4. **KISS principle** maintained - no complex configuration frameworks or abstractions added
5. **Clear documentation** explains the three model environment variables and their purpose

## Technology Requirements

**No new technologies** are required for this plan. The implementation uses only:
- Existing Python os.getenv() functionality
- Existing configuration patterns in the codebase
- Existing Gemini API calls for validation
- No new frameworks, libraries, or architectural patterns

## Critical Reminders

- **NO INTUITION**: Every task has explicit steps. Do not make assumptions.
- **NO OVER-ENGINEERING**: Keep every solution as simple as possible.
- **REVIEW PLAN**: Before implementing each task, review this plan's Executive Summary.
- **KISS PRINCIPLE**: If a solution seems complex, stop and find a simpler approach.
- **STAY ON COURSE**: Each task must align with the simple goal of moving hardcoded models to environment variables.