# Optional Dependencies Analysis

## Task 2.1 Completed: Analysis of Dependency Handling Patterns

### Overview of Three Optional Dependency Modules

#### 1. `/src/utils/optional_dependencies.py` (133 lines)
**Purpose**: Resource monitoring dependencies (psutil)
**Pattern**: Try-except import with mock classes
**Dependencies Handled**:
- `psutil` - System/process monitoring

**Key Features**:
- Mock classes: `MockProcess`, `MockPsutil`
- Helper functions: `get_psutil()`, `get_memory_info()`, `get_cpu_info()`
- Returns dictionaries with fallback values
- `PSUTIL_AVAILABLE` flag

#### 2. `/src/utils/optional_deps.py` (278 lines)
**Purpose**: Scientific computing dependencies
**Pattern**: Try-except imports with fallback algorithms
**Dependencies Handled**:
- `networkx` - Graph analysis
- `numpy` - Numerical arrays
- `scipy` - Scientific computing

**Key Features**:
- Fallback implementations for algorithms:
  - `fallback_degree_centrality()`
  - `fallback_betweenness_centrality()`
  - `fallback_eigenvector_centrality()`
  - `fallback_cosine_similarity()`
- Feature availability checking
- `HAS_NETWORKX`, `HAS_NUMPY`, `HAS_SCIPY` flags
- `require_*()` functions that raise errors
- Feature documentation dictionary

#### 3. `/src/utils/optional_google.py` (81 lines)
**Purpose**: Google AI dependencies
**Pattern**: Try-except import with mock API responses
**Dependencies Handled**:
- `google-generativeai` - Gemini API

**Key Features**:
- Mock classes: `MockGeminiEmbedding`, `MockGeminiModel`, `MockGenAI`
- Returns zero embeddings when unavailable
- `GOOGLE_AI_AVAILABLE` flag
- `get_genai()` helper function

### Common Patterns Identified

1. **Try-Except Import Pattern**:
   ```python
   try:
       import package
       PACKAGE_AVAILABLE = True
   except ImportError:
       PACKAGE_AVAILABLE = False
       package = None
   ```

2. **Mock Classes**: Each module creates mock versions of missing dependencies

3. **Availability Flags**: Boolean flags to check if dependency is available

4. **Helper Functions**: `get_*()` functions that return real or mock module

5. **Fallback Implementations**: Either mock objects or pure Python algorithms

### Duplications and Inconsistencies

1. **Pattern Duplication**: Same try-except pattern repeated 7 times across files

2. **Naming Inconsistencies**:
   - `optional_dependencies.py` vs `optional_deps.py` (abbreviated)
   - Different flag naming: `PSUTIL_AVAILABLE` vs `HAS_NUMPY`

3. **Different Approaches**:
   - File 1: Returns mock objects that mimic API
   - File 2: Provides fallback algorithms  
   - File 3: Returns mock API responses

4. **No Unified Registry**: Each file manages its own dependencies independently

5. **Repeated Mock Patterns**: Similar mock class structures in each file

### Consolidation Strategy

1. **Single Registry Pattern**:
   ```python
   OPTIONAL_DEPENDENCIES = {
       'psutil': {'available': False, 'module': None, 'mock': MockPsutil},
       'networkx': {'available': False, 'module': None, 'fallbacks': {...}},
       'numpy': {'available': False, 'module': None},
       # etc.
   }
   ```

2. **Unified Import Handler**:
   ```python
   class OptionalDependency:
       def __init__(self, name, mock_class=None, fallbacks=None):
           self.name = name
           self.module = None
           self.available = False
           self._try_import()
   ```

3. **Consistent API**:
   - Single `get_dependency(name)` function
   - Consistent availability checking
   - Unified error messages

4. **Benefits**:
   - ~60% code reduction
   - Consistent handling across all dependencies
   - Easy to add new optional dependencies
   - Single place to manage all mocks/fallbacks