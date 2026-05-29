import json
from pathlib import Path

from flask import Blueprint, render_template, current_app, request, abort, send_from_directory

from data_explorer.services.search_service import search_entries

from data_explorer.utils.health_check import check_r_api_health, get_health_status_display

# Create the blueprint
main_bp = Blueprint("main_bp", __name__)


# Define routes for this blueprint
@main_bp.route("/")
def index():
    return render_template("index.html")


@main_bp.route("/about")
def about():
    """About page with R API health status display and team data."""
    # Read team data from json and pass to template
    team_data = {"users": []}
    team_data_path = Path(current_app.root_path) / \
        "static" / "data" / "csv" / "team_data.json"
    if team_data_path.exists():
        team_data = json.loads(team_data_path.read_text(encoding="utf-8"))

    # Get R API health status (cached for 60 seconds)
    api_url = current_app.config.get("API_URL", "http://127.0.0.1:8000")

    show_health_status = current_app.config.get(
        "SHOW_SYSTEM_HEALTH_NOTICE", "false")
    health_result = check_r_api_health(api_url)
    health_display = get_health_status_display(health_result)

    return render_template("about.html", r_api_health=health_display, team_data=team_data, show_health_status=show_health_status)


@main_bp.route("/resources")
def resources():
    return render_template("resources.html")


@main_bp.route("/faqs")
def faqs():
    return render_template("faqs.html")


@main_bp.route("/terms")
def terms():
    return render_template("terms.html")


@main_bp.route("/search")
def search():
    query = request.args.get("q", "").strip()
    results = search_entries(query) if query else []
    return render_template("search.html", query=query, results=results)


@main_bp.route("/r_package")
def r_package():
    return render_template("r_package.html")


@main_bp.route("/coming_soon")
def coming_soon():
    return render_template("coming_soon.html")


@main_bp.route("/version")
def system_version():
    """
    Public endpoint to expose system version information.
    Proxies R API version details + configured Flask version.
    """
    from flask import jsonify

    # 1. Get Flask App Version (from env or current tag)
    flask_version = current_app.config.get("DATA_EXPLORER_VERSION", "unknown")

    # 2. Get R API Version (via internal proxy)
    api_url = current_app.config.get("API_URL", "http://127.0.0.1:8000")
    try:
        # We likely need requests here if not imported, but this file is already using logic
        # normally found in services.
        import requests
        r_resp = requests.get(f"{api_url}/version", timeout=5)
        if r_resp.status_code == 200:
            r_data = r_resp.json()
        else:
            r_data = {"error": f"R API returned {r_resp.status_code}"}
    except Exception as e:
        r_data = {"error": "R API unreachable", "details": str(e)}

    return jsonify({
        "app_version": flask_version,
        "r_api_version": r_data
    })


@main_bp.route("/favicon.ico")
def favicon():
    """Serve the site favicon for browsers and legacy icon requests."""
    assets_dir = Path(current_app.root_path) / "static" / "assets"
    return send_from_directory(assets_dir, "favicon.ico", mimetype="image/vnd.microsoft.icon")
