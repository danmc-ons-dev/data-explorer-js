"""
api_error_handler.py - Centralized Error Handling for R API Calls

Implements Inversion of Control (IoC) using the Strategy Pattern:
- Each error type (503 throttling, 413 file too large, 502, 5xx) has its own handler
- A central registry manages strategies and finds the right one by status code
- Adding new error types requires only creating a new strategy class

This design ensures:
- Consistent error handling across all indicator routes
- Helpful, contextual error messages for users
- Easy extensibility for future error types
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod
import re
from html import escape
import requests
from flask import jsonify, current_app


# =============================================================================
# SANITIZATION HELPERS
# =============================================================================

def sanitize_error_message(message) -> str:
    """
    Sanitize R error messages before displaying to users.

    Handles cases where Plumber returns HTML stack traces on severe crashes.
    - Strips HTML tags to prevent layout breakage and XSS
    - Removes filesystem paths (security)
    - Escapes any remaining special characters

    Args:
        message: Raw error message from R API. Defensive against non-string
            inputs because Plumber serializes single-element character vectors
            as JSON arrays (e.g. ``["error text"]``), and `stop()` payloads
            can also be lists/dicts depending on the R-side handler.

    Returns:
        Sanitized message safe for display
    """
    if message is None:
        return ""

    if isinstance(message, str):
        text = message
    elif isinstance(message, (list, tuple)):
        # Plumber-default array wrapping: ["error"] / ["line1", "line2"]
        text = "\n".join(str(part) for part in message if part not in (None, ""))
    elif isinstance(message, dict):
        text = message.get("message") or message.get("error") or str(message)
        if not isinstance(text, str):
            text = str(text)
    else:
        text = str(message)

    if not text:
        return ""

    # Check if response looks like HTML (Plumber crash output)
    if "<html" in text.lower() or "<!doctype" in text.lower():
        return "An internal error occurred. Please try again."

    message = text

    # Strip any HTML tags
    clean = re.sub(r'<[^>]+>', '', message)

    # Remove filesystem paths (keep only filename)
    # Matches paths like /home/user/data/file.csv -> file.csv
    clean = re.sub(r'/[^\s]+/([^/\s]+\.\w+)', r'\1', clean)

    # Escape HTML entities for safe display
    clean = escape(clean)

    # Truncate if too long
    if len(clean) > 500:
        clean = clean[:497] + "..."

    return clean.strip()


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class APIErrorResponse:
    """Structured error response to send to frontend.

    Attributes:
        error_type: Machine-readable type (throttling, file_too_large, bad_gateway, api_error)
        message: Technical message for logging
        user_message: User-friendly message for display
        status_code: HTTP status code to return
        retry_after_seconds: Seconds to wait before retry (None if not applicable)
        details: Additional context (memory stats, etc.)
    """
    error_type: str
    message: str
    user_message: str
    status_code: int
    retry_after_seconds: Optional[int] = None
    details: Optional[Dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict for frontend."""
        result = {
            "error": True,
            "error_type": self.error_type,
            "message": self.message,
            "user_message": self.user_message,
            "status_code": self.status_code,
        }
        if self.retry_after_seconds is not None:
            result["retry_after_seconds"] = self.retry_after_seconds
        if self.details:
            result["details"] = self.details
        return result


# =============================================================================
# STRATEGY PATTERN: ERROR HANDLERS
# =============================================================================

class ErrorStrategy(ABC):
    """Base class for error handling strategies.

    Each strategy handles a specific type of API error.
    Subclasses must implement can_handle() and handle().
    """

    @abstractmethod
    def can_handle(self, response: requests.Response) -> bool:
        """Check if this strategy can handle the given response."""
        pass

    @abstractmethod
    def handle(self, response: requests.Response, endpoint: str) -> APIErrorResponse:
        """Handle the error and return a structured response."""
        pass


class FileTooLargeErrorStrategy(ErrorStrategy):
    """Handles 413 Payload Too Large errors.

    This is a PERMANENT failure - the request will NEVER succeed because
    it exceeds the server's total memory capacity. No retry is offered.
    """

    def can_handle(self, response: requests.Response) -> bool:
        return response.status_code == 413

    def handle(self, response: requests.Response, endpoint: str) -> APIErrorResponse:
        details = {}
        user_message = (
            "Your data is too large for this server to process. "
            "Please reduce your file size by filtering rows, removing columns, "
            "or splitting into smaller batches."
        )

        try:
            body = response.json()
            details = body.get("details", {})

            # Build contextual message with memory stats
            total_mb = details.get("total_mb")
            required_mb = details.get("required_mb")
            if total_mb and required_mb:
                user_message = (
                    f"Your data requires approximately {required_mb} MB to process, "
                    f"but this server has a maximum capacity of {total_mb} MB. "
                    f"Please reduce your file size by about {required_mb - total_mb} MB."
                )
        except (ValueError, KeyError):
            pass

        return APIErrorResponse(
            error_type="file_too_large",
            message=f"R API {endpoint} returned 413 - payload too large",
            user_message=user_message,
            status_code=413,
            retry_after_seconds=None,  # No retry - permanent failure
            details=details
        )


class ThrottlingErrorStrategy(ErrorStrategy):
    """Handles 503 Service Unavailable (throttling) errors.

    This is a TEMPORARY failure - the request could succeed later when
    system resources free up. A retry timer is provided.
    """

    def can_handle(self, response: requests.Response) -> bool:
        return response.status_code == 503

    def handle(self, response: requests.Response, endpoint: str) -> APIErrorResponse:
        retry_after = 60  # Default
        details = {}
        user_message = (
            "The server is temporarily busy processing other requests. "
            "Please wait and try again."
        )

        # Extract retry-after from header
        if "Retry-After" in response.headers:
            try:
                retry_after = int(response.headers["Retry-After"])
            except ValueError:
                pass

        try:
            body = response.json()
            details = body.get("details", {})

            # Override with body value if present
            if body.get("retry_after_seconds"):
                retry_after = body["retry_after_seconds"]

            # Build contextual message with memory stats
            available_mb = details.get("available_mb")
            required_mb = details.get("required_mb")
            if available_mb is not None and required_mb is not None:
                user_message = (
                    f"The server is temporarily busy. "
                    f"Your request needs {required_mb} MB but only {available_mb} MB is available. "
                    f"Please try again in {retry_after} seconds."
                )
        except (ValueError, KeyError):
            pass

        return APIErrorResponse(
            error_type="throttling",
            message=f"R API {endpoint} returned 503 - service throttled",
            user_message=user_message,
            status_code=503,
            retry_after_seconds=retry_after,
            details=details
        )


class BadGatewayErrorStrategy(ErrorStrategy):
    """Handles 502 Bad Gateway errors.

    Usually indicates the R API is unreachable or crashed.
    """

    def can_handle(self, response: requests.Response) -> bool:
        return response.status_code == 502

    def handle(self, response: requests.Response, endpoint: str) -> APIErrorResponse:
        return APIErrorResponse(
            error_type="bad_gateway",
            message=f"R API {endpoint} returned 502 - bad gateway",
            user_message=(
                "The analysis service is temporarily unreachable. "
                "Please try again in a few moments."
            ),
            status_code=502,
        )


class GenericServerErrorStrategy(ErrorStrategy):
    """Handles other 5xx server errors.

    Fallback for any server error not handled by more specific strategies.

    Phase 0 enhancement: Now extracts and displays the actual R error message
    (if available) instead of a generic "check your inputs" message.
    This surfaces helpful messages like "Column 'tmean' not found in dataset"
    that were previously buried in technical details.
    """

    def can_handle(self, response: requests.Response) -> bool:
        return 500 <= response.status_code < 600

    def handle(self, response: requests.Response, endpoint: str) -> APIErrorResponse:
        r_message = ""
        details = {}
        raw_body = response.text or ""

        try:
            body = response.json()
            if isinstance(body, dict):
                # R API returns the original error message in the "message" field
                r_message = body.get("message", "") or body.get("error", "")
                raw_details = body.get("details")
                if isinstance(raw_details, dict):
                    details = raw_details
            else:
                # Body was JSON but not an object (e.g. ["msg"] from plumber).
                r_message = body
        except (ValueError, KeyError):
            # Response is not valid JSON (possibly HTML crash page from Plumber).
            # Fall back to the raw text so we don't lose the message.
            r_message = raw_body

        # Sanitize the R message for safe display.  This also coerces lists /
        # dicts / etc. into a string defensively.
        safe_message = sanitize_error_message(r_message)

        # Use actual R message if available and safe, otherwise fallback to generic
        if safe_message:
            user_message = safe_message
        else:
            user_message = (
                "An error occurred while processing your request. "
                "Please check your inputs and try again."
            )

        # Always include a body preview in details so the central logger can
        # surface what R actually said even if sanitisation stripped it.
        details["response_preview"] = safe_message or (
            raw_body[:500] if raw_body else "No response body"
        )
        # Capture the unsanitised first 500 chars too — useful for diagnosing
        # plumber HTML crash pages that get reduced to a generic message.
        if raw_body:
            details["raw_body_snippet"] = raw_body[:500]

        # Log the raw body immediately so we never lose the message even if
        # downstream logging is misconfigured.  Status + endpoint provide
        # context; the body is truncated to keep logs readable.
        try:
            current_app.logger.error(
                "R API %s returned %s. Body: %s",
                endpoint,
                response.status_code,
                (raw_body[:500] + "...") if len(raw_body) > 500 else raw_body or "<empty>",
            )
        except RuntimeError:
            # Outside application context (e.g. tests)
            pass

        return APIErrorResponse(
            error_type="api_error",
            message=f"R API {endpoint} returned {response.status_code}",
            user_message=user_message,
            status_code=response.status_code,
            details=details
        )


# =============================================================================
# STRATEGY REGISTRY
# =============================================================================

class ErrorStrategyRegistry:
    """Registry of error handling strategies, checked in priority order.

    Strategies are checked in the order they were registered.
    The first strategy that can_handle() the response wins.
    """

    def __init__(self):
        self._strategies: List[ErrorStrategy] = []

    def register(self, strategy: ErrorStrategy) -> "ErrorStrategyRegistry":
        """Register a strategy. Returns self for chaining."""
        self._strategies.append(strategy)
        return self

    def get_handler(self, response: requests.Response) -> Optional[ErrorStrategy]:
        """Find the first strategy that can handle this response."""
        for strategy in self._strategies:
            if strategy.can_handle(response):
                return strategy
        return None


# =============================================================================
# GLOBAL REGISTRY (Singleton)
# =============================================================================

# Order matters: more specific handlers first (413 before generic 5xx)
_error_registry = ErrorStrategyRegistry()
_error_registry.register(FileTooLargeErrorStrategy())
_error_registry.register(ThrottlingErrorStrategy())
_error_registry.register(BadGatewayErrorStrategy())
_error_registry.register(GenericServerErrorStrategy())


def get_error_registry() -> ErrorStrategyRegistry:
    """Get the global error strategy registry."""
    return _error_registry


# =============================================================================
# PUBLIC API
# =============================================================================

def handle_api_response(response: requests.Response, endpoint: str):
    """Process an API response, returning success or structured error.

    Usage in routes:
        api_response = requests.post(url, json=payload)
        result = handle_api_response(api_response, endpoint="/temperature")
        if isinstance(result, APIErrorResponse):
            return make_error_response(result)
        # Continue with successful response...
        data = result.json()

    Args:
        response: The requests.Response from the R API call
        endpoint: The endpoint name for logging (e.g., "/temperature")

    Returns:
        - The original response if status_code == 200 (and no error in body)
        - An APIErrorResponse for any error

    Note:
        TRANSITIONAL: Some legacy R API endpoints return HTTP 200 with
        {"error": "message"} in the body (Gap 4 from research). This function
        detects and handles those cases until all endpoints are migrated to
        return proper HTTP status codes.
    """
    if response.status_code == 200:
        # Check for legacy 200-with-error pattern (Gap 4 from research)
        try:
            body = response.json()
            # Legacy pattern: {"error": "some message"} with no error_type.
            # Plumber may wrap single strings in a JSON array, so accept
            # lists/tuples too.
            error_value = body.get("error") if isinstance(body, dict) else None
            is_error = (
                isinstance(error_value, (str, list, tuple))
                and error_value
                and (not isinstance(body, dict) or "error_type" not in body)
            )
            if is_error:
                safe_message = sanitize_error_message(error_value)
                preview = (
                    error_value[:100] if isinstance(error_value, str)
                    else str(error_value)[:100]
                )
                try:
                    current_app.logger.warning(
                        "Legacy 200-with-error detected for %s: %s",
                        endpoint, preview
                    )
                except RuntimeError:
                    pass
                return APIErrorResponse(
                    error_type="legacy_validation_error",
                    message=f"R API {endpoint} returned 200 with error in body",
                    user_message=safe_message or preview,
                    status_code=400,  # Treat as 400 for frontend
                    details={"legacy_200_error": True}
                )
        except (ValueError, KeyError):
            pass
        # True success
        return response

    registry = get_error_registry()
    handler = registry.get_handler(response)

    if handler:
        error = handler.handle(response, endpoint)
        try:
            current_app.logger.error(
                "API error [%s] %s (status=%d, retry_after=%s) | user_message=%r | details=%r",
                error.error_type,
                error.message,
                error.status_code,
                error.retry_after_seconds,
                error.user_message,
                error.details,
            )
        except RuntimeError:
            # Outside application context (e.g., in tests)
            pass
        return error

    # Fallback for unexpected status codes (e.g., 4xx client errors).  Log the
    # raw body so the operator at least sees what the R API actually sent.
    try:
        current_app.logger.error(
            "Unhandled R API response from %s: status=%s, body=%s",
            endpoint,
            response.status_code,
            (response.text[:500] + "...") if len(response.text or "") > 500
            else (response.text or "<empty>"),
        )
    except RuntimeError:
        pass
    return APIErrorResponse(
        error_type="unknown",
        message=f"Unexpected response from R API {endpoint}: {response.status_code}",
        user_message="An unexpected error occurred. Please try again.",
        status_code=response.status_code,
        details={"raw_body_snippet": (response.text or "")[:500]},
    )


def make_error_response(error: APIErrorResponse):
    """Convert APIErrorResponse to Flask response tuple.

    Usage:
        if isinstance(result, APIErrorResponse):
            return make_error_response(result)

    Returns:
        Tuple of (response, status_code) for Flask
    """
    response = jsonify(error.to_dict())

    # Add Retry-After header for throttling errors
    if error.error_type == "throttling" and error.retry_after_seconds:
        response.headers["Retry-After"] = str(error.retry_after_seconds)

    return response, error.status_code
