# Types and Validators

This document describes the reusable validation types system in Cinelog, located in `app/types/`.

## Overview

The `app/types/` package provides reusable Pydantic `Annotated` types that bundle validation logic with field constraints, as well as closed enum types shared across application layers. This eliminates duplicate validation and enum declarations and ensures consistent contracts across the codebase.

## File Structure

```
app/types/
├── __init__.py              # Re-exports all public types and functions
├── common_validation.py     # Cross-domain validators shared by multiple domains
├── cursor_pagination_types.py # Reusable typed pagination cursor values
├── notification_types.py    # Closed notification and action enums
├── user_validation.py       # User-related: NameStr, HandleStr, BioStr
└── log_validation.py        # Log-related: WatchedWhereStr
```

## Domain Files

Each `<domain>_validation.py` file contains:

1. **Validation functions** — pure functions that take a value, validate/transform it, and return the result
2. **Annotated type aliases** — Pydantic `Annotated` types combining `AfterValidator` with `StringConstraints`
3. **Module-level docstring** — documents all exported types and their purpose

### user_validation.py

User-related validators used by `auth_schemas` and `user_schemas`.

| Type | Description |
|------|-------------|
| `NameStr` | Required name (1–50 chars, letters/accents/hyphens only) |
| `HandleStr` | Required handle (3–20 chars, alphanumeric + underscore, no leading digit; casing preserved) |
| `BioStr` | Optional bio (`None` or up to 500 chars, HTML tags stripped) |
| `ProfileVisibilityStr` | Required profile visibility (`public`, `followers_only`, or `private`) |

### log_validation.py

Log-related validators used by `log_schemas`.

| Type | Description |
|------|-------------|
| `WatchedWhereStr` | Required watched_where (must be one of the allowed choices) |

### common_validation.py

| Type | Description |
|------|-------------|
| `RatingInt` | Integer from 1 through 10, shared by log and movie-rating schemas |

### notification_types.py

Closed `NotificationType` and `NotificationAction` enums shared by persistence, services, schemas, and API contract tests. This module contains no validators.

### cursor_pagination_types.py

Reusable strongly typed cursor-pagination values shared by repositories and encoding utilities. Serialization and signing remain in `app/utils/cursor_pagination_utils.py`.

## Usage

Import types from the `app.types` package:

```python
from app.types import NameStr, HandleStr, BioStr

class RegisterRequest(BaseSchema):
    first_name: NameStr = Field(description="User's first name")
    last_name: NameStr = Field(description="User's last name")
    handle: HandleStr = Field(description="User's unique handle")
    bio: BioStr = Field(None, description="User biography")
```

No `@field_validator` methods needed — validation is handled by the Annotated type.

For optional validated fields, use `Type | None` inline in the schema — do not create a separate `Optional{Type}` alias in `app/types/`:

```python
# correct
watched_where: WatchedWhereStr | None = Field(None, ...)
profile_visibility: ProfileVisibilityStr | None = Field(None, ...)

# wrong — do not add OptionalWatchedWhereStr to app/types/
watched_where: OptionalWatchedWhereStr = Field(None, ...)
```

## Adding a New Validator

1. Identify the domain (user, log, movie, etc.)
2. Create or open the corresponding `<domain>_validation.py` file
3. Add the validation function and Annotated type alias
4. Update `app/types/__init__.py` to re-export the new type
5. Use the type in schema fields — never define inline `@field_validator`
6. For optional fields, write `YourType | None` in the schema rather than creating an `OptionalYourType` alias

If the validator applies to multiple domains, place it in `common_validation.py` instead.

## Relationship to `app/utils/sanitize_utils.py`

`sanitize_utils.py` provides low-level patterns and helpers (regex patterns, `strip_html_tags`). The validation functions in `app/types/` build on these utilities to create full validators with error messages and constraints.

## See Also

- [Architecture Reference](../../ARCHITECTURE.md)
- [AGENTS.md](../../AGENTS.md) — Types and Validators convention rules
