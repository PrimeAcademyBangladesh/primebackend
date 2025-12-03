"""Reusable password validation helpers.

Centralize password strength rules so multiple serializers can reuse
the same logic without duplication.
"""
from django.contrib.auth.password_validation import \
    validate_password as django_validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers


def validate_password_strength(value: str, user=None) -> str:
    """Validate password strength and raise serializers.ValidationError on failure.

    Strategy: run Django's configured validators first via
    `django.contrib.auth.password_validation.validate_password`. If they
    pass, additionally run a small local set of checks as a fallback/extra.

    Accepts optional `user` for similarity checks.
    """
    try:
        django_validate_password(value, user=user)
    except DjangoValidationError as e:
        # Convert to DRF ValidationError with the list of messages
        raise serializers.ValidationError(list(e.messages))

    # Local extra checks (kept for parity with previous behavior)
    common_passwords = ["password", "12345678", "qwerty123", "admin123"]

    if value.lower() in common_passwords:
        raise serializers.ValidationError(
            "This password is too common. Please choose a stronger password."
        )

    if len(value) < 8:
        raise serializers.ValidationError("Password must be at least 8 characters.")

    if not any(char.isdigit() for char in value):
        raise serializers.ValidationError("Password must contain at least one digit.")

    if not any(char.isalpha() for char in value):
        raise serializers.ValidationError("Password must contain at least one letter.")

    if not any(char in "!@#$%^&*()_+-=[]{}|;:,.<>?/" for char in value):
        raise serializers.ValidationError(
            "Password must contain at least one special character."
        )

    return value
