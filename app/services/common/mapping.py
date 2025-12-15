# app/services/common/mapping.py
"""
Model-Schema mapping utilities.

Provides type-safe conversion between ORM models and Pydantic schemas,
with support for batch operations and custom field exclusions.
"""
from __future__ import annotations

from typing import Any, Callable, Iterable, Optional, Sequence, Type, TypeVar, overload

from pydantic import BaseModel, ValidationError

from .errors import ServiceError

TModel = TypeVar("TModel")
TSchema = TypeVar("TSchema", bound=BaseModel)


class MappingError(ServiceError):
    """Raised when model-to-schema conversion fails."""
    
    def __init__(self, message: str, source_obj: Any = None) -> None:
        super().__init__(message, details={"source_type": type(source_obj).__name__})
        self.source_obj = source_obj


def to_schema(
    obj: Optional[TModel],
    schema_cls: Type[TSchema],
    *,
    strict: bool = True,
) -> TSchema:
    """
    Convert an ORM model to a Pydantic schema.

    Args:
        obj: Source ORM model instance
        schema_cls: Target Pydantic schema class
        strict: If True, raise error on None; if False, return None-like behavior

    Returns:
        Validated Pydantic schema instance

    Raises:
        MappingError: If conversion fails or obj is None (when strict=True)

    Example:
        >>> user_schema = to_schema(db_user, UserSchema)
    """
    if obj is None:
        if strict:
            raise MappingError(
                f"Cannot convert None to {schema_cls.__name__}",
                source_obj=obj,
            )
        # Type checker won't like this, but it's guarded by strict=False
        return None  # type: ignore

    try:
        return schema_cls.model_validate(obj)
    except ValidationError as exc:
        raise MappingError(
            f"Failed to convert {type(obj).__name__} to {schema_cls.__name__}: {exc}",
            source_obj=obj,
        ) from exc


def to_schema_list(
    objs: Iterable[TModel],
    schema_cls: Type[TSchema],
    *,
    skip_invalid: bool = False,
) -> list[TSchema]:
    """
    Convert an iterable of ORM models to a list of Pydantic schemas.

    Args:
        objs: Iterable of ORM model instances
        schema_cls: Target Pydantic schema class
        skip_invalid: If True, skip items that fail validation instead of raising

    Returns:
        List of validated Pydantic schema instances

    Raises:
        MappingError: If any conversion fails (when skip_invalid=False)

    Example:
        >>> users = to_schema_list(db_users, UserSchema)
    """
    results: list[TSchema] = []
    
    for idx, obj in enumerate(objs):
        try:
            results.append(schema_cls.model_validate(obj))
        except ValidationError as exc:
            if skip_invalid:
                continue
            raise MappingError(
                f"Failed to convert item at index {idx} to {schema_cls.__name__}: {exc}",
                source_obj=obj,
            ) from exc
    
    return results


def update_model_from_schema(
    model_obj: TModel,
    schema_obj: BaseModel,
    *,
    exclude_unset: bool = True,
    exclude_none: bool = False,
    exclude_fields: Optional[Sequence[str]] = None,
    include_fields: Optional[Sequence[str]] = None,
) -> TModel:
    """
    Update an ORM model instance with data from a Pydantic schema.

    Args:
        model_obj: Target ORM model instance to update
        schema_obj: Source Pydantic schema with update data
        exclude_unset: Only update fields that were explicitly set
        exclude_none: Skip fields with None values
        exclude_fields: Field names to exclude from update
        include_fields: If provided, only update these fields

    Returns:
        Updated model instance (same object, modified in-place)

    Example:
        >>> update_model_from_schema(
        ...     db_user,
        ...     user_update_schema,
        ...     exclude_fields=["id", "created_at"]
        ... )
    """
    if model_obj is None:
        raise MappingError("Cannot update None model object")

    # Extract data from schema
    data = schema_obj.model_dump(
        exclude_unset=exclude_unset,
        exclude_none=exclude_none,
    )

    # Apply field filters
    if exclude_fields:
        exclude_set = set(exclude_fields)
        data = {k: v for k, v in data.items() if k not in exclude_set}

    if include_fields:
        include_set = set(include_fields)
        data = {k: v for k, v in data.items() if k in include_set}

    # Update model attributes
    updated_fields: list[str] = []
    for field_name, value in data.items():
        if hasattr(model_obj, field_name):
            setattr(model_obj, field_name, value)
            updated_fields.append(field_name)

    return model_obj


def batch_update_models(
    model_objs: Iterable[TModel],
    update_data: dict[Any, BaseModel],
    *,
    key_attr: str = "id",
    **kwargs: Any,
) -> list[TModel]:
    """
    Batch update multiple models using a mapping of updates.

    Args:
        model_objs: Iterable of model instances
        update_data: Dict mapping model key to update schema
        key_attr: Attribute name to use as key (default: "id")
        **kwargs: Additional arguments passed to update_model_from_schema

    Returns:
        List of updated model instances

    Example:
        >>> updates = {user1.id: update_schema1, user2.id: update_schema2}
        >>> batch_update_models(users, updates)
    """
    updated: list[TModel] = []
    
    for model_obj in model_objs:
        key = getattr(model_obj, key_attr)
        if key in update_data:
            update_model_from_schema(model_obj, update_data[key], **kwargs)
            updated.append(model_obj)
    
    return updated


def map_with_custom_logic(
    obj: TModel,
    schema_cls: Type[TSchema],
    mapper_fn: Optional[Callable[[TModel, TSchema], TSchema]] = None,
) -> TSchema:
    """
    Convert model to schema with optional post-processing.

    Args:
        obj: Source model instance
        schema_cls: Target schema class
        mapper_fn: Optional function to customize the converted schema

    Returns:
        Validated and optionally customized schema instance

    Example:
        >>> def add_computed_field(model, schema):
        ...     schema.full_name = f"{model.first_name} {model.last_name}"
        ...     return schema
        >>> user_schema = map_with_custom_logic(db_user, UserSchema, add_computed_field)
    """
    schema_instance = to_schema(obj, schema_cls)
    
    if mapper_fn:
        schema_instance = mapper_fn(obj, schema_instance)
    
    return schema_instance