"""Health check utilities for monitoring R API status."""

import time
import logging
import requests
import urllib3
from typing import Optional, Dict, Any, Union
from threading import Lock

# Suppress InsecureRequestWarning for internal pod-to-pod/localhost traffic
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


def _unwrap_r_value(value: Any) -> Any:
    """
    R Plumber serializes single values as arrays: ["healthy"] instead of "healthy".
    This helper extracts the first element if value is a list with one item.
    """
    if isinstance(value, list) and len(value) == 1:
        return value[0]
    return value


class HealthCheckCache:
    """Thread-safe cache for health check results with TTL."""

    def __init__(self, ttl_seconds: int = 60):  # 60 seconds for health checks
        self._cache: Optional[Dict[str, Any]] = None
        self._cache_time: float = 0
        self._ttl = ttl_seconds
        self._lock = Lock()

    def get(self) -> Optional[Dict[str, Any]]:
        """Get cached value if not expired."""
        with self._lock:
            if self._cache is None:
                return None
            if time.time() - self._cache_time > self._ttl:
                return None
            return self._cache.copy()

    def set(self, value: Dict[str, Any]) -> None:
        """Set cache value with current timestamp."""
        with self._lock:
            self._cache = value.copy()
            self._cache_time = time.time()

    def invalidate(self) -> None:
        """Clear the cache."""
        with self._lock:
            self._cache = None
            self._cache_time = 0


# Global cache instance (60 second TTL for better outage responsiveness)
_health_cache = HealthCheckCache(ttl_seconds=60)


def check_r_api_health(api_url: str, timeout: int = 10) -> Dict[str, Any]:
    """
    Check the health of the R API.

    Args:
        api_url: Base URL of the R API (e.g., "http://localhost:8000")
        timeout: Request timeout in seconds

    Returns:
        Dict with health status information
    """
    # Check cache first
    cached = _health_cache.get()
    if cached is not None:
        cached['from_cache'] = True
        return cached

    # Normalize URL
    if api_url and api_url.endswith('/'):
        api_url = api_url[:-1]

    # Handle missing API URL
    if not api_url:
        result = {
            'reachable': False,
            'status': 'unconfigured',
            'message': 'R API URL not configured',
            'details': None,
            'checked_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'from_cache': False,
        }
        _health_cache.set(result)
        return result

    health_url = f"{api_url}/health"

    result = {
        'reachable': False,
        'status': 'unknown',
        'message': '',
        'details': None,
        'checked_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'from_cache': False,
    }

    try:
        response = requests.get(
            health_url,
            timeout=timeout,
            verify=False  # Internal pod-to-pod/localhost traffic
        )

        if response.status_code == 200:
            health_data = response.json()
            result['reachable'] = True
            # R Plumber returns arrays for single values, so unwrap them
            result['status'] = _unwrap_r_value(health_data.get('status', 'unknown'))
            result['message'] = 'R API is operational'
            result['details'] = health_data.get('checks', {})

            # Extract package version if available
            pkg_check = health_data.get('checks', {}).get('package', {})
            pkg_version = _unwrap_r_value(pkg_check.get('version'))
            if pkg_version:
                result['package_version'] = pkg_version

            # Extract memory info (sanitized for UI)
            memory_check = health_data.get('checks', {}).get('memory', {})

            # Match the R 'info_available' flag
            info_available = _unwrap_r_value(memory_check.get('info_available'))
            if info_available:
                used = _unwrap_r_value(memory_check.get('used_mb'))
                limit = _unwrap_r_value(memory_check.get('limit_mb'))
                percent = _unwrap_r_value(memory_check.get('percent_used'))

                result['memory'] = {
                    'used_mb': used,
                    # Ensure UI doesn't break on None values
                    'limit_mb': limit if limit is not None else "N/A",
                    'percent_used': percent if percent is not None else "N/A",
                }

        elif response.status_code == 503:
            # API is reachable but unhealthy - still parse JSON for error details
            result['reachable'] = True
            result['status'] = 'unhealthy'
            result['message'] = 'R API reports unhealthy status'
            try:
                result['details'] = response.json().get('checks', {})
            except ValueError:
                pass

        else:
            result['reachable'] = True
            result['status'] = 'error'
            result['message'] = f'R API returned status {response.status_code}'

    except requests.exceptions.Timeout:
        result['status'] = 'timeout'
        result['message'] = 'R API request timed out'
        logger.warning("Health check timed out for %s", health_url)

    except requests.exceptions.ConnectionError as e:
        result['status'] = 'unreachable'
        result['message'] = 'Cannot connect to R API'
        logger.warning("Health check connection error for %s: %s", health_url, str(e))

    except requests.exceptions.RequestException as e:
        result['status'] = 'error'
        result['message'] = f'Health check failed: {str(e)}'
        logger.error("Health check error for %s: %s", health_url, str(e))

    except ValueError as e:
        result['reachable'] = True
        result['status'] = 'error'
        result['message'] = 'Invalid JSON response from R API'
        logger.error("Health check JSON parse error: %s", str(e))

    # Cache the result
    _health_cache.set(result)

    return result


def get_health_status_display(health_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert health check result to display-friendly format.

    Returns:
        Dict with display properties (color, icon, text, css_class)
    """
    status = health_result.get('status', 'unknown')

    status_map = {
        'healthy': {
            'color': 'green',
            'css_class': 'health-status-healthy',
            'icon': '&#10003;',  # checkmark
            'text': 'Operational',
        },
        'degraded': {
            'color': 'orange',
            'css_class': 'health-status-degraded',
            'icon': '&#9888;',  # warning
            'text': 'Degraded',
        },
        'unhealthy': {
            'color': 'red',
            'css_class': 'health-status-unhealthy',
            'icon': '&#10007;',  # x mark
            'text': 'Unhealthy',
        },
        'unreachable': {
            'color': 'red',
            'css_class': 'health-status-unreachable',
            'icon': '&#10007;',  # x mark
            'text': 'Unreachable',
        },
        'timeout': {
            'color': 'red',
            'css_class': 'health-status-timeout',
            'icon': '&#8987;',  # hourglass
            'text': 'Timeout',
        },
        'error': {
            'color': 'red',
            'css_class': 'health-status-error',
            'icon': '&#10007;',  # x mark
            'text': 'Error',
        },
        'unconfigured': {
            'color': 'gray',
            'css_class': 'health-status-unconfigured',
            'icon': '?',
            'text': 'Not Configured',
        },
        'unknown': {
            'color': 'gray',
            'css_class': 'health-status-unknown',
            'icon': '?',
            'text': 'Unknown',
        },
    }

    display = status_map.get(status, status_map['unknown']).copy()
    display['status'] = status
    display['message'] = health_result.get('message', '')
    display['from_cache'] = health_result.get('from_cache', False)
    display['checked_at'] = health_result.get('checked_at', '')
    display['package_version'] = health_result.get('package_version')
    display['memory'] = health_result.get('memory')

    return display
