# Security Guidelines

## Overview

This document outlines security considerations for the VTT Knowledge Graph Pipeline.

## Input Validation

### VTT File Processing
- All VTT files are validated before processing
- File paths are checked to ensure they exist and are regular files
- VTT format validation (WEBVTT header required)
- File extension validation (.vtt only)

### Path Security
- No path traversal allowed - files must be within specified directories
- Absolute paths are resolved and validated
- Symbolic links are followed but validated

## Configuration Security

### Environment Variables
- Sensitive configuration (API keys, database passwords) stored in `.env` file
- `.env` file should never be committed to version control
- Use environment-specific `.env` files for different deployments

### Recommended `.env` permissions:
```bash
chmod 600 .env  # Read/write for owner only
```

## API Security

### Authentication
- API endpoints should be protected in production
- Use API keys or OAuth2 for authentication
- Rate limiting recommended for public endpoints

### Input Sanitization
- All API inputs are validated using Pydantic models
- File paths are restricted to allowed directories
- No direct SQL queries - all database access through Neo4j driver

## Dependencies

### Known Issues
- Keep dependencies updated regularly
- Run security audits periodically:
  ```bash
  pip-audit  # Install with: pip install pip-audit
  ```

### Dependency Management
- Use exact versions in requirements.txt
- Review dependency changes before updating
- Monitor security advisories for critical dependencies

## File Operations

### Safe Practices
- Always specify encoding when opening files
- Use pathlib.Path for path operations
- Validate file types before processing
- Limit file sizes to prevent DoS attacks

### Example Safe File Reading:
```python
from pathlib import Path

def read_vtt_safely(file_path: str, max_size_mb: int = 100) -> str:
    path = Path(file_path).resolve()
    
    # Check file size
    size_mb = path.stat().st_size / 1024 / 1024
    if size_mb > max_size_mb:
        raise ValueError(f"File too large: {size_mb}MB")
    
    # Read with encoding
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()
```

## Neo4j Security

### Connection Security
- Use encrypted connections (neo4j+s://) in production
- Strong passwords for database users
- Limit database user permissions to minimum required

### Query Security
- Use parameterized queries to prevent injection
- Never construct queries with string concatenation
- Validate all user inputs before querying

## Deployment Security

### Docker Security
- Run containers with non-root users
- Use specific image tags, not 'latest'
- Limit container resources
- Use secrets management for sensitive data

### Network Security
- Use HTTPS for all API endpoints
- Implement proper CORS policies
- Use firewalls to restrict database access
- Monitor for unusual activity

## Data Privacy

### Personal Information
- VTT files may contain personal information
- Implement data retention policies
- Allow users to request data deletion
- Log access to sensitive data

### GDPR Compliance
- Document what data is collected
- Implement right to deletion
- Provide data export functionality
- Maintain audit logs

## Security Checklist

Before deployment, ensure:
- [ ] All dependencies are up to date
- [ ] Environment variables are properly secured
- [ ] API authentication is enabled
- [ ] File uploads are size-limited
- [ ] Database connections are encrypted
- [ ] Logs don't contain sensitive information
- [ ] Error messages don't expose system details
- [ ] Input validation is comprehensive
- [ ] Rate limiting is configured
- [ ] Security headers are set (HSTS, CSP, etc.)

## Reporting Security Issues

If you discover a security vulnerability:
1. Do NOT create a public issue
2. Email security concerns to: security@example.com
3. Include steps to reproduce
4. Allow time for patching before disclosure

## Regular Maintenance

### Monthly Tasks
- Review and update dependencies
- Check for security advisories
- Rotate API keys and passwords
- Review access logs

### Quarterly Tasks
- Full security audit
- Penetration testing (if applicable)
- Review and update security policies
- Training for team members