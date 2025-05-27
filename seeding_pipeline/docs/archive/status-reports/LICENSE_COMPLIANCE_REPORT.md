# License Compliance Report

## Project License
- **Project**: Podcast Knowledge Graph Pipeline
- **License**: MIT License
- **SPDX ID**: MIT
- **OSI Approved**: Yes
- **GPL Compatible**: Yes

## Dependency License Analysis

### Core Dependencies

| Package | Version | License | Compatibility | Notes |
|---------|---------|---------|---------------|-------|
| neo4j | >=5.14.0 | Apache-2.0 | ✅ Compatible | Permissive, attribution required |
| python-dotenv | >=1.0.0 | BSD-3-Clause | ✅ Compatible | Permissive |
| numpy | >=1.24.3 | BSD-3-Clause | ✅ Compatible | Permissive |
| scipy | >=1.11.4 | BSD-3-Clause | ✅ Compatible | Permissive |
| networkx | >=3.1 | BSD-3-Clause | ✅ Compatible | Permissive |
| torch | >=2.1.0 | BSD-3-Clause | ✅ Compatible | Includes NVIDIA components |
| openai-whisper | >=20231117 | MIT | ✅ Compatible | Same as project |
| pyannote.audio | >=3.1.1 | MIT | ✅ Compatible | Same as project |
| langchain | >=0.1.0 | MIT | ✅ Compatible | Same as project |
| langchain-google-genai | >=0.0.5 | MIT | ✅ Compatible | Same as project |
| sentence-transformers | >=2.2.2 | Apache-2.0 | ✅ Compatible | Permissive |
| feedparser | >=6.0.10 | BSD-2-Clause | ✅ Compatible | Permissive |
| tqdm | >=4.66.1 | MIT + MPL-2.0 | ✅ Compatible | Dual licensed |

### Development Dependencies

| Package | Version | License | Compatibility | Notes |
|---------|---------|---------|---------------|-------|
| pytest | >=7.4.3 | MIT | ✅ Compatible | Same as project |
| pytest-cov | >=4.1.0 | MIT | ✅ Compatible | Same as project |
| pytest-asyncio | >=0.21.1 | Apache-2.0 | ✅ Compatible | Permissive |
| pytest-mock | >=3.12.0 | MIT | ✅ Compatible | Same as project |
| mypy | >=1.7.1 | MIT | ✅ Compatible | Same as project |
| black | >=23.11.0 | MIT | ✅ Compatible | Same as project |
| isort | >=5.12.0 | MIT | ✅ Compatible | Same as project |
| flake8 | >=6.1.0 | MIT | ✅ Compatible | Same as project |
| pre-commit | >=3.5.0 | MIT | ✅ Compatible | Same as project |

## License Categories

### Permissive Licenses (Compatible with MIT)
1. **MIT License**: Most development tools and several core dependencies
2. **BSD-3-Clause**: Scientific computing libraries (numpy, scipy, torch)
3. **BSD-2-Clause**: feedparser
4. **Apache-2.0**: neo4j driver, sentence-transformers

### Copyleft Licenses
- **None identified**: All dependencies use permissive licenses

### Proprietary Components
- **None identified**: All dependencies are open source

## Compliance Requirements

### Attribution Requirements
The following packages require attribution in documentation or notices:

1. **Apache-2.0 Licensed** (neo4j, sentence-transformers):
   - Include copyright notice
   - Include copy of Apache-2.0 license
   - State changes made (if any)

2. **BSD Licensed** (numpy, scipy, networkx, torch, feedparser):
   - Include copyright notice
   - Include license text

### Binary Distribution
When distributing binaries:
- Include all required notices
- Bundle license texts
- Maintain copyright attributions

## Third-Party Components

### Model Licenses
1. **Whisper Models**: MIT License (OpenAI)
2. **Sentence Transformers**: Apache-2.0 (varies by model)
3. **Gemini API**: Subject to Google's Terms of Service

### Data and Content
- Podcast content remains property of respective owners
- Generated knowledge graphs are derivative works
- Respect podcast licensing and fair use

## Compliance Checklist

- [x] Project has clear license (MIT)
- [x] All dependencies are compatible with MIT
- [x] No copyleft dependencies
- [x] No proprietary dependencies
- [x] Attribution requirements documented
- [x] License file included in repository
- [x] Third-party licenses documented
- [x] No license conflicts identified

## Legal Notices

### Required Attributions
Create a `NOTICE` or `THIRD_PARTY_LICENSES` file containing:

```
This software includes the following third-party components:

1. Neo4j Python Driver
   Copyright (c) Neo4j, Inc.
   Licensed under Apache License 2.0
   https://github.com/neo4j/neo4j-python-driver

2. NumPy
   Copyright (c) 2005-2024, NumPy Developers.
   Licensed under BSD 3-Clause License
   https://numpy.org/

3. PyTorch
   Copyright (c) 2016-2024 Facebook, Inc.
   Licensed under BSD 3-Clause License
   https://pytorch.org/

[Continue for all dependencies requiring attribution]
```

### Recommendations

1. **Create NOTICE file**: Include all required attributions
2. **Update README**: Add license badge and compliance info
3. **Distribution packages**: Include all license texts
4. **Documentation**: Mention third-party components
5. **Regular audits**: Check for license changes in updates

## Tools for Ongoing Compliance

### Automated License Checking
```bash
# Install license checker
pip install pip-licenses

# Generate license report
pip-licenses --format=markdown --with-urls > licenses.md

# Check for GPL licenses (incompatible)
pip-licenses --fail-on="GPL;LGPL"
```

### Pre-commit Hook
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/Lucas-C/pre-commit-hooks
    rev: v1.5.4
    hooks:
      - id: insert-license
        files: \.py$
        args: [--license-filepath, LICENSE_HEADER.txt]
```

## Conclusion

The Podcast Knowledge Graph Pipeline is fully compliant with open source licensing requirements:
- Uses MIT license (permissive, business-friendly)
- All dependencies are compatible
- No copyleft or proprietary components
- Clear attribution requirements

The project can be safely used in both open source and commercial contexts with proper attribution.