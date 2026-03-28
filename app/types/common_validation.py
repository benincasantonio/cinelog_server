"""
Common validation types shared across multiple domains.

When a validator or Annotated type is used by more than one domain
(e.g. both user and log schemas), it belongs here. Domain-specific
validators should live in their respective ``app/types/<domain>_validation.py``
module instead.
"""
