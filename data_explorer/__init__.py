import datetime
import json
import logging
import os
import secrets
from threading import Thread
from pathlib import Path

from flask import Flask
from flask_session import Session

from data_explorer.config import load_app_config
from data_explorer.utils.cleanup import cleanup_temp_directories


def get_component_versions():
    """
    Get component version information from environment variables.
    Returns a list of component dicts with name, version, and sha.
    Only includes components that have at least one value set.
    """
    components = [
        ('CLIMATEHEALTH', 'Climate Health'),
        ('DATA_EXPLORER', 'Data Explorer'),
    ]

    result = []
    for env_prefix, display_name in components:
        version = os.environ.get(f"{env_prefix}_VERSION")
        sha = os.environ.get(f"{env_prefix}_SHA")

        # Only include if at least one value is set and not 'local'
        if (version and version != 'local-dev') or (sha and sha != 'local'):
            result.append({
                'name': display_name,
                'version': version or 'N/A',
                'sha': sha[:7] if sha and len(sha) > 7 else (sha or 'N/A'),
            })

    # Add build metadata
    build_number = os.environ.get('BUILD_NUMBER')
    build_timestamp = os.environ.get('BUILD_TIMESTAMP')

    build_meta = {}
    if build_number and build_number != 'local':
        build_meta['build_number'] = build_number
    if build_timestamp and build_timestamp != 'local':
        build_meta['build_timestamp'] = build_timestamp

    return result, build_meta


def generate_startup_log(app_config):
    """
    Generate a structured JSON log entry for startup configuration.
    Explicit manual redaction is used for maximum security.
    Designed for Elasticsearch ingestion.
    """
    component_versions, build_meta = get_component_versions()

    # Safe session lifetime calculation
    session_lifetime = app_config.get("PERMANENT_SESSION_LIFETIME")
    lifetime_minutes = None
    if session_lifetime:
        try:
            # Handle timedelta objects
            lifetime_minutes = session_lifetime.total_seconds() / 60
        except AttributeError:
            # Handle integers/floats
            lifetime_minutes = session_lifetime

    # Explicitly build the dict to ensure no secrets accidentally slip in
    startup_log = {
        "event": "application_startup",
        # Use timezone-aware UTC (Python 3.12+ compatible)
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "log_type": "structured_config",
        "application": {
            "name": "data_explorer",
            "debug_mode": app_config.get("DEBUG_MODE", False),
            "dummy_mode": app_config.get("DUMMY_MODE", False),
        },
        "api_endpoints": {
            "api_url": app_config.get("API_URL"),
        },
        "database": {
            "host": app_config.get("SQL_HOST"),
            "port": app_config.get("SQL_PORT"),
            "dbname": app_config.get("SQL_DBNAME"),
            "user": app_config.get("SQL_USER"),
            "password": "***REDACTED***",
        },
        "session": {
            "type": app_config.get("SESSION_TYPE"),
            "cookie_secure": app_config.get("SESSION_COOKIE_SECURE"),
            "cookie_httponly": app_config.get("SESSION_COOKIE_HTTPONLY"),
            "cookie_samesite": app_config.get("SESSION_COOKIE_SAMESITE"),
            "permanent": app_config.get("SESSION_PERMANENT"),
            "lifetime_minutes": lifetime_minutes,
        },
        "keycloak": {
            "url": app_config.get("KEYCLOAK_URL"),
            "realm_name": app_config.get("REALM_NAME"),
            "client_id": app_config.get("CLIENT_ID"),
            "client_secret": "***REDACTED***",
            "redirect_uri": app_config.get("REDIRECT_URI"),
        },
        "paths": {
            "temporary_directory": app_config.get("TEMPORARY_DIRECTORY_PATH"),
        },
        "version_info": {
            "components": component_versions,
            "build": build_meta,
        }
    }

    return startup_log


def create_app():
    """Application factory for the data_explorer Flask app."""

    # 1. Create the Flask app
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # 2. Load configuration from config.yml (and possibly environment variables)
    config = load_app_config()

    #    Log the loaded configuration (sensitive values redacted)
    safe_config = {
        k: ("***" if "secret" in k or "password" in k else v)
        for k, v in config.items()
    }
    app.logger.debug("App configuration (safe): %s", safe_config)


    # 3. Update Flask config based on config.yml
    #    (Coerce some "true"/"false" strings into booleans below)
    app.config.update(
        # Values from config.yml
        RUN_MIGRATIONS=(config.get("run_migrations", "false").lower() == "true"),
        DEBUG_MODE=(config.get("debug_mode", "false").lower() == "true"),
        DUMMY_MODE=(config.get("dummy_mode", "false").lower() == "true"),
        ENABLE_FULL_UI=(config.get("enable_full_ui", "false").lower() == "true"),
        SHOW_SYSTEM_HEALTH_NOTICE=config.get("show_system_health_notice", "false"),
        SQL_HOST=config.get("host", "localhost"),
        SQL_DBNAME=config.get("dbname", "app_db"),
        SQL_USER=config.get("user", "postgres"),
        SQL_PASSWORD=config.get("password", "password"),
        SQL_PORT=config.get("port", 5432),
        SECRET_KEY=config.get("secret_key", secrets.token_hex(32)),
        API_URL=config.get("API_URL"),
        KEYCLOAK_URL=config.get("keycloak_url"),
        TEMPORARY_DIRECTORY_PATH=config.get("temporary_directory_path"),
        REALM_NAME=config.get("realm_name"),
        CLIENT_ID=config.get("client_id"),
        CLIENT_SECRET=config.get("client_secret"),
        REDIRECT_URI=config.get("redirect_uri"),
        # Session config
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_TYPE="filesystem",
        SESSION_PERMANENT=False,
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=datetime.timedelta(minutes=30),
    )

    # Handle issue of SSL verification for keycloak requests
    debug_mode = config.get("debug_mode", "false").lower()
    if debug_mode == "true":
        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

    # Set the Flask app's 'debug' property from debug_mode:
    app.debug = app.config["DEBUG_MODE"]

    # 4. Initialize Flask extensions (e.g., Session, SQLAlchemy, etc.)
    Session(app)
    # db.init_app(app)  # if using Flask-SQLAlchemy

    # 5. Register Blueprints
    from data_explorer.routes.auth_routes import auth_bp
    from data_explorer.routes.main_routes import main_bp
    from data_explorer.routes.indicator_routes import indicator_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(indicator_bp)

    # 6. Setup logging
    logging.basicConfig(level=logging.DEBUG if app.debug else logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    # 6b. Output structured startup log for Elasticsearch
    # Note: We use prefix "JSON_STARTUP_CONFIG:" to help Filebeat/Logstash
    # identify this line specifically for JSON parsing
    startup_log = generate_startup_log(app.config)
    app.logger.info("JSON_STARTUP_CONFIG: %s", json.dumps(startup_log, default=str))

    # 7. Initialise temporary directory cleanup
    #    This will run in a separate thread to clean up temporary directories
    # temp_dir_path = app.config.get("TEMPORARY_DIRECTORY_PATH")
    # if temp_dir_path:
    #     cleanup_config = [Path(temp_dir_path), 1800, 900]
    #     t = Thread(target=cleanup_temp_directories, args=cleanup_config)
    #     t.daemon = True
    #     t.start()

    # else:
    #    app.logger.warning("Temporary directory path not set. Skipping temp directory cleanup.")

    # 8. Register context processor for build info
    @app.context_processor
    def inject_build_info():
        component_versions, build_meta = get_component_versions()
        return dict(
            component_versions=component_versions,
            build_meta=build_meta
        )

    app.logger.info("Flask app created and configured successfully.")

    return app

