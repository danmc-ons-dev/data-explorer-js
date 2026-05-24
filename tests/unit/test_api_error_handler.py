"""
Unit tests for api_error_handler.py

Tests the Strategy Pattern implementation for handling R API error responses.
"""
import pytest
from unittest.mock import Mock, MagicMock
import json

from data_explorer.utils.api_error_handler import (
    APIErrorResponse,
    FileTooLargeErrorStrategy,
    ThrottlingErrorStrategy,
    BadGatewayErrorStrategy,
    GenericServerErrorStrategy,
    ErrorStrategyRegistry,
    get_error_registry,
    handle_api_response,
    make_error_response,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_response():
    """Create a mock requests.Response object."""
    def _create_response(status_code, json_body=None, text="", headers=None):
        response = Mock()
        response.status_code = status_code
        # Fix precedence: text takes priority, then JSON body serialization
        if text:
            response.text = text
        elif json_body is not None:
            response.text = json.dumps(json_body)
        else:
            response.text = ""
        response.headers = headers or {}
        if json_body is not None:
            response.json.return_value = json_body
        else:
            response.json.side_effect = ValueError("No JSON body")
        return response
    return _create_response


# =============================================================================
# TESTS: APIErrorResponse
# =============================================================================

class TestAPIErrorResponse:
    """Tests for the APIErrorResponse dataclass."""

    def test_to_dict_basic(self):
        """Test basic conversion to dict."""
        error = APIErrorResponse(
            error_type="throttling",
            message="Server busy",
            user_message="Please wait and try again.",
            status_code=503,
        )
        result = error.to_dict()

        assert result["error"] is True
        assert result["error_type"] == "throttling"
        assert result["message"] == "Server busy"
        assert result["user_message"] == "Please wait and try again."
        assert result["status_code"] == 503
        assert "retry_after_seconds" not in result

    def test_to_dict_with_retry_after(self):
        """Test conversion includes retry_after_seconds when set."""
        error = APIErrorResponse(
            error_type="throttling",
            message="Server busy",
            user_message="Please wait.",
            status_code=503,
            retry_after_seconds=60,
        )
        result = error.to_dict()

        assert result["retry_after_seconds"] == 60

    def test_to_dict_with_details(self):
        """Test conversion includes details when set."""
        error = APIErrorResponse(
            error_type="throttling",
            message="Server busy",
            user_message="Please wait.",
            status_code=503,
            details={"available_mb": 500, "required_mb": 1000},
        )
        result = error.to_dict()

        assert result["details"]["available_mb"] == 500
        assert result["details"]["required_mb"] == 1000


# =============================================================================
# TESTS: FileTooLargeErrorStrategy
# =============================================================================

class TestFileTooLargeErrorStrategy:
    """Tests for 413 Payload Too Large handling."""

    def test_can_handle_413(self, mock_response):
        """Strategy handles 413 responses."""
        strategy = FileTooLargeErrorStrategy()
        response = mock_response(413)
        assert strategy.can_handle(response) is True

    def test_can_handle_not_413(self, mock_response):
        """Strategy does not handle non-413 responses."""
        strategy = FileTooLargeErrorStrategy()
        for code in [200, 400, 500, 502, 503]:
            response = mock_response(code)
            assert strategy.can_handle(response) is False

    def test_handle_with_memory_details(self, mock_response):
        """Test handling with memory stats in response body."""
        strategy = FileTooLargeErrorStrategy()
        response = mock_response(
            413,
            json_body={
                "error": "Request too large",
                "reason": "file_too_large",
                "details": {
                    "total_mb": 4000,
                    "required_mb": 5000,
                }
            }
        )

        result = strategy.handle(response, "/temperature")

        assert result.error_type == "file_too_large"
        assert result.status_code == 413
        assert result.retry_after_seconds is None  # No retry for permanent failure
        assert "5000" in result.user_message  # Required MB mentioned
        assert "4000" in result.user_message  # Total MB mentioned

    def test_handle_without_memory_details(self, mock_response):
        """Test handling when response has no memory details."""
        strategy = FileTooLargeErrorStrategy()
        response = mock_response(413, text="Payload too large")

        result = strategy.handle(response, "/temperature")

        assert result.error_type == "file_too_large"
        assert result.status_code == 413
        assert "reduce your file size" in result.user_message.lower()


# =============================================================================
# TESTS: ThrottlingErrorStrategy
# =============================================================================

class TestThrottlingErrorStrategy:
    """Tests for 503 Service Unavailable (throttling) handling."""

    def test_can_handle_503(self, mock_response):
        """Strategy handles 503 responses."""
        strategy = ThrottlingErrorStrategy()
        response = mock_response(503)
        assert strategy.can_handle(response) is True

    def test_can_handle_not_503(self, mock_response):
        """Strategy does not handle non-503 responses."""
        strategy = ThrottlingErrorStrategy()
        for code in [200, 400, 413, 500, 502]:
            response = mock_response(code)
            assert strategy.can_handle(response) is False

    def test_handle_with_retry_header(self, mock_response):
        """Test handling extracts Retry-After header."""
        strategy = ThrottlingErrorStrategy()
        response = mock_response(
            503,
            json_body={"error": "Service unavailable"},
            headers={"Retry-After": "120"}
        )

        result = strategy.handle(response, "/temperature")

        assert result.error_type == "throttling"
        assert result.status_code == 503
        assert result.retry_after_seconds == 120

    def test_handle_with_body_retry_override(self, mock_response):
        """Test body retry_after_seconds overrides header."""
        strategy = ThrottlingErrorStrategy()
        response = mock_response(
            503,
            json_body={
                "error": "Service unavailable",
                "retry_after_seconds": 90,
            },
            headers={"Retry-After": "60"}
        )

        result = strategy.handle(response, "/temperature")

        assert result.retry_after_seconds == 90  # Body value wins

    def test_handle_with_memory_details(self, mock_response):
        """Test handling includes memory stats in user message."""
        strategy = ThrottlingErrorStrategy()
        response = mock_response(
            503,
            json_body={
                "error": "Service unavailable",
                "retry_after_seconds": 60,
                "details": {
                    "available_mb": 500,
                    "required_mb": 1500,
                }
            }
        )

        result = strategy.handle(response, "/temperature")

        assert "1500" in result.user_message  # Required MB
        assert "500" in result.user_message   # Available MB
        assert "60" in result.user_message    # Retry seconds

    def test_handle_default_retry(self, mock_response):
        """Test default retry time when not specified."""
        strategy = ThrottlingErrorStrategy()
        response = mock_response(503, text="Server busy")

        result = strategy.handle(response, "/temperature")

        assert result.retry_after_seconds == 60  # Default


# =============================================================================
# TESTS: BadGatewayErrorStrategy
# =============================================================================

class TestBadGatewayErrorStrategy:
    """Tests for 502 Bad Gateway handling."""

    def test_can_handle_502(self, mock_response):
        """Strategy handles 502 responses."""
        strategy = BadGatewayErrorStrategy()
        response = mock_response(502)
        assert strategy.can_handle(response) is True

    def test_can_handle_not_502(self, mock_response):
        """Strategy does not handle non-502 responses."""
        strategy = BadGatewayErrorStrategy()
        for code in [200, 400, 413, 500, 503]:
            response = mock_response(code)
            assert strategy.can_handle(response) is False

    def test_handle_returns_correct_response(self, mock_response):
        """Test handling returns appropriate error response."""
        strategy = BadGatewayErrorStrategy()
        response = mock_response(502, text="Bad Gateway")

        result = strategy.handle(response, "/temperature")

        assert result.error_type == "bad_gateway"
        assert result.status_code == 502
        assert "unreachable" in result.user_message.lower()


# =============================================================================
# TESTS: GenericServerErrorStrategy
# =============================================================================

class TestGenericServerErrorStrategy:
    """Tests for generic 5xx error handling."""

    def test_can_handle_5xx(self, mock_response):
        """Strategy handles any 5xx response."""
        strategy = GenericServerErrorStrategy()
        for code in [500, 501, 504, 505, 599]:
            response = mock_response(code)
            assert strategy.can_handle(response) is True

    def test_can_handle_not_5xx(self, mock_response):
        """Strategy does not handle non-5xx responses."""
        strategy = GenericServerErrorStrategy()
        for code in [200, 301, 400, 404]:
            response = mock_response(code)
            assert strategy.can_handle(response) is False

    def test_handle_includes_response_preview(self, mock_response):
        """Test handling includes response text preview."""
        strategy = GenericServerErrorStrategy()
        response = mock_response(500, text="Internal Server Error: something broke")

        result = strategy.handle(response, "/temperature")

        assert result.error_type == "api_error"
        assert result.status_code == 500
        assert "Internal Server Error" in result.details.get("response_preview", "")


# =============================================================================
# TESTS: ErrorStrategyRegistry
# =============================================================================

class TestErrorStrategyRegistry:
    """Tests for the strategy registry."""

    def test_get_handler_returns_first_matching(self, mock_response):
        """Registry returns first strategy that can handle."""
        registry = ErrorStrategyRegistry()
        registry.register(FileTooLargeErrorStrategy())
        registry.register(ThrottlingErrorStrategy())
        registry.register(GenericServerErrorStrategy())

        response = mock_response(503)
        handler = registry.get_handler(response)

        assert isinstance(handler, ThrottlingErrorStrategy)

    def test_get_handler_priority_order(self, mock_response):
        """More specific handlers are checked before generic."""
        registry = ErrorStrategyRegistry()
        # Register generic first
        registry.register(GenericServerErrorStrategy())
        # Then register specific
        registry.register(ThrottlingErrorStrategy())

        # 503 should match generic first since it was registered first
        response = mock_response(503)
        handler = registry.get_handler(response)

        # Generic handles all 5xx, so it wins
        assert isinstance(handler, GenericServerErrorStrategy)

    def test_get_handler_none_when_no_match(self, mock_response):
        """Registry returns None when no strategy matches."""
        registry = ErrorStrategyRegistry()
        registry.register(ThrottlingErrorStrategy())

        response = mock_response(404)  # No 404 handler
        handler = registry.get_handler(response)

        assert handler is None

    def test_global_registry_has_correct_order(self, mock_response):
        """Global registry has strategies in correct priority order."""
        registry = get_error_registry()

        # 413 should get FileTooLarge, not Generic5xx
        response_413 = mock_response(413)
        handler_413 = registry.get_handler(response_413)
        assert isinstance(handler_413, FileTooLargeErrorStrategy)

        # 503 should get Throttling, not Generic5xx
        response_503 = mock_response(503)
        handler_503 = registry.get_handler(response_503)
        assert isinstance(handler_503, ThrottlingErrorStrategy)

        # 502 should get BadGateway, not Generic5xx
        response_502 = mock_response(502)
        handler_502 = registry.get_handler(response_502)
        assert isinstance(handler_502, BadGatewayErrorStrategy)

        # 500 should get Generic5xx
        response_500 = mock_response(500)
        handler_500 = registry.get_handler(response_500)
        assert isinstance(handler_500, GenericServerErrorStrategy)


# =============================================================================
# TESTS: handle_api_response (Integration)
# =============================================================================

class TestHandleApiResponse:
    """Integration tests for the main handle_api_response function."""

    def test_success_returns_response(self, mock_response):
        """Successful response (200) returns original response."""
        response = mock_response(200, json_body={"data": "success"})

        result = handle_api_response(response, "/temperature")

        assert result is response

    def test_503_returns_throttling_error(self, mock_response):
        """503 response returns throttling APIErrorResponse."""
        response = mock_response(
            503,
            json_body={
                "error": "Service unavailable",
                "retry_after_seconds": 60,
                "details": {"available_mb": 500, "required_mb": 1000}
            }
        )

        result = handle_api_response(response, "/temperature")

        assert isinstance(result, APIErrorResponse)
        assert result.error_type == "throttling"
        assert result.retry_after_seconds == 60

    def test_413_returns_file_too_large_error(self, mock_response):
        """413 response returns file_too_large APIErrorResponse."""
        response = mock_response(
            413,
            json_body={
                "error": "Request too large",
                "details": {"total_mb": 4000, "required_mb": 5000}
            }
        )

        result = handle_api_response(response, "/temperature")

        assert isinstance(result, APIErrorResponse)
        assert result.error_type == "file_too_large"
        assert result.retry_after_seconds is None

    def test_unknown_status_returns_fallback(self, mock_response):
        """Unknown status codes return generic APIErrorResponse."""
        response = mock_response(418, text="I'm a teapot")

        result = handle_api_response(response, "/temperature")

        assert isinstance(result, APIErrorResponse)
        assert result.error_type == "unknown"
        assert result.status_code == 418


# =============================================================================
# TESTS: make_error_response
# =============================================================================

class TestMakeErrorResponse:
    """Tests for Flask response generation."""

    def test_returns_tuple(self, app):
        """Returns (response, status_code) tuple."""
        error = APIErrorResponse(
            error_type="throttling",
            message="Server busy",
            user_message="Please wait.",
            status_code=503,
            retry_after_seconds=60,
        )

        with app.app_context():
            response, status_code = make_error_response(error)

        assert status_code == 503

    def test_throttling_sets_retry_header(self, app):
        """Throttling errors set Retry-After header."""
        error = APIErrorResponse(
            error_type="throttling",
            message="Server busy",
            user_message="Please wait.",
            status_code=503,
            retry_after_seconds=120,
        )

        with app.app_context():
            response, status_code = make_error_response(error)

        assert response.headers.get("Retry-After") == "120"

    def test_non_throttling_no_retry_header(self, app):
        """Non-throttling errors don't set Retry-After header."""
        error = APIErrorResponse(
            error_type="file_too_large",
            message="File too large",
            user_message="Reduce file size.",
            status_code=413,
        )

        with app.app_context():
            response, status_code = make_error_response(error)

        assert "Retry-After" not in response.headers


# =============================================================================
# TESTS: Phase 0 - Sanitization and R Message Pass-through
# =============================================================================

class TestSanitizeErrorMessage:
    """Tests for the sanitize_error_message helper function."""

    def test_empty_message_returns_empty(self):
        """Empty or None messages return empty string."""
        from data_explorer.utils.api_error_handler import sanitize_error_message

        assert sanitize_error_message("") == ""
        assert sanitize_error_message(None) == ""

    def test_simple_message_passes_through(self):
        """Simple R error messages pass through unchanged."""
        from data_explorer.utils.api_error_handler import sanitize_error_message

        result = sanitize_error_message("Column 'tmean' not found in dataset")
        assert "Column" in result
        assert "tmean" in result

    def test_html_content_returns_generic(self):
        """HTML responses from Plumber crashes return generic message."""
        from data_explorer.utils.api_error_handler import sanitize_error_message

        html_content = "<html><body>Error: stack trace here</body></html>"
        result = sanitize_error_message(html_content)
        assert result == "An internal error occurred. Please try again."

        # Also test with doctype
        result2 = sanitize_error_message("<!DOCTYPE html><html>...")
        assert result2 == "An internal error occurred. Please try again."

    def test_strips_html_tags(self):
        """HTML tags in messages are stripped."""
        from data_explorer.utils.api_error_handler import sanitize_error_message

        result = sanitize_error_message("Error: <b>bold</b> text")
        assert "<b>" not in result
        assert "</b>" not in result
        assert "bold" in result

    def test_strips_filesystem_paths(self):
        """Filesystem paths are sanitized to just filename."""
        from data_explorer.utils.api_error_handler import sanitize_error_message

        result = sanitize_error_message(
            "Error reading /home/api/uploads/user123/data.csv"
        )
        assert "/home/api/uploads" not in result
        assert "data.csv" in result

    def test_truncates_long_messages(self):
        """Messages over 500 chars are truncated."""
        from data_explorer.utils.api_error_handler import sanitize_error_message

        long_message = "A" * 600
        result = sanitize_error_message(long_message)
        assert len(result) <= 500
        assert result.endswith("...")


class TestGenericServerErrorStrategyPhase0:
    """Tests for Phase 0 enhancement: R message pass-through."""

    def test_shows_actual_r_message(self, mock_response):
        """GenericServerErrorStrategy now shows actual R error message."""
        strategy = GenericServerErrorStrategy()
        response = mock_response(
            500,
            json_body={
                "error": "Internal server error",
                "path": "/temperature",
                "message": "Column 'death_count' not found in dataset"
            }
        )

        result = strategy.handle(response, "/temperature")

        # User message should contain the actual R error, not generic text
        assert "death_count" in result.user_message
        assert "Column" in result.user_message
        # Should NOT be the old generic message
        assert "check your inputs" not in result.user_message.lower()

    def test_falls_back_to_generic_when_no_message(self, mock_response):
        """Falls back to generic message when R message not available."""
        strategy = GenericServerErrorStrategy()
        response = mock_response(500, text="Something went wrong")

        result = strategy.handle(response, "/temperature")

        # Should fall back to generic message
        assert "check your inputs" in result.user_message.lower() or \
               "error occurred" in result.user_message.lower()

    def test_sanitizes_r_message(self, mock_response):
        """R messages are sanitized before display."""
        strategy = GenericServerErrorStrategy()
        response = mock_response(
            500,
            json_body={
                "message": "Error reading /home/api/secret/data.csv"
            }
        )

        result = strategy.handle(response, "/temperature")

        # Path should be sanitized
        assert "/home/api/secret" not in result.user_message
        assert "data.csv" in result.user_message


class TestLegacy200WithError:
    """Tests for transitional handling of 200-with-error responses."""

    def test_detects_legacy_200_error(self, mock_response):
        """Detects and handles legacy 200 responses with error in body."""
        response = mock_response(
            200,
            json_body={"error": "No valid geospatial file found in ZIP"}
        )

        result = handle_api_response(response, "/diarrhea")

        assert isinstance(result, APIErrorResponse)
        assert result.error_type == "legacy_validation_error"
        assert result.status_code == 400  # Treated as 400 for frontend
        assert "geospatial" in result.user_message.lower()
        assert result.details.get("legacy_200_error") is True

    def test_ignores_true_success(self, mock_response):
        """True success responses (no error key) pass through."""
        response = mock_response(
            200,
            json_body={"data": [1, 2, 3], "status": "success"}
        )

        result = handle_api_response(response, "/temperature")

        # Should return the original response, not APIErrorResponse
        assert result is response

    def test_ignores_structured_error_responses(self, mock_response):
        """Ignores responses with error_type (not legacy pattern)."""
        response = mock_response(
            200,
            json_body={
                "error": True,  # Boolean, not string
                "error_type": "throttling",
                "message": "..."
            }
        )

        result = handle_api_response(response, "/temperature")

        # Should return original response (error is boolean, not string)
        assert result is response
