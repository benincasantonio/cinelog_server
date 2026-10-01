# Validation Error Sanitization

## Problem

FastAPI's default `RequestValidationError` handler echoes the submitted request payload back in each 422 error entry's `input` field. For auth endpoints this leaked cleartext passwords and reset codes into browser devtools, proxy/WAF/CDN logs, and monitoring tools (security audit finding, issue #24).

## Behavior

A custom `RequestValidationError` handler in `app/__init__.py` returns the standard `{"detail": [...]}` shape but strips the `input` echo (and pydantic's docs `url`) from every entry via `sanitize_validation_errors()` in `app/utils/validation_error_utils.py`. Dropping the field entirely — instead of redacting a denylist of sensitive keys — means newly added fields can never leak by omission.

Clients keep full field-level feedback through `type`, `loc`, `msg`, and `ctx`:

```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "email"],
      "msg": "value is not a valid email address: An email address must have an @-sign.",
      "ctx": { "reason": "An email address must have an @-sign." }
    },
    { "type": "missing", "loc": ["body", "dateOfBirth"], "msg": "Field required" }
  ]
}
```

## Implementation notes

- `ctx` values that are exceptions (custom `@field_validator`s raising `ValueError`) are stringified before JSON encoding — `jsonable_encoder` alone would flatten them to `{}`.
- The handler applies app-wide: every endpoint's 422 response is sanitized, not just auth routes.

## Tests

- `tests/units/utils/test_validation_error_utils.py` — sanitizer unit tests
- `tests/units/controllers/test_auth_controller.py` — register/login/reset-password 422 responses contain no submitted secrets
- `tests/e2e/test_auth_e2e.py::test_validation_error_does_not_echo_password` — full-stack regression

## See Also

- [Authentication (technical)](authentication.md)
