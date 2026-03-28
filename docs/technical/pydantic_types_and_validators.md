# Types and Validators

This document describes the reusable validation types system in Cinelog, located in `app/types/`.

## Overview

The `app/types/` package provides reusable Pydantic `Annotated` types that bundle validation logic with field constraints. This eliminates the need for inline `@field_validator` methods in schema classes and ensures consistent validation across the codebase.

## File Structure

```
app/types/
├── __init__.py              # Re-exports all public types and functions
├── common_validation.py     # Cross-domain validators shared by multiple domains
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
| `OptionalNameStr` | Optional name (`None` or 1–50 chars) |
| `HandleStr` | Required handle (3–20 chars, alphanumeric + underscore, no leading digit) |
| `OptionalHandleStr` | Optional handle (`None` or 3–20 chars) |
| `BioStr` | Optional bio (`None` or up to 500 chars, HTML tags stripped) |

### log_validation.py

Log-related validators used by `log_schemas`.

| Type | Description |
|------|-------------|
| `WatchedWhereStr` | Required watched_where (must be one of the allowed choices) |
| `OptionalWatchedWhereStr` | Optional watched_where (`None` or one of the allowed choices) |

### common_validation.py

Validators that span multiple domains. Currently empty — as cross-domain needs emerge (e.g., generic text sanitization), they go here.

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

## Adding a New Validator

1. Identify the domain (user, log, movie, etc.)
2. Create or open the corresponding `<domain>_validation.py` file
3. Add the validation function and Annotated type alias
4. Update `app/types/__init__.py` to re-export the new type
5. Use the type in schema fields — never define inline `@field_validator`

If the validator applies to multiple domains, place it in `common_validation.py` instead.

## Relationship to `app/utils/sanitize_utils.py`

`sanitize_utils.py` provides low-level patterns and helpers (regex patterns, `strip_html_tags`). The validation functions in `app/types/` build on these utilities to create full validators with error messages and constraints.

## See Also

- [Architecture Reference](../../ARCHITECTURE.md)
- [AGENTS.md](../../AGENTS.md) — Types and Validators convention rules
