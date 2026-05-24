import os
import yaml
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def load_app_config(config_path="config.yml"):
    """Load config from a YAML file and/or environment variables.

    Environment variables take precedence over YAML config values.
    This supports both local development (YAML file) and production (env vars).
    """
    # Load .env if present (optional, for local development)
    load_dotenv()

    config = {}

    # Attempt to read the YAML file
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f) or {}
            safe_config = {
                k: ("***" if "secret" in k.lower() or "password" in k.lower() else v)
                for k, v in config.items()
            }
            logger.debug("Loaded configuration from YAML (safe): %s", safe_config)
    except FileNotFoundError:
        logger.warning(f"{config_path} not found. Using environment variables only.")
    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML: {e}")

    # Environment variables override YAML config
    # Map: ENV_VAR_NAME -> (yaml_key, default_value)
    env_mappings = {
        # Core settings
        "SECRET_KEY": ("secret_key", None),
        "SHOW_SYSTEM_HEALTH_NOTICE": ("show_system_health_notice", "false"),
        "DEBUG_MODE": ("debug_mode", "false"),
        "DUMMY_MODE": ("dummy_mode", "false"),
        "RUN_MIGRATIONS": ("run_migrations", "false"),
        "ENABLE_FULL_UI": ("enable_full_ui", "true"),

        # API endpoints
        "API_URL": ("API_URL", None),

        # Database
        "SQL_HOST": ("host", "localhost"),
        "SQL_PORT": ("port", 5432),
        "SQL_DBNAME": ("dbname", "app_db"),
        "SQL_USER": ("user", "postgres"),
        "SQL_PASSWORD": ("password", None),

        # Keycloak
        "KEYCLOAK_URL": ("keycloak_url", None),
        "REALM_NAME": ("realm_name", None),
        "CLIENT_ID": ("client_id", None),
        "CLIENT_SECRET": ("client_secret", None),
        "REDIRECT_URI": ("redirect_uri", None),

        # Paths
        "TEMPORARY_DIRECTORY_PATH": ("temporary_directory_path", None),
    }

    for env_var, (yaml_key, default) in env_mappings.items():
        env_value = os.getenv(env_var)
        if env_value is not None:
            config[yaml_key] = env_value
        elif yaml_key not in config and default is not None:
            config[yaml_key] = default

    return config
