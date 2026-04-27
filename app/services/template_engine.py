"""Template Engine for Email_Scheduler.

Handles template CRUD, placeholder parsing, validation, rendering,
and JSON serialization/deserialization.
Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6
"""

import json
import re
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.orm import Session

from app.models.models import Template

# Regex for valid placeholders: {{field_name}} where field_name is alphanumeric + underscore
PLACEHOLDER_PATTERN = re.compile(r"\{\{(\w+)\}\}")
# Regex for any {{ ... }} pattern (including malformed ones)
ANY_BRACE_PATTERN = re.compile(r"\{\{.*?\}\}")


@dataclass
class ValidationResult:
    valid: bool
    valid_placeholders: list[str] = field(default_factory=list)
    invalid_placeholders: list[str] = field(default_factory=list)


@dataclass
class RenderedEmail:
    subject: str
    body: str


@dataclass
class RenderResult:
    success: bool
    rendered: Optional[RenderedEmail] = None
    missing_fields: list[str] = field(default_factory=list)


def extract_placeholders(text: str) -> list[str]:
    """Extract all valid placeholder names from text."""
    return PLACEHOLDER_PATTERN.findall(text)


def find_all_brace_patterns(text: str) -> list[str]:
    """Find all {{...}} patterns in text, including malformed ones."""
    return ANY_BRACE_PATTERN.findall(text)


def validate_template(subject: str, body: str) -> ValidationResult:
    """Validate that all placeholders in subject and body conform to supported syntax.

    Valid placeholder syntax: {{field_name}} where field_name contains only
    alphanumeric characters and underscores.

    Requirement 2.1: Support Dynamic_Field placeholders.
    Requirement 2.4: Validate placeholder syntax on edit.
    """
    combined = subject + " " + body

    all_patterns = find_all_brace_patterns(combined)
    valid_matches = PLACEHOLDER_PATTERN.findall(combined)

    # Reconstruct valid patterns for comparison
    valid_patterns = {f"{{{{{name}}}}}" for name in valid_matches}

    invalid = [p for p in all_patterns if p not in valid_patterns]
    valid_names = list(dict.fromkeys(valid_matches))  # deduplicate, preserve order

    return ValidationResult(
        valid=len(invalid) == 0,
        valid_placeholders=valid_names,
        invalid_placeholders=invalid,
    )


def render_template(subject: str, body: str, context: dict[str, str]) -> RenderResult:
    """Render a template by replacing placeholders with context values.

    Requirement 2.2: Replace all Dynamic_Field placeholders with Recipient-specific values.
    Requirement 2.3: Report unresolved fields and prevent sending.
    """
    # Collect all unique placeholder names from subject and body
    all_placeholders = set(extract_placeholders(subject)) | set(extract_placeholders(body))

    missing = sorted(all_placeholders - set(context.keys()))

    if missing:
        return RenderResult(success=False, missing_fields=missing)

    rendered_subject = PLACEHOLDER_PATTERN.sub(lambda m: context[m.group(1)], subject)
    rendered_body = PLACEHOLDER_PATTERN.sub(lambda m: context[m.group(1)], body)

    return RenderResult(
        success=True,
        rendered=RenderedEmail(subject=rendered_subject, body=rendered_body),
    )


# --- CRUD operations (database-backed) ---


def create_template(db: Session, name: str, subject: str, body: str) -> Template:
    """Create a new email template after validating placeholders.

    Requirement 2.1: Support Dynamic_Field placeholders.
    Requirement 2.4: Validate placeholder syntax.
    """
    validation = validate_template(subject, body)
    if not validation.valid:
        raise ValueError(
            f"Template contains invalid placeholders: {validation.invalid_placeholders}"
        )

    template = Template(name=name, subject=subject, body=body)
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def get_template(db: Session, template_id: int) -> Template | None:
    """Retrieve a template by ID."""
    return db.query(Template).filter(Template.id == template_id).first()


def list_templates(db: Session) -> list[Template]:
    """List all templates."""
    return db.query(Template).all()


def update_template(
    db: Session, template_id: int, name: str | None = None,
    subject: str | None = None, body: str | None = None,
) -> Template | None:
    """Update an existing template. Validates placeholders if subject or body changes.

    Requirement 2.4: Validate placeholder syntax on edit.
    """
    template = get_template(db, template_id)
    if template is None:
        return None

    new_subject = subject if subject is not None else template.subject
    new_body = body if body is not None else template.body

    if subject is not None or body is not None:
        validation = validate_template(new_subject, new_body)
        if not validation.valid:
            raise ValueError(
                f"Template contains invalid placeholders: {validation.invalid_placeholders}"
            )

    if name is not None:
        template.name = name
    if subject is not None:
        template.subject = new_subject
    if body is not None:
        template.body = new_body

    db.commit()
    db.refresh(template)
    return template


def delete_template(db: Session, template_id: int) -> bool:
    """Delete a template by ID."""
    template = get_template(db, template_id)
    if template is None:
        return False
    db.delete(template)
    db.commit()
    return True


# --- Serialization / Deserialization ---


@dataclass
class TemplateData:
    """Plain data representation of a template for serialization."""
    name: str
    subject: str
    body: str
    id: int | None = None


def serialize_template(template) -> str:
    """Serialize a Template (ORM model or TemplateData) to a JSON string.

    Requirement 2.5: Encode template using JSON format.
    """
    data = {
        "name": template.name,
        "subject": template.subject,
        "body": template.body,
    }
    if hasattr(template, "id") and template.id is not None:
        data["id"] = template.id
    return json.dumps(data, ensure_ascii=False)


def deserialize_template(json_str: str) -> TemplateData:
    """Deserialize a JSON string back into a TemplateData object.

    Requirement 2.6: Deserialize JSON and reconstruct the original Template
    with all Dynamic_Field placeholders intact.
    """
    data = json.loads(json_str)

    required_keys = {"name", "subject", "body"}
    missing = required_keys - set(data.keys())
    if missing:
        raise ValueError(f"Missing required fields in JSON: {missing}")

    return TemplateData(
        name=data["name"],
        subject=data["subject"],
        body=data["body"],
        id=data.get("id"),
    )
