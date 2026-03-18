"""Tests for the domain layer - ZERO infrastructure dependencies."""
import ast
import os

import pytest

from server.core.domain.model.query import Query
from server.core.domain.exception.domain_exception import (
    InvalidQueryException,
    QueryNotFoundException,
    DomainException,
)


class TestQueryCreation:
    def test_query_creation(self):
        """Create a valid Query entity with all fields."""
        query = Query(
            id=1,
            title="Test Query",
            description="A test query",
            purpose="조회",
            tags="test,sample",
            sql_text="SELECT 1;",
        )
        assert query.id == 1
        assert query.title == "Test Query"
        assert query.description == "A test query"
        assert query.purpose == "조회"
        assert query.tags == "test,sample"
        assert query.sql_text == "SELECT 1;"
        assert query.created_at is None


class TestQueryValidation:
    def test_query_validate_valid(self):
        """Validate succeeds for valid data."""
        query = Query(
            title="Valid Title",
            description="desc",
            purpose="조회",
            tags="tag",
            sql_text="SELECT 1;",
        )
        # Should not raise
        query.validate()

    def test_query_validate_empty_title(self):
        """Validate raises InvalidQueryException for empty title."""
        query = Query(
            title="",
            description="desc",
            purpose="조회",
            tags="tag",
            sql_text="SELECT 1;",
        )
        with pytest.raises(InvalidQueryException, match="제목은 필수입니다"):
            query.validate()

    def test_query_validate_whitespace_title(self):
        """Validate raises InvalidQueryException for whitespace-only title."""
        query = Query(
            title="   ",
            description="desc",
            purpose="조회",
            tags="tag",
            sql_text="SELECT 1;",
        )
        with pytest.raises(InvalidQueryException):
            query.validate()

    def test_query_validate_invalid_purpose(self):
        """Validate raises InvalidQueryException for invalid purpose."""
        query = Query(
            title="Title",
            description="desc",
            purpose="INVALID",
            tags="tag",
            sql_text="SELECT 1;",
        )
        with pytest.raises(InvalidQueryException, match="유효하지 않은 용도"):
            query.validate()

    def test_query_validate_empty_sql(self):
        """Validate raises InvalidQueryException for empty sql_text."""
        query = Query(
            title="Title",
            description="desc",
            purpose="조회",
            tags="tag",
            sql_text="",
        )
        with pytest.raises(InvalidQueryException, match="SQL은 필수입니다"):
            query.validate()

    def test_query_validate_whitespace_sql(self):
        """Validate raises InvalidQueryException for whitespace-only sql_text."""
        query = Query(
            title="Title",
            description="desc",
            purpose="조회",
            tags="tag",
            sql_text="   ",
        )
        with pytest.raises(InvalidQueryException):
            query.validate()


class TestValidPurposes:
    def test_valid_purposes_list(self):
        """VALID_PURPOSES contains all 5 options."""
        assert Query.VALID_PURPOSES == ("조회", "수정", "삭제", "집계", "기타")
        assert len(Query.VALID_PURPOSES) == 5

    def test_each_purpose_validates(self):
        """Each valid purpose passes validation."""
        for purpose in Query.VALID_PURPOSES:
            query = Query(
                title="Title",
                description=None,
                purpose=purpose,
                tags="",
                sql_text="SELECT 1;",
            )
            query.validate()  # Should not raise


class TestDomainExceptions:
    def test_invalid_query_exception_is_domain_exception(self):
        assert issubclass(InvalidQueryException, DomainException)

    def test_query_not_found_exception(self):
        ex = QueryNotFoundException(42)
        assert ex.query_id == 42
        assert "42" in str(ex)


class TestDomainPurity:
    def test_domain_has_no_framework_imports(self):
        """Verify domain layer files do NOT import sqlalchemy, sqlmodel, fastapi, etc.
        pydantic is allowed as a data modeling library."""
        domain_dir = os.path.join(
            os.path.dirname(__file__),
            "..",
            "server",
            "core",
            "domain",
        )
        domain_dir = os.path.abspath(domain_dir)

        # pydantic is allowed; sqlmodel, sqlalchemy, fastapi, etc. are forbidden
        forbidden = {"fastapi", "sqlalchemy", "sqlmodel", "uvicorn", "starlette", "httpx"}

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
                            assert top_module not in forbidden, (
                                f"{filepath} imports forbidden module '{alias.name}'"
                            )
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            top_module = node.module.split(".")[0]
                            assert top_module not in forbidden, (
                                f"{filepath} imports from forbidden module '{node.module}'"
                            )
