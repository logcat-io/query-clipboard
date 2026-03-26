class DomainException(Exception):
    """Base exception for domain layer."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class QueryNotFoundException(DomainException):
    """Raised when a query is not found."""

    def __init__(self, query_id: int):
        super().__init__(f"쿼리를 찾을 수 없습니다: id={query_id}")
        self.query_id = query_id


class InvalidQueryException(DomainException):
    """Raised when a query fails validation."""
    pass


class InvalidPurposeException(DomainException):
    """Raised when a purpose fails validation."""
    pass
