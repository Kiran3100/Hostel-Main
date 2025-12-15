# app/services/notification/template_service.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional, Protocol
from uuid import uuid4

from app.schemas.notification.notification_template import (
    TemplateCreate,
    TemplateUpdate,
    TemplateResponse,
    VariableMapping,
    TemplatePreview,
    TemplatePreviewResponse,
    TemplateList,
)
from app.services.common import errors


class TemplateStore(Protocol):
    """
    Abstract storage for notification templates (TemplateResponse-like dicts).
    """

    def get_template(self, template_code: str) -> Optional[dict]: ...
    def save_template(self, template_code: str, data: dict) -> None: ...
    def delete_template(self, template_code: str) -> None: ...
    def list_templates(self) -> List[dict]: ...


class TemplateService:
    """
    Manage notification templates:

    - Create / update / delete
    - List templates
    - Render / preview templates with variables
    """

    def __init__(self, store: TemplateStore) -> None:
        self._store = store

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    # ------------------------------------------------------------------ #
    # CRUD
    # ------------------------------------------------------------------ #
    def create_template(self, data: TemplateCreate) -> TemplateResponse:
        if self._store.get_template(data.template_code):
            raise errors.ConflictError(
                f"Template {data.template_code!r} already exists"
            )

        now = self._now()
        record = {
            "id": uuid4(),
            "created_at": now,
            "updated_at": now,
            "template_code": data.template_code,
            "template_name": data.template_name,
            "template_type": data.template_type,
            "subject": data.subject,
            "body_template": data.body_template,
            "variables": data.variables,
            "is_active": data.is_active,
            "description": data.description,
            "usage_count": 0,
            "last_used_at": None,
        }
        self._store.save_template(data.template_code, record)
        return TemplateResponse.model_validate(record)

    def update_template(
        self,
        template_code: str,
        data: TemplateUpdate,
    ) -> TemplateResponse:
        record = self._store.get_template(template_code)
        if not record:
            raise errors.NotFoundError(f"Template {template_code!r} not found")

        mapping = data.model_dump(exclude_unset=True)
        for field, value in mapping.items():
            record[field] = value
        record["updated_at"] = self._now()

        self._store.save_template(template_code, record)
        return TemplateResponse.model_validate(record)

    def delete_template(self, template_code: str) -> None:
        record = self._store.get_template(template_code)
        if not record:
            raise errors.NotFoundError(f"Template {template_code!r} not found")
        self._store.delete_template(template_code)

    def get_template(self, template_code: str) -> TemplateResponse:
        record = self._store.get_template(template_code)
        if not record:
            raise errors.NotFoundError(f"Template {template_code!r} not found")
        return TemplateResponse.model_validate(record)

    def list_templates(self) -> TemplateList:
        records = self._store.list_templates()
        templates = [TemplateResponse.model_validate(r) for r in records]
        total = len(templates)
        active = sum(1 for t in templates if t.is_active)
        return TemplateList(
            total_templates=total,
            active_templates=active,
            templates=templates,
        )

    # ------------------------------------------------------------------ #
    # Rendering / preview
    # ------------------------------------------------------------------ #
    def render_template(
        self,
        template_code: str,
        variables: Dict[str, str],
        *,
        mark_used: bool = False,
    ) -> TemplatePreviewResponse:
        record = self._store.get_template(template_code)
        if not record:
            raise errors.NotFoundError(f"Template {template_code!r} not found")

        tmpl = TemplateResponse.model_validate(record)
        missing_vars = [v for v in tmpl.variables if v not in variables]
        all_provided = not missing_vars

        body = tmpl.body_template
        for key, value in variables.items():
            body = body.replace(f"{{{{{key}}}}}", value)

        if mark_used:
            record["usage_count"] = int(record.get("usage_count") or 0) + 1
            record["last_used_at"] = self._now()
            self._store.save_template(template_code, record)

        return TemplatePreviewResponse(
            subject=tmpl.subject,
            rendered_body=body,
            all_variables_provided=all_provided,
            missing_variables=missing_vars,
        )

    def preview(self, data: TemplatePreview) -> TemplatePreviewResponse:
        return self.render_template(
            template_code=data.template_code,
            variables=data.variables,
            mark_used=False,
        )