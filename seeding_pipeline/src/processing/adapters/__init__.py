"""
Extraction adapters for unified interface.
"""

from .fixed_schema_adapter import FixedSchemaAdapter
from .schemaless_adapter import SchemalessAdapter

__all__ = [
    'FixedSchemaAdapter',
    'SchemalessAdapter'
]