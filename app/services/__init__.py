# app/services/__init__.py
"""
Service layer root package.

Each subpackage implements application use-cases on top of:

- SQLAlchemy models (app.models.*)
- Repositories (app.repositories.*)
- Pydantic schemas (app.schemas.*)
- Common service infrastructure (app.services.common.*)

Typical pattern for a service:

    class SomeService:
        def __init__(self, session_factory: Callable[[], Session]) -> None:
            self._session_factory = session_factory

        def some_use_case(...):
            with UnitOfWork(self._session_factory) as uow:
                repo = uow.get_repo(SomeRepository)
                ...
"""

from app.services.common import UnitOfWork, security, permissions, mapping, pagination

__all__ = [
    "UnitOfWork",
    "security",
    "permissions",
    "mapping",
    "pagination",
]