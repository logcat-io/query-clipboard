"""Tests for the domain layer - ZERO infrastructure dependencies."""
import ast
import os

import pytest

from server.core.domain.model.query import Query
from server.core.domain.model.purpose import Purpose
from server.core.domain.exception.domain_exception import (
    InvalidQueryException,
    InvalidPurposeException,
    QueryNotFoundException,
    DomainException,
)


class TestQueryCreation:
    def test_query_creation(self):
        query = Query(
            id=1, title="Test Query", description="A test query",
            purpose_id=1, tags="test,sample", sql_text="SELECT 1;",
        )
        assert query.id == 1
        assert query.title == "Test Query"
        assert query.purpose_id == 1
        assert query.created_at is None


class TestQueryValidation:
    def test_query_validate_valid(self):
        query = Query(title="Valid Title", purpose_id=1, sql_text="SELECT 1;")
        query.validate()

    def test_query_validate_empty_title(self):
        query = Query(title="", purpose_id=1, sql_text="SELECT 1;")
        with pytest.raises(InvalidQueryException, match="제목은 필수입니다"):
            query.validate()

    def test_query_validate_whitespace_title(self):
        query = Query(title="   ", purpose_id=1, sql_text="SELECT 1;")
        with pytest.raises(InvalidQueryException):
            query.validate()

    def test_query_validate_empty_sql(self):
        query = Query(title="Title", purpose_id=1, sql_text="")
        with pytest.raises(InvalidQueryException, match="SQL은 필수입니다"):
            query.validate()

    def test_query_validate_whitespace_sql(self):
        query = Query(title="Title", purpose_id=1, sql_text="   ")
        with pytest.raises(InvalidQueryException):
            query.validate()


class TestPurposeValidation:
    def test_purpose_creation(self):
        purpose = Purpose(name="test-purpose", sort_order=0)
        assert purpose.name == "test-purpose"

    def test_purpose_validate_empty_name(self):
        purpose = Purpose(name="", sort_order=0)
        with pytest.raises(InvalidPurposeException, match="용도 이름은 필수입니다"):
            purpose.validate()


class TestDomainExceptions:
    def test_invalid_query_exception_is_domain_exception(self):
        assert issubclass(InvalidQueryException, DomainException)

    def test_invalid_purpose_exception_is_domain_exception(self):
        assert issubclass(InvalidPurposeException, DomainException)

    def test_query_not_found_exception(self):
        ex = QueryNotFoundException(42)
        assert ex.query_id == 42
        assert "42" in str(ex)


class TestDomainPurity:
    def test_domain_has_no_framework_imports(self):
        domain_dir = os.path.join(
            os.path.dirname(__file__), "..", "server", "core", "domain",
        )
        domain_dir = os.path.abspath(domain_dir)
        forbidden = {"fastapi", "sqlalchemy", "uvicorn", "starlette", "httpx"}

        for root, _dirs, files in os.walk(domain_dir):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                filepath = os.path.join(root, fname)
                with open(filepath) as f:
                    source = f.read()
                tree = ast.parse(source)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            top_module = alias.name.split(".")[0]
                            assert top_module not in forbidden
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            top_module = node.module.split(".")[0]
                            assert top_module not in forbidden
