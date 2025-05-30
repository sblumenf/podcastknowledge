"""Comprehensive tests for validation utilities."""

import pytest
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import re

from src.utils.validation import (
    ValidationError,
    ValidationResult,
    Validator,
    StringValidator,
    NumberValidator,
    DateValidator,
    CollectionValidator,
    DictValidator,
    CompositeValidator,
    validate_email,
    validate_url,
    validate_phone,
    validate_json,
    validate_regex,
    validate_range,
    validate_length,
    validate_type,
    validate_required,
    validate_schema,
    validate_custom,
    ValidationContext,
    ValidationRule,
    ValidationChain,
    create_validator,
    register_validator,
    get_validator,
)


class TestValidationResult:
    """Test ValidationResult class."""
    
    def test_create_success_result(self):
        """Test creating a successful validation result."""
        result = ValidationResult(valid=True)
        assert result.valid is True
        assert result.errors == []
        assert result.warnings == []
        assert str(result) == "ValidationResult(valid=True)"
    
    def test_create_failure_result(self):
        """Test creating a failed validation result."""
        errors = ["Invalid email format", "Required field missing"]
        result = ValidationResult(valid=False, errors=errors)
        assert result.valid is False
        assert result.errors == errors
        assert result.warnings == []
        assert "Invalid email format" in str(result)
    
    def test_result_with_warnings(self):
        """Test result with warnings."""
        warnings = ["Deprecated field used", "Weak password"]
        result = ValidationResult(valid=True, warnings=warnings)
        assert result.valid is True
        assert result.errors == []
        assert result.warnings == warnings
    
    def test_merge_results(self):
        """Test merging validation results."""
        result1 = ValidationResult(valid=True, warnings=["Warning 1"])
        result2 = ValidationResult(valid=False, errors=["Error 1"])
        result3 = ValidationResult(valid=True, warnings=["Warning 2"])
        
        merged = ValidationResult.merge([result1, result2, result3])
        assert merged.valid is False
        assert merged.errors == ["Error 1"]
        assert merged.warnings == ["Warning 1", "Warning 2"]
    
    def test_add_error(self):
        """Test adding errors to result."""
        result = ValidationResult(valid=True)
        result.add_error("New error")
        assert result.valid is False
        assert "New error" in result.errors
    
    def test_add_warning(self):
        """Test adding warnings to result."""
        result = ValidationResult(valid=True)
        result.add_warning("New warning")
        assert result.valid is True
        assert "New warning" in result.warnings


class TestStringValidator:
    """Test StringValidator class."""
    
    def test_validate_min_length(self):
        """Test minimum length validation."""
        validator = StringValidator(min_length=5)
        
        assert validator.validate("hello").valid is True
        assert validator.validate("hello world").valid is True
        assert validator.validate("hi").valid is False
        assert validator.validate("").valid is False
    
    def test_validate_max_length(self):
        """Test maximum length validation."""
        validator = StringValidator(max_length=10)
        
        assert validator.validate("hello").valid is True
        assert validator.validate("hello world").valid is False
        assert validator.validate("").valid is True
    
    def test_validate_pattern(self):
        """Test pattern validation."""
        validator = StringValidator(pattern=r"^[A-Z][a-z]+$")
        
        assert validator.validate("Hello").valid is True
        assert validator.validate("hello").valid is False
        assert validator.validate("HELLO").valid is False
        assert validator.validate("Hello123").valid is False
    
    def test_validate_allowed_values(self):
        """Test allowed values validation."""
        validator = StringValidator(allowed_values=["red", "green", "blue"])
        
        assert validator.validate("red").valid is True
        assert validator.validate("green").valid is True
        assert validator.validate("yellow").valid is False
        assert validator.validate("RED").valid is False
    
    def test_validate_forbidden_values(self):
        """Test forbidden values validation."""
        validator = StringValidator(forbidden_values=["admin", "root", "test"])
        
        assert validator.validate("user").valid is True
        assert validator.validate("admin").valid is False
        assert validator.validate("root").valid is False
        assert validator.validate("Admin").valid is True  # Case sensitive
    
    def test_validate_strip_whitespace(self):
        """Test whitespace stripping."""
        validator = StringValidator(strip_whitespace=True, min_length=5)
        
        assert validator.validate("  hello  ").valid is True
        assert validator.validate("  hi  ").valid is False
    
    def test_validate_case_sensitive(self):
        """Test case sensitivity."""
        validator = StringValidator(
            allowed_values=["Hello"],
            case_sensitive=False
        )
        
        assert validator.validate("hello").valid is True
        assert validator.validate("HELLO").valid is True
        assert validator.validate("HeLLo").valid is True
    
    def test_validate_custom_validators(self):
        """Test custom string validators."""
        def no_numbers(value: str) -> ValidationResult:
            if any(char.isdigit() for char in value):
                return ValidationResult(False, ["String cannot contain numbers"])
            return ValidationResult(True)
        
        validator = StringValidator(custom_validators=[no_numbers])
        
        assert validator.validate("hello").valid is True
        assert validator.validate("hello123").valid is False


class TestNumberValidator:
    """Test NumberValidator class."""
    
    def test_validate_min_value(self):
        """Test minimum value validation."""
        validator = NumberValidator(min_value=0)
        
        assert validator.validate(5).valid is True
        assert validator.validate(0).valid is True
        assert validator.validate(-1).valid is False
        assert validator.validate(100.5).valid is True
    
    def test_validate_max_value(self):
        """Test maximum value validation."""
        validator = NumberValidator(max_value=100)
        
        assert validator.validate(50).valid is True
        assert validator.validate(100).valid is True
        assert validator.validate(101).valid is False
        assert validator.validate(-50).valid is True
    
    def test_validate_allowed_values(self):
        """Test allowed values validation."""
        validator = NumberValidator(allowed_values=[1, 2, 3, 5, 8])
        
        assert validator.validate(3).valid is True
        assert validator.validate(8).valid is True
        assert validator.validate(4).valid is False
        assert validator.validate(10).valid is False
    
    def test_validate_multiple_of(self):
        """Test multiple of validation."""
        validator = NumberValidator(multiple_of=5)
        
        assert validator.validate(10).valid is True
        assert validator.validate(15).valid is True
        assert validator.validate(7).valid is False
        assert validator.validate(0).valid is True
    
    def test_validate_integer_only(self):
        """Test integer only validation."""
        validator = NumberValidator(integer_only=True)
        
        assert validator.validate(5).valid is True
        assert validator.validate(5.0).valid is True
        assert validator.validate(5.5).valid is False
        assert validator.validate(-10).valid is True
    
    def test_validate_positive_only(self):
        """Test positive only validation."""
        validator = NumberValidator(positive_only=True)
        
        assert validator.validate(5).valid is True
        assert validator.validate(0).valid is False
        assert validator.validate(-5).valid is False
        assert validator.validate(0.1).valid is True
    
    def test_validate_custom_validators(self):
        """Test custom number validators."""
        def is_prime(value: int) -> ValidationResult:
            if value < 2:
                return ValidationResult(False, ["Not a prime number"])
            for i in range(2, int(value ** 0.5) + 1):
                if value % i == 0:
                    return ValidationResult(False, ["Not a prime number"])
            return ValidationResult(True)
        
        validator = NumberValidator(
            integer_only=True,
            custom_validators=[is_prime]
        )
        
        assert validator.validate(7).valid is True
        assert validator.validate(11).valid is True
        assert validator.validate(4).valid is False
        assert validator.validate(1).valid is False


class TestDateValidator:
    """Test DateValidator class."""
    
    def test_validate_min_date(self):
        """Test minimum date validation."""
        min_date = datetime(2020, 1, 1)
        validator = DateValidator(min_date=min_date)
        
        assert validator.validate(datetime(2021, 1, 1)).valid is True
        assert validator.validate(datetime(2020, 1, 1)).valid is True
        assert validator.validate(datetime(2019, 12, 31)).valid is False
    
    def test_validate_max_date(self):
        """Test maximum date validation."""
        max_date = datetime(2025, 12, 31)
        validator = DateValidator(max_date=max_date)
        
        assert validator.validate(datetime(2024, 1, 1)).valid is True
        assert validator.validate(datetime(2025, 12, 31)).valid is True
        assert validator.validate(datetime(2026, 1, 1)).valid is False
    
    def test_validate_allowed_weekdays(self):
        """Test allowed weekdays validation."""
        validator = DateValidator(allowed_weekdays=[0, 1, 2, 3, 4])  # Mon-Fri
        
        monday = datetime(2024, 1, 1)  # Monday
        saturday = datetime(2024, 1, 6)  # Saturday
        
        assert validator.validate(monday).valid is True
        assert validator.validate(saturday).valid is False
    
    def test_validate_forbidden_dates(self):
        """Test forbidden dates validation."""
        forbidden = [
            datetime(2024, 12, 25),  # Christmas
            datetime(2024, 1, 1),    # New Year
        ]
        validator = DateValidator(forbidden_dates=forbidden)
        
        assert validator.validate(datetime(2024, 12, 24)).valid is True
        assert validator.validate(datetime(2024, 12, 25)).valid is False
        assert validator.validate(datetime(2024, 1, 1)).valid is False
    
    def test_validate_date_format(self):
        """Test date format validation."""
        validator = DateValidator(date_format="%Y-%m-%d")
        
        assert validator.validate("2024-01-01").valid is True
        assert validator.validate("01/01/2024").valid is False
        assert validator.validate("2024-13-01").valid is False
    
    def test_validate_future_only(self):
        """Test future only validation."""
        validator = DateValidator(future_only=True)
        
        future_date = datetime.now() + timedelta(days=1)
        past_date = datetime.now() - timedelta(days=1)
        
        assert validator.validate(future_date).valid is True
        assert validator.validate(past_date).valid is False
    
    def test_validate_past_only(self):
        """Test past only validation."""
        validator = DateValidator(past_only=True)
        
        future_date = datetime.now() + timedelta(days=1)
        past_date = datetime.now() - timedelta(days=1)
        
        assert validator.validate(past_date).valid is True
        assert validator.validate(future_date).valid is False


class TestCollectionValidator:
    """Test CollectionValidator class."""
    
    def test_validate_min_length(self):
        """Test minimum length validation."""
        validator = CollectionValidator(min_length=2)
        
        assert validator.validate([1, 2, 3]).valid is True
        assert validator.validate([1]).valid is False
        assert validator.validate([]).valid is False
        assert validator.validate(["a", "b"]).valid is True
    
    def test_validate_max_length(self):
        """Test maximum length validation."""
        validator = CollectionValidator(max_length=3)
        
        assert validator.validate([1, 2]).valid is True
        assert validator.validate([1, 2, 3]).valid is True
        assert validator.validate([1, 2, 3, 4]).valid is False
        assert validator.validate([]).valid is True
    
    def test_validate_unique_items(self):
        """Test unique items validation."""
        validator = CollectionValidator(unique_items=True)
        
        assert validator.validate([1, 2, 3]).valid is True
        assert validator.validate([1, 2, 2]).valid is False
        assert validator.validate(["a", "b", "a"]).valid is False
        assert validator.validate([]).valid is True
    
    def test_validate_item_validator(self):
        """Test item validator."""
        item_validator = NumberValidator(min_value=0, max_value=10)
        validator = CollectionValidator(item_validator=item_validator)
        
        assert validator.validate([1, 5, 8]).valid is True
        assert validator.validate([1, 5, 15]).valid is False
        assert validator.validate([-1, 5, 8]).valid is False
    
    def test_validate_allowed_types(self):
        """Test allowed types validation."""
        validator = CollectionValidator(allowed_types=[int, str])
        
        assert validator.validate([1, "hello", 3]).valid is True
        assert validator.validate([1, 2.5, "hi"]).valid is False
        assert validator.validate([True, False]).valid is False
    
    def test_validate_contains_required(self):
        """Test contains required items validation."""
        validator = CollectionValidator(contains_required=["admin", "user"])
        
        assert validator.validate(["admin", "user", "guest"]).valid is True
        assert validator.validate(["user", "guest", "admin"]).valid is True
        assert validator.validate(["user", "guest"]).valid is False
    
    def test_validate_custom_validators(self):
        """Test custom collection validators."""
        def sum_less_than_100(items: List[Any]) -> ValidationResult:
            if not all(isinstance(item, (int, float)) for item in items):
                return ValidationResult(True)  # Skip non-numeric
            total = sum(items)
            if total >= 100:
                return ValidationResult(False, [f"Sum {total} exceeds 100"])
            return ValidationResult(True)
        
        validator = CollectionValidator(custom_validators=[sum_less_than_100])
        
        assert validator.validate([10, 20, 30]).valid is True
        assert validator.validate([40, 50, 20]).valid is False


class TestDictValidator:
    """Test DictValidator class."""
    
    def test_validate_required_keys(self):
        """Test required keys validation."""
        validator = DictValidator(required_keys=["name", "age"])
        
        assert validator.validate({"name": "John", "age": 30}).valid is True
        assert validator.validate({"name": "John"}).valid is False
        assert validator.validate({"age": 30}).valid is False
        assert validator.validate({}).valid is False
    
    def test_validate_optional_keys(self):
        """Test optional keys validation."""
        validator = DictValidator(
            required_keys=["name"],
            optional_keys=["age", "email"]
        )
        
        assert validator.validate({"name": "John"}).valid is True
        assert validator.validate({"name": "John", "age": 30}).valid is True
        assert validator.validate({"name": "John", "phone": "123"}).valid is False
    
    def test_validate_forbidden_keys(self):
        """Test forbidden keys validation."""
        validator = DictValidator(forbidden_keys=["password", "secret"])
        
        assert validator.validate({"name": "John"}).valid is True
        assert validator.validate({"name": "John", "password": "123"}).valid is False
        assert validator.validate({"secret": "data"}).valid is False
    
    def test_validate_key_validators(self):
        """Test key validators."""
        key_validators = {
            "age": NumberValidator(min_value=0, max_value=150),
            "email": StringValidator(pattern=r".*@.*\..*"),
            "name": StringValidator(min_length=2),
        }
        validator = DictValidator(key_validators=key_validators)
        
        valid_data = {"name": "John", "age": 30, "email": "john@example.com"}
        assert validator.validate(valid_data).valid is True
        
        invalid_age = {"name": "John", "age": 200}
        assert validator.validate(invalid_age).valid is False
        
        invalid_email = {"name": "John", "email": "invalid"}
        assert validator.validate(invalid_email).valid is False
    
    def test_validate_strict_mode(self):
        """Test strict mode validation."""
        validator = DictValidator(
            required_keys=["name"],
            optional_keys=["age"],
            strict=True
        )
        
        assert validator.validate({"name": "John"}).valid is True
        assert validator.validate({"name": "John", "age": 30}).valid is True
        assert validator.validate({"name": "John", "extra": "field"}).valid is False
    
    def test_validate_nested_validators(self):
        """Test nested dict validators."""
        address_validator = DictValidator(
            required_keys=["street", "city"],
            key_validators={
                "street": StringValidator(min_length=5),
                "city": StringValidator(min_length=2),
            }
        )
        
        validator = DictValidator(
            required_keys=["name", "address"],
            key_validators={
                "name": StringValidator(min_length=2),
                "address": address_validator,
            }
        )
        
        valid_data = {
            "name": "John",
            "address": {
                "street": "123 Main St",
                "city": "New York"
            }
        }
        assert validator.validate(valid_data).valid is True
        
        invalid_address = {
            "name": "John",
            "address": {
                "street": "123",  # Too short
                "city": "NY"
            }
        }
        assert validator.validate(invalid_address).valid is False


class TestCompositeValidator:
    """Test CompositeValidator class."""
    
    def test_validate_all_mode(self):
        """Test ALL mode validation."""
        validators = [
            StringValidator(min_length=5),
            StringValidator(pattern=r"^[a-z]+$"),
        ]
        validator = CompositeValidator(validators=validators, mode="ALL")
        
        assert validator.validate("hello").valid is True
        assert validator.validate("hi").valid is False
        assert validator.validate("HELLO").valid is False
        assert validator.validate("hello123").valid is False
    
    def test_validate_any_mode(self):
        """Test ANY mode validation."""
        validators = [
            StringValidator(min_length=10),
            StringValidator(pattern=r"^[A-Z].*"),
        ]
        validator = CompositeValidator(validators=validators, mode="ANY")
        
        assert validator.validate("Hello").valid is True  # Starts with uppercase
        assert validator.validate("hello world").valid is True  # Length > 10
        assert validator.validate("hi").valid is False
    
    def test_validate_one_mode(self):
        """Test ONE mode validation."""
        validators = [
            NumberValidator(min_value=0),
            NumberValidator(max_value=10),
        ]
        validator = CompositeValidator(validators=validators, mode="ONE")
        
        assert validator.validate(-5).valid is True  # Only max_value passes
        assert validator.validate(15).valid is True  # Only min_value passes
        assert validator.validate(5).valid is False  # Both pass
        assert validator.validate(-15).valid is False  # Neither passes
    
    def test_validate_custom_aggregation(self):
        """Test custom aggregation function."""
        def majority_vote(results: List[ValidationResult]) -> ValidationResult:
            valid_count = sum(1 for r in results if r.valid)
            is_valid = valid_count > len(results) / 2
            
            if is_valid:
                return ValidationResult(True)
            else:
                all_errors = []
                for r in results:
                    all_errors.extend(r.errors)
                return ValidationResult(False, all_errors)
        
        validators = [
            StringValidator(min_length=5),
            StringValidator(pattern=r"[a-z]+"),
            StringValidator(max_length=10),
        ]
        validator = CompositeValidator(
            validators=validators,
            custom_aggregator=majority_vote
        )
        
        assert validator.validate("hello").valid is True  # 3/3 pass
        assert validator.validate("HELLO").valid is True  # 2/3 pass
        assert validator.validate("hi").valid is False  # 1/3 pass


class TestUtilityFunctions:
    """Test utility validation functions."""
    
    def test_validate_email(self):
        """Test email validation."""
        assert validate_email("user@example.com").valid is True
        assert validate_email("user.name@example.co.uk").valid is True
        assert validate_email("user+tag@example.com").valid is True
        assert validate_email("invalid.email").valid is False
        assert validate_email("@example.com").valid is False
        assert validate_email("user@").valid is False
        assert validate_email("").valid is False
    
    def test_validate_url(self):
        """Test URL validation."""
        assert validate_url("https://example.com").valid is True
        assert validate_url("http://example.com/path").valid is True
        assert validate_url("https://example.com:8080").valid is True
        assert validate_url("ftp://files.example.com").valid is True
        assert validate_url("example.com").valid is False
        assert validate_url("://example.com").valid is False
        assert validate_url("").valid is False
    
    def test_validate_phone(self):
        """Test phone number validation."""
        assert validate_phone("+1-555-123-4567").valid is True
        assert validate_phone("555-123-4567").valid is True
        assert validate_phone("(555) 123-4567").valid is True
        assert validate_phone("5551234567").valid is True
        assert validate_phone("+44 20 7123 4567").valid is True
        assert validate_phone("123").valid is False
        assert validate_phone("abc-def-ghij").valid is False
    
    def test_validate_json(self):
        """Test JSON validation."""
        assert validate_json('{"key": "value"}').valid is True
        assert validate_json('["item1", "item2"]').valid is True
        assert validate_json('"string"').valid is True
        assert validate_json('123').valid is True
        assert validate_json('null').valid is True
        assert validate_json('{invalid}').valid is False
        assert validate_json('').valid is False
    
    def test_validate_regex(self):
        """Test regex pattern validation."""
        pattern = r"^\d{3}-\d{2}-\d{4}$"  # SSN pattern
        
        result = validate_regex("123-45-6789", pattern)
        assert result.valid is True
        
        result = validate_regex("123456789", pattern)
        assert result.valid is False
        
        result = validate_regex("abc-de-fghi", pattern)
        assert result.valid is False
    
    def test_validate_range(self):
        """Test range validation."""
        assert validate_range(5, 0, 10).valid is True
        assert validate_range(0, 0, 10).valid is True
        assert validate_range(10, 0, 10).valid is True
        assert validate_range(-1, 0, 10).valid is False
        assert validate_range(11, 0, 10).valid is False
        
        # Float ranges
        assert validate_range(5.5, 0.0, 10.0).valid is True
        assert validate_range(10.1, 0.0, 10.0).valid is False
    
    def test_validate_length(self):
        """Test length validation."""
        assert validate_length("hello", 1, 10).valid is True
        assert validate_length("", 0, 10).valid is True
        assert validate_length("hello world", 1, 10).valid is False
        
        # Lists
        assert validate_length([1, 2, 3], 1, 5).valid is True
        assert validate_length([], 1, 5).valid is False
        
        # Dicts
        assert validate_length({"a": 1, "b": 2}, 1, 3).valid is True
        assert validate_length({}, 1, 3).valid is False
    
    def test_validate_type(self):
        """Test type validation."""
        assert validate_type(5, int).valid is True
        assert validate_type("hello", str).valid is True
        assert validate_type([1, 2], list).valid is True
        assert validate_type({"key": "value"}, dict).valid is True
        
        assert validate_type(5, str).valid is False
        assert validate_type("hello", int).valid is False
        
        # Multiple types
        assert validate_type(5, (int, float)).valid is True
        assert validate_type(5.5, (int, float)).valid is True
        assert validate_type("5", (int, float)).valid is False
    
    def test_validate_required(self):
        """Test required field validation."""
        assert validate_required("value").valid is True
        assert validate_required(0).valid is True
        assert validate_required(False).valid is True
        assert validate_required([]).valid is True
        
        assert validate_required(None).valid is False
        assert validate_required("").valid is False
        assert validate_required("   ").valid is False


class TestValidationContext:
    """Test ValidationContext class."""
    
    def test_create_context(self):
        """Test creating validation context."""
        context = ValidationContext(
            field_name="email",
            parent_path="user.contact",
            locale="en_US",
            custom_data={"source": "registration"}
        )
        
        assert context.field_name == "email"
        assert context.parent_path == "user.contact"
        assert context.full_path == "user.contact.email"
        assert context.locale == "en_US"
        assert context.custom_data["source"] == "registration"
    
    def test_context_with_index(self):
        """Test context with array index."""
        context = ValidationContext(
            field_name="name",
            parent_path="users[0]",
            index=0
        )
        
        assert context.full_path == "users[0].name"
        assert context.index == 0
    
    def test_nested_context(self):
        """Test creating nested context."""
        parent = ValidationContext(field_name="user")
        child = parent.nested("email")
        
        assert child.parent_path == "user"
        assert child.field_name == "email"
        assert child.full_path == "user.email"
    
    def test_context_in_validator(self):
        """Test using context in validator."""
        def validate_with_context(value: Any, context: ValidationContext) -> ValidationResult:
            if context.field_name == "admin_email" and not value.endswith("@admin.com"):
                return ValidationResult(False, ["Admin email must end with @admin.com"])
            return ValidationResult(True)
        
        validator = StringValidator(
            custom_validators=[validate_with_context]
        )
        
        context = ValidationContext(field_name="admin_email")
        assert validator.validate("user@admin.com", context).valid is True
        assert validator.validate("user@example.com", context).valid is False
        
        context = ValidationContext(field_name="user_email")
        assert validator.validate("user@example.com", context).valid is True


class TestValidationChain:
    """Test ValidationChain class."""
    
    def test_simple_chain(self):
        """Test simple validation chain."""
        chain = ValidationChain()
        chain.add(StringValidator(min_length=5))
        chain.add(StringValidator(pattern=r"^[a-z]+$"))
        
        assert chain.validate("hello").valid is True
        assert chain.validate("hi").valid is False
        assert chain.validate("HELLO").valid is False
    
    def test_chain_with_transformations(self):
        """Test chain with value transformations."""
        def lowercase_transform(value: str) -> str:
            return value.lower()
        
        def trim_transform(value: str) -> str:
            return value.strip()
        
        chain = ValidationChain()
        chain.add_transform(trim_transform)
        chain.add_transform(lowercase_transform)
        chain.add(StringValidator(pattern=r"^[a-z]+$"))
        
        assert chain.validate("  HELLO  ").valid is True
        assert chain.validate("  Hello123  ").valid is False
    
    def test_chain_short_circuit(self):
        """Test chain short-circuit on failure."""
        call_count = 0
        
        def counting_validator(value: Any) -> ValidationResult:
            nonlocal call_count
            call_count += 1
            return ValidationResult(True)
        
        chain = ValidationChain(short_circuit=True)
        chain.add(StringValidator(min_length=5))
        chain.add(Validator(custom_validators=[counting_validator]))
        
        chain.validate("hi")  # Should fail on first validator
        assert call_count == 0  # Second validator not called
        
        chain.validate("hello")  # Should pass first validator
        assert call_count == 1  # Second validator called
    
    def test_chain_with_conditions(self):
        """Test conditional validation in chain."""
        def only_if_admin(value: Dict[str, Any]) -> bool:
            return value.get("role") == "admin"
        
        chain = ValidationChain()
        chain.add(DictValidator(required_keys=["name", "role"]))
        chain.add(
            DictValidator(required_keys=["admin_code"]),
            condition=only_if_admin
        )
        
        # Non-admin doesn't need admin_code
        assert chain.validate({"name": "John", "role": "user"}).valid is True
        
        # Admin needs admin_code
        assert chain.validate({"name": "Jane", "role": "admin"}).valid is False
        assert chain.validate({
            "name": "Jane",
            "role": "admin",
            "admin_code": "123"
        }).valid is True


class TestValidatorRegistry:
    """Test validator registry functionality."""
    
    def test_register_validator(self):
        """Test registering custom validators."""
        @register_validator("ssn")
        class SSNValidator(Validator):
            def validate(self, value: Any, context: Optional[ValidationContext] = None) -> ValidationResult:
                if not isinstance(value, str):
                    return ValidationResult(False, ["SSN must be a string"])
                if not re.match(r"^\d{3}-\d{2}-\d{4}$", value):
                    return ValidationResult(False, ["Invalid SSN format"])
                return ValidationResult(True)
        
        validator = get_validator("ssn")
        assert validator is not None
        assert validator.validate("123-45-6789").valid is True
        assert validator.validate("123456789").valid is False
    
    def test_create_validator_from_config(self):
        """Test creating validator from configuration."""
        config = {
            "type": "string",
            "min_length": 5,
            "max_length": 20,
            "pattern": "^[a-zA-Z]+$"
        }
        
        validator = create_validator(config)
        assert validator.validate("Hello").valid is True
        assert validator.validate("Hi").valid is False
        assert validator.validate("Hello123").valid is False
    
    def test_create_composite_validator_from_config(self):
        """Test creating composite validator from configuration."""
        config = {
            "type": "composite",
            "mode": "ALL",
            "validators": [
                {
                    "type": "string",
                    "min_length": 5
                },
                {
                    "type": "string",
                    "pattern": "^[a-z]+$"
                }
            ]
        }
        
        validator = create_validator(config)
        assert validator.validate("hello").valid is True
        assert validator.validate("hi").valid is False
        assert validator.validate("HELLO").valid is False


class TestSchemaValidation:
    """Test schema validation functionality."""
    
    def test_simple_schema_validation(self):
        """Test simple schema validation."""
        schema = {
            "name": StringValidator(min_length=2),
            "age": NumberValidator(min_value=0, max_value=150),
            "email": StringValidator(pattern=r".*@.*\..*")
        }
        
        valid_data = {
            "name": "John",
            "age": 30,
            "email": "john@example.com"
        }
        assert validate_schema(valid_data, schema).valid is True
        
        invalid_data = {
            "name": "J",  # Too short
            "age": 200,   # Too old
            "email": "invalid"  # Bad format
        }
        result = validate_schema(invalid_data, schema)
        assert result.valid is False
        assert len(result.errors) == 3
    
    def test_nested_schema_validation(self):
        """Test nested schema validation."""
        address_schema = {
            "street": StringValidator(min_length=5),
            "city": StringValidator(min_length=2),
            "zip": StringValidator(pattern=r"^\d{5}$")
        }
        
        schema = {
            "name": StringValidator(min_length=2),
            "address": DictValidator(
                required_keys=["street", "city", "zip"],
                key_validators=address_schema
            )
        }
        
        valid_data = {
            "name": "John",
            "address": {
                "street": "123 Main St",
                "city": "New York",
                "zip": "10001"
            }
        }
        assert validate_schema(valid_data, schema).valid is True
    
    def test_array_schema_validation(self):
        """Test array schema validation."""
        schema = {
            "tags": CollectionValidator(
                min_length=1,
                max_length=5,
                item_validator=StringValidator(min_length=2)
            ),
            "scores": CollectionValidator(
                item_validator=NumberValidator(min_value=0, max_value=100)
            )
        }
        
        valid_data = {
            "tags": ["python", "testing", "validation"],
            "scores": [85, 92, 78]
        }
        assert validate_schema(valid_data, schema).valid is True
        
        invalid_data = {
            "tags": ["a"],  # Too short
            "scores": [85, 120, 78]  # 120 > 100
        }
        assert validate_schema(invalid_data, schema).valid is False


class TestValidationErrorHandling:
    """Test validation error handling."""
    
    def test_validation_error_creation(self):
        """Test creating validation errors."""
        error = ValidationError(
            field="email",
            value="invalid",
            message="Invalid email format",
            code="INVALID_EMAIL"
        )
        
        assert error.field == "email"
        assert error.value == "invalid"
        assert error.message == "Invalid email format"
        assert error.code == "INVALID_EMAIL"
        assert "email" in str(error)
        assert "Invalid email format" in str(error)
    
    def test_validation_error_with_context(self):
        """Test validation error with context."""
        context = ValidationContext(
            field_name="email",
            parent_path="user.contact"
        )
        
        error = ValidationError(
            field=context.full_path,
            value="invalid",
            message="Invalid email format",
            context=context
        )
        
        assert error.field == "user.contact.email"
        assert error.context == context
    
    def test_collect_validation_errors(self):
        """Test collecting validation errors from results."""
        results = [
            ValidationResult(False, ["Error 1", "Error 2"]),
            ValidationResult(True, warnings=["Warning 1"]),
            ValidationResult(False, ["Error 3"]),
        ]
        
        errors = []
        warnings = []
        
        for result in results:
            errors.extend(result.errors)
            warnings.extend(result.warnings)
        
        assert len(errors) == 3
        assert len(warnings) == 1
        assert "Error 1" in errors
        assert "Warning 1" in warnings


class TestAdvancedValidationPatterns:
    """Test advanced validation patterns."""
    
    def test_cross_field_validation(self):
        """Test validation across multiple fields."""
        def validate_date_range(data: Dict[str, Any]) -> ValidationResult:
            start = data.get("start_date")
            end = data.get("end_date")
            
            if start and end and start > end:
                return ValidationResult(False, ["End date must be after start date"])
            return ValidationResult(True)
        
        schema = {
            "start_date": DateValidator(),
            "end_date": DateValidator(),
        }
        
        # Add cross-field validator
        validator = DictValidator(
            key_validators=schema,
            custom_validators=[validate_date_range]
        )
        
        valid_data = {
            "start_date": datetime(2024, 1, 1),
            "end_date": datetime(2024, 12, 31)
        }
        assert validator.validate(valid_data).valid is True
        
        invalid_data = {
            "start_date": datetime(2024, 12, 31),
            "end_date": datetime(2024, 1, 1)
        }
        assert validator.validate(invalid_data).valid is False
    
    def test_conditional_required_fields(self):
        """Test conditionally required fields."""
        def validate_payment_method(data: Dict[str, Any]) -> ValidationResult:
            method = data.get("payment_method")
            
            if method == "credit_card" and not data.get("card_number"):
                return ValidationResult(False, ["Card number required for credit card payment"])
            
            if method == "bank_transfer" and not data.get("account_number"):
                return ValidationResult(False, ["Account number required for bank transfer"])
            
            return ValidationResult(True)
        
        validator = DictValidator(
            required_keys=["payment_method"],
            custom_validators=[validate_payment_method]
        )
        
        # Credit card requires card_number
        assert validator.validate({
            "payment_method": "credit_card",
            "card_number": "1234-5678-9012-3456"
        }).valid is True
        
        assert validator.validate({
            "payment_method": "credit_card"
        }).valid is False
        
        # Bank transfer requires account_number
        assert validator.validate({
            "payment_method": "bank_transfer",
            "account_number": "123456789"
        }).valid is True
    
    def test_recursive_validation(self):
        """Test recursive data structure validation."""
        # Define recursive validator for tree structure
        tree_validator = DictValidator(
            required_keys=["value"],
            optional_keys=["children"],
        )
        
        # Add children validator
        tree_validator.key_validators["children"] = CollectionValidator(
            item_validator=tree_validator  # Recursive reference
        )
        
        valid_tree = {
            "value": "root",
            "children": [
                {
                    "value": "child1",
                    "children": [
                        {"value": "grandchild1"},
                        {"value": "grandchild2"}
                    ]
                },
                {
                    "value": "child2"
                }
            ]
        }
        
        assert tree_validator.validate(valid_tree).valid is True
        
        invalid_tree = {
            "value": "root",
            "children": [
                {
                    # Missing required "value" field
                    "children": [{"value": "grandchild"}]
                }
            ]
        }
        
        assert tree_validator.validate(invalid_tree).valid is False