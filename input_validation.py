"""
Input validation utilities for Agency OS.

Provides sanitization for user-controlled inputs that touch the filesystem
or are used in security-sensitive contexts (client IDs, filenames, paths).
"""

import os
import re

# Only allow alphanumeric, underscores, hyphens, and spaces in client IDs
CLIENT_ID_RE = re.compile(r"^[a-zA-Z0-9_\- ]+$")

# Block any path traversal sequences in filenames
PATH_TRAVERSAL_SEQUENCES = {"../", "..\\", "..", "%2e%2e", "%2f", "%5c"}


class InputValidationError(ValueError):
    """Raised when user input fails validation."""

    pass


def validate_client_id(client_id: str) -> str:
    """
    Validate and sanitize a client ID.

    Ensures the client ID contains only safe characters and cannot be used
    for path traversal attacks.

    Returns the stripped client_id on success.
    Raises InputValidationError on failure.
    """
    cleaned = str(client_id or "").strip()
    if not cleaned:
        raise InputValidationError("Client ID cannot be empty.")
    if len(cleaned) > 128:
        raise InputValidationError("Client ID exceeds maximum length of 128 characters.")
    if not CLIENT_ID_RE.match(cleaned):
        raise InputValidationError(
            f"Client ID '{cleaned}' contains invalid characters. "
            "Only letters, numbers, underscores, hyphens, and spaces are allowed."
        )
    # Extra safety: reject anything that looks like path traversal
    if ".." in cleaned:
        raise InputValidationError("Client ID cannot contain path traversal sequences.")
    return cleaned


def validate_filename(filename: str) -> str:
    """
    Validate and sanitize a filename.

    Strips path components, rejects traversal sequences, and ensures
    the filename is a simple basename.

    Returns the sanitized filename.
    Raises InputValidationError on failure.
    """
    cleaned = str(filename or "").strip()
    if not cleaned:
        raise InputValidationError("Filename cannot be empty.")
    if len(cleaned) > 255:
        raise InputValidationError("Filename exceeds maximum length of 255 characters.")

    # Reject path traversal
    lowered = cleaned.lower()
    for seq in PATH_TRAVERSAL_SEQUENCES:
        if seq in lowered:
            raise InputValidationError(
                f"Filename '{cleaned}' contains path traversal sequences."
            )

    # Extract just the basename to prevent directory injection
    basename = os.path.basename(cleaned)
    if not basename or basename != cleaned:
        # The filename contained directory separators
        raise InputValidationError(
            f"Filename '{cleaned}' contains directory separators. Provide a simple filename only."
        )

    return basename


def safe_join_path(base_dir: str, *parts: str) -> str:
    """
    Safely join a base directory with user-provided path components.

    Resolves the final path and verifies it remains under base_dir.
    This prevents path traversal even if individual validation is bypassed.

    Returns the resolved absolute path.
    Raises InputValidationError if the result escapes base_dir.
    """
    resolved_base = os.path.realpath(base_dir)
    joined = os.path.join(resolved_base, *parts)
    resolved_joined = os.path.realpath(joined)

    if not resolved_joined.startswith(resolved_base + os.sep) and resolved_joined != resolved_base:
        raise InputValidationError(
            f"Path resolution escaped the allowed directory. "
            f"Base: {resolved_base}, Resolved: {resolved_joined}"
        )

    return resolved_joined
