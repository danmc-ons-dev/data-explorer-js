"""
This blueprint handles all indicator-related routes.
Currently includes:
- dlnm (heat/cold)
- wildfires (air pollution)
- mental health
Placeholders for future indicators are also included.
"""

import base64
import io
import json as _json
import os
import pathlib
import tempfile
import zipfile

import pandas as pd
import requests
from flask import (
    Blueprint,
    json,
    request,
    jsonify,
    render_template,
    current_app,
    send_file,
    session
)

from data_explorer.utils.api_error_handler import (
    handle_api_response,
    make_error_response,
    APIErrorResponse
)

indicator_bp = Blueprint("indicator_bp", __name__)


# -----------------------------------------------------------------------------
# Hash allowlists for top-level tab sections.
# These lists drive both header link visibility and hash-based access checks.
# When ENABLE_FULL_UI is false we use LIVE_* lists; when true we use DEV_* lists.
# -----------------------------------------------------------------------------

LIVE_FRAMEWORK_HASHES = [
    "soschi",
    # "waterborne-diseases",
    # "vectorborne-diseases",
    # "heat-and-cold",
    # "mental-health",
    # "air-pollution-tab",
    # "wildfires-tab",
    # "airborne-diseases-tab",
    # "undernutrition",
    # "flooding-tab",
    # "healthcare-systems-and-facilities"
]

LIVE_INDICATOR_CALCULATOR_HASHES = [
    "descriptive-statistics",
    "heat-and-cold",
    "extreme-weather-events",
    "waterborne-diseases",
    "vectorborne-diseases",
    "mental-health",
    "air-pollution",
]

DEV_FRAMEWORK_HASHES = [
    "soschi",
    "waterborne-diseases",
    "vectorborne-diseases",
    "heat-and-cold",
    "mental-health",
    "air-pollution-tab",
    "wildfires-tab",
    "airborne-diseases-tab",
    "undernutrition",
    "flooding-tab",
    "healthcare-systems-and-facilities"
]


DEV_INDICATOR_CALCULATOR_HASHES = [
    "descriptive-statistics",
    "heat-and-cold",
    "extreme-weather-events",
    "waterborne-diseases",
    "vectorborne-diseases",
    "mental-health",
    "air-pollution",
]


def get_allowed_framework_hashes():
    if not current_app.config.get("ENABLE_FULL_UI", False):
        return LIVE_FRAMEWORK_HASHES
    return DEV_FRAMEWORK_HASHES


def get_allowed_indicator_calculator_hashes():
    if not current_app.config.get("ENABLE_FULL_UI", False):
        return LIVE_INDICATOR_CALCULATOR_HASHES
    return DEV_INDICATOR_CALCULATOR_HASHES


@indicator_bp.app_context_processor
def inject_allowed_framework_hashes():
    return {
        "allowed_framework_hashes": get_allowed_framework_hashes(),
        "allowed_indicator_calculator_hashes": get_allowed_indicator_calculator_hashes(),
    }


TOOLTIPS_PATH = pathlib.Path(os.path.dirname(os.path.abspath(__file__))) / \
    ".." / "static" / "data" / "csv" / "tooltips.json"


def load_tooltips():
    if not TOOLTIPS_PATH.exists():
        return {}
    try:
        with TOOLTIPS_PATH.open("r", encoding="utf-8") as handle:
            raw = _json.load(handle)
    except _json.JSONDecodeError:
        return {}
    tooltips = {}
    for key, value in raw.items():
        if isinstance(value, list):
            tooltips[key] = value[0] if value else ""
        else:
            tooltips[key] = value
    return tooltips


@indicator_bp.route("/framework")
def framework():
    """
    Renders a page describing the conceptual framework
    (e.g., how climate indicators link to health outcomes).
    """
    allowed_hashes = get_allowed_framework_hashes()
    return render_template("framework.html", allowed_hashes=allowed_hashes)


@indicator_bp.route("/indicator_calculators")
def indicator_calculators():
    """
    Page that lists or provides access to various climate-health calculators.
    """
    return render_template(
        "indicator_calculators.html",
        tooltips=load_tooltips(),
        allowed_indicator_hashes=get_allowed_indicator_calculator_hashes(),
    )

# -----------------------------------------------------------------------------
# HELPER FUNCTION (optional)
# -----------------------------------------------------------------------------


def create_tmp_dir():
    tmp_path = (current_app.config.get(
        "TEMPORARY_DIRECTORY_PATH") or "").strip()
    if tmp_path:
        tmp_dir = tempfile.mkdtemp(
            prefix="desc_stats_temporary_", dir=tmp_path)
    else:
        tmp_dir = tempfile.mkdtemp(prefix="desc_stats_temporary_")
    with open(os.path.join(tmp_dir, "keep.txt"), "w") as f:
        f.write("")
    return tmp_dir


def zip_directory_as_bytes(path):
    """Zip a directory and return it as a BytesIO buffer."""
    if not os.path.exists(path):
        return None
    zip_bytes = io.BytesIO()
    with zipfile.ZipFile(zip_bytes, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(path):
            for file_ in files:
                fpath = os.path.join(root, file_)
                archive_name = os.path.relpath(fpath, start=path)
                zf.write(fpath, archive_name)
    zip_bytes.seek(0)
    return zip_bytes


@indicator_bp.route("/get_zip_file", methods=["POST"])
def get_zip_file():
    """Return a zip of an indicator output directory for client download."""
    data = request.json
    path = data["path"]
    fname = data["fname"]
    if "desc_stats_temporary" not in str(path):
        return None
    zip_bytes = zip_directory_as_bytes(path)
    if len(fname.split(".")) < 2:
        fname = f"{fname}.zip"
    elif fname.split(".")[1] != "zip":
        fname = f"{fname.split('.')[0]}.zip"
    return send_file(zip_bytes, mimetype="application/zip", as_attachment=True, download_name=fname)


def call_r_api(payload, endpoint="regression"):
    """
    Generic function to call external R-based API endpoint.
    """
    api_url = current_app.config.get("API_URL", "http://127.0.0.1:5671")
    if api_url.endswith("/"):
        api_url = api_url[:-1]
    full_endpoint = f"{api_url}/{endpoint}"

    auth_user = current_app.config.get("API_USERNAME", "")
    auth_pass = current_app.config.get("API_PASSWORD", "")

    try:
        response = requests.post(
            full_endpoint,
            json=payload,
            headers={"Content-Type": "application/json"},
            auth=(auth_user, auth_pass),
            verify=False,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        current_app.logger.error(
            f"Error calling R-based API endpoint '{endpoint}': {e.__class__.__name__} - {str(e)}")
        if e.response is not None:
            current_app.logger.error(f"Response content: {e.response.text}")
        # Return an error structure or re-raise
        return jsonify({"error": str(e)}, status=500)


def _as_records(value):
    """Coerce an R-deserialised value into a list of dicts.

    Plumber's default JSON serialiser is inconsistent about shape:
      - a one-row data.frame can come back as either a list-of-dicts or as
        a dict-of-columns
      - missing/empty results can be ``NULL`` (-> ``None``) or ``list()``
        (-> ``{}`` or ``[]``)
    Routes that iterate over rows need a single normalised shape to avoid
    AttributeError when calling ``.get()`` on non-dict items.
    """
    if value in (None, "", [], {}):
        return []
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    if isinstance(value, dict):
        # Dict-of-columns (R data.frame style): {"col_a": [v1, v2], ...}
        # -> transpose into row-records.
        cols = [v for v in value.values() if isinstance(v, list)]
        if cols and all(isinstance(v, list) for v in value.values()):
            n = min(len(v) for v in cols)
            keys = list(value.keys())
            return [
                {k: value[k][i] for k in keys}
                for i in range(n)
            ]
        # Named-list-of-dicts (e.g. region -> row): take the values.
        if all(isinstance(v, dict) for v in value.values()):
            return list(value.values())
    return []


# -----------------------------------------------------------------------------
# Shared helpers for the disease endpoints (diarrhea, malaria)
#
# Both endpoints share the same shape:
#   - three file uploads (health CSV, climate CSV, shapefile ZIP)
#   - the same set of column-mapping form fields
#   - the same INLA / spline / threshold tuning fields
# The only meaningful divergence is the case column name on the JS side
# ("diarrhea_case_col" vs "malaria_case_col"), which both map onto R's
# single `case_col` argument.
# -----------------------------------------------------------------------------

_DISEASE_COL_FIELDS = (
    "region_col",
    "district_col",
    "date_col",
    "year_col",
    "month_col",
    "tot_pop_col",
    "tmin_col",
    "tmean_col",
    "tmax_col",
    "rainfall_col",
    "r_humidity_col",
    "runoff_col",
    "geometry_col",
    "spi_col",
    "ndvi_col",
    "param_term",
    "level",
)

_DISEASE_MANDATORY = (
    "region_col",
    "district_col",
    "year_col",
    "month_col",
    "case_col",
    "tot_pop_col",
    "tmin_col",
    "tmean_col",
    "tmax_col",
    "rainfall_col",
    "r_humidity_col",
    "runoff_col",
    "param_term",
    "level",
)


def _split_csv_or_none(raw):
    if not isinstance(raw, str):
        return None
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return parts or None


def _disease_payload_from_form(health_df, climate_df, geo_zip_file,
                               case_col_form_key):
    """Translate the disease-indicator form into the JSON payload that
    climatehealth::{diarrhea,malaria}_do_analysis expects.

    The geo zip file is read into memory and base64-encoded inline; the R-side
    plumber wrapper (`.with_map_zip`) decodes it back to a shapefile path.
    """
    form = request.form

    payload = {name: form.get(name) for name in _DISEASE_COL_FIELDS}
    payload["case_col"] = form.get(case_col_form_key)
    payload["geometry_col"] = payload.get("geometry_col") or "geometry"

    # Backwards-compat: older forms used "cvh_col" for what is now ndvi_col.
    if not payload.get("ndvi_col"):
        payload["ndvi_col"] = form.get("cvh_col")

    payload["basis_matrices_choices"] = _split_csv_or_none(
        form.get("basis_matrices_choices"))
    payload["inla_param"] = _split_csv_or_none(form.get("inla_param"))

    try:
        payload["param_threshold"] = float(form.get("param_threshold", 1))
    except (TypeError, ValueError):
        payload["param_threshold"] = 1.0
    try:
        payload["max_lag"] = int(form.get("max_lag", 2))
    except (TypeError, ValueError):
        payload["max_lag"] = 2

    payload["health_data_path"] = health_df.to_dict(orient="records")
    payload["climate_data_path"] = climate_df.to_dict(orient="records")
    payload["map_zip_b64"] = base64.b64encode(geo_zip_file.read()).decode("ascii")

    # Replace empty strings with None for cleaner JSON.
    for nm, val in list(payload.items()):
        if isinstance(val, str) and val.strip() == "":
            payload[nm] = None

    return payload


def _call_disease_endpoint(payload, endpoint_path):
    """POST a disease payload to the R plumber endpoint and return jsonified
    results.  Validates required fields up-front so the caller doesn't burn an
    HTTP round-trip on an obviously bad form."""
    missing = [k for k in _DISEASE_MANDATORY if not payload.get(k)]
    if missing:
        return jsonify(
            error=f"Missing required parameters: {', '.join(missing)}"
        ), 400

    api_url = current_app.config.get("API_URL", "http://127.0.0.1:8000")
    if api_url.endswith("/"):
        api_url = api_url[:-1]
    url = f"{api_url}{endpoint_path}"

    try:
        api_response = requests.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            verify=False,
        )
        current_app.logger.info(
            "R %s HTTP status: %s", endpoint_path, api_response.status_code)

        api_result = handle_api_response(api_response, endpoint=endpoint_path)
        if isinstance(api_result, APIErrorResponse):
            return make_error_response(api_result)

        result_json = api_result.json()
    except requests.RequestException as e:
        resp_text = e.response.text if e.response is not None else ""
        current_app.logger.error(
            "Error calling R %s: %s; response: %s",
            endpoint_path, str(e), resp_text)
        return jsonify(
            error="R API call failed",
            details=str(e),
            response=resp_text or None,
        ), 502

    return jsonify(
        rr_df=result_json.get("rr_df"),
        an_ar_results=result_json.get("an_ar_results"),
        result_json=result_json,
    )


# -----------------------------------------------------------------------------
# 0. Descriptive Stats
# -----------------------------------------------------------------------------


def preprocess_descriptives(form):
    """Read and reformat the form data for descriptive stats.

    Translates UI form field names to the parameter names that
    climatehealth::run_descriptive_stats_api() actually accepts, and drops
    anything the R function doesn't know about (otherwise plumber silently
    discards them, which has historically masked broken plot toggles).
    """
    # Map JS form-key → R argument name where they differ.
    js_to_r = {
        "plot_correlation": "plot_corr_matrix",
        "plot_dist_hists": "plot_dist",
    }

    # Booleans that come in as the literal strings "true"/"false".
    bool_keys = {
        "plot_corr_matrix",
        "plot_dist",
        "plot_ma",
        "plot_na_counts",
        "plot_scatter",
        "plot_box",
        "plot_seasonal",
        "plot_regional",
        "plot_total",
        "detect_outliers",
        "calculate_rate",
        "create_base_dir",
    }

    # Comma-separated multi-selects.
    list_keys = {"independent_cols"}

    # Whitelist of keys run_descriptive_stats_api() accepts. Anything else
    # (e.g. dataset_title, dist_columns, ma_columns) is UI-only and must not
    # be forwarded — plumber would otherwise drop them on the R side anyway,
    # and forwarding them makes future schema drift harder to spot.
    r_param_whitelist = {
        "aggregation_column",
        "population_col",
        "dependent_col",
        "independent_cols",
        "units",
        "plot_corr_matrix",
        "plot_dist",
        "plot_ma",
        "plot_na_counts",
        "plot_scatter",
        "plot_box",
        "plot_seasonal",
        "plot_regional",
        "plot_total",
        "correlation_method",
        "ma_days",
        "ma_sides",
        "timeseries_col",
        "detect_outliers",
        "calculate_rate",
        "run_id",
        "create_base_dir",
    }

    payload = {}
    for js_key in form.keys():
        r_key = js_to_r.get(js_key, js_key)
        if r_key not in r_param_whitelist:
            continue

        raw = form.get(js_key)

        if r_key == "aggregation_column":
            payload[r_key] = None if raw in (None, "", "no_column") else raw
            continue

        if r_key in bool_keys:
            payload[r_key] = str(raw).lower() == "true"
            continue

        if r_key in list_keys:
            if raw in (None, "", "null"):
                payload[r_key] = None
            else:
                parts = [p.strip() for p in raw.split(",") if p.strip()]
                payload[r_key] = parts or None
            continue

        payload[r_key] = None if raw in (None, "", "null") else raw

    return payload


@indicator_bp.route("/descriptive_stats", methods=["GET", "POST"])
def descriptive_stats():
    """
    Desc Stats.
    """
    if request.method == "POST":
        # Read Data
        file = request.files.get("file")
        if not file:
            return jsonify(error="No file uploaded"), 400
        df = pd.read_csv(file).fillna('').to_dict(orient="records")
        # Create payload
        payload = preprocess_descriptives(request.form)
        payload["data"] = df
        # Setup temp dir
        tmp_dir = create_tmp_dir()
        payload["output_path"] = os.path.abspath(tmp_dir)

        # Call R-based API
        desc_stats_path = call_r_api(payload, endpoint="descriptive_stats")
        return jsonify(desc_stats_path=desc_stats_path)

    # If GET, show a template or instructions
    return jsonify({"message": "Descriptive stats instructions coming soon."})


# -----------------------------------------------------------------------------
# 1. Heat and cold indicator
# -----------------------------------------------------------------------------
@indicator_bp.route("/heat_and_cold_indicator", methods=["GET", "POST"])
def heat_and_cold_indicator():
    """
    Endpoint for uploading temperature + mortality data,
    then calling the R-based heat_and_cold_analysis endpoint.
    """
    print("#### INDICATOR_ROUTES /heat_and_cold ####    ")
    if request.method == "POST":
        file = request.files.get("file")
        if not file:
            return jsonify(error="No file uploaded"), 400

        df = pd.read_csv(file).fillna("")
        # Gather form data
        deaths = request.form.get("deaths")
        time = request.form.get("time")
        temp = request.form.get("temp")
        pop = request.form.get("pop")
        country = request.form.get("country") or "National"
        subgeo = request.form.get("subgeo")
        ind1 = request.form.get("ind1")
        ind2 = request.form.get("ind2")
        ind3 = request.form.get("ind3")
        ind4 = request.form.get("ind4")
        meta = request.form.get("meta")
        rr_dist = int(request.form.get("rr_dist") or 0)
        output_year = int(request.form.get("output_year") or 0)
        lag = int(request.form.get("lag") or 21)
        seasonal = int(request.form.get("seasonal") or 8)

        meta_val = True if meta == "true" else False
        independent_cols = [c for c in [
            ind1, ind2, ind3, ind4] if c not in ["", None]]
        if len(independent_cols) == 0:
            independent_cols = None

        df_records = df.to_dict(orient="records")
        subgeo = None if (subgeo or "").strip().lower() in ["", "none"] else subgeo

        # Optional analysis tuning (UI doesn't expose these yet, but the
        # passthrough keeps the route ready for fuller forms in the future).
        def _float_or(default, name):
            try:
                return float(request.form.get(name, default))
            except (TypeError, ValueError):
                return default

        var_per_raw = request.form.get("var_per")
        if var_per_raw:
            try:
                var_per = [float(v.strip()) for v in var_per_raw.split(",") if v.strip()]
                if not var_per:
                    var_per = [10, 75, 90]
            except ValueError:
                var_per = [10, 75, 90]
        else:
            var_per = [10, 75, 90]

        attr_thr_high = _float_or(97.5, "attr_thr_high")
        attr_thr_low = _float_or(2.5, "attr_thr_low")

        # Parameter names must match temp_mortality_do_analysis()
        payload = {
            "data_path": df_records,
            "date_col": time,
            "region_col": subgeo,
            "temperature_col": temp,
            "dependent_col": deaths,
            "population_col": pop,
            "country": country,
            "independent_cols": independent_cols,
            "var_fun": "bs",
            "var_degree": 2,
            "var_per": var_per,
            "lagn": int(lag),
            "lagnk": 3,
            "dfseas": seasonal,
            "meta_analysis": meta_val,
            "attr_thr_high": attr_thr_high,
            "attr_thr_low": attr_thr_low,
        }

        # Call R-based API
        api_url = current_app.config.get("API_URL", "http://127.0.0.1:8000")
        if api_url.endswith("/"):
            api_url = api_url[:-1]
        heat_api_url = f"{api_url}/temperature"

        try:
            api_response = requests.post(
                heat_api_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                verify=False
            )
            # Use centralized error handling for API responses
            result = handle_api_response(api_response, endpoint="/temperature")
            if isinstance(result, APIErrorResponse):
                return make_error_response(result)

            json_response = result.json()

            # R API returns a dict with keys: rr_results, an_ar_results,
            # annual_an_ar_results, monthly_an_ar_results
            # Transform to the list-based format the frontend expects

            # Transform RR results: map column names to what JS expects
            transformed_rr = [
                {
                    "regions": row.get("Area"),
                    "temp": row.get("Temperature"),
                    "rel_risk": row.get("RR"),
                    "upper": row.get("RR_upper_CI"),
                    "lower": row.get("RR_lower_CI"),
                    "optimal_temp_range_min": row.get("Attr_Threshold_Ligh_Temp"),
                    "optimal_temp_range_max": row.get("Attr_Threshold_High_Temp"),
                }
                for row in _as_records(json_response.get("rr_results"))
            ]

            # Transform AR results: map column names to what JS expects
            transformed_ar = [
                {
                    "_row": row.get("region"),
                    "high_heat": row.get("ar_heat"),
                    "high_cold": row.get("ar_cold"),
                    "high_heat_upper": row.get("ar_heat_upper_ci"),
                    "high_heat_lower": row.get("ar_heat_lower_ci"),
                    "high_cold_upper": row.get("ar_cold_upper_ci"),
                    "high_cold_lower": row.get("ar_cold_lower_ci"),
                }
                for row in _as_records(json_response.get("an_ar_results"))
            ]

            # Aggregate annual AN per region (R returns dict keyed by region).
            annual_results = json_response.get("annual_an_ar_results") or {}
            transformed_deaths = []
            if isinstance(annual_results, dict):
                for region, data in annual_results.items():
                    rows = _as_records(data)
                    if not rows:
                        continue
                    total_an_heat = sum(r.get("an_heat", 0) or 0 for r in rows)
                    total_an_cold = sum(r.get("an_cold", 0) or 0 for r in rows)
                    transformed_deaths.append({
                        "_row": region,
                        "high_heat": total_an_heat,
                        "high_cold": total_an_cold,
                    })

            # Build response in old list format:
            # [0]=rr, [1]=temp_df, [2]=deaths, [3]=bind, [4]=ar_rates
            legacy_response = [
                transformed_rr,       # index 0: RR results
                [],                   # index 1: temp_df (unused)
                transformed_deaths,   # index 2: deaths (AN totals)
                [],                   # index 3: bind (unused)
                transformed_ar,       # index 4: AR rates
            ]

            return jsonify(
                json_response=legacy_response,
                joined_gdf=pd.DataFrame().to_json()
            )

        except Exception as e:
            current_app.logger.error(f"Error calling R-based API: {str(e)}")
            return jsonify(error=str(e)), 500

    return render_template("dlnm_form.html", indicator="Heat and cold indicator")


# -----------------------------------------------------------------------------
# 2. Mental Health Indicator
# -----------------------------------------------------------------------------
@indicator_bp.route("/mental_health", methods=["GET", "POST"])
def mental_health_indicator():
    """
    Endpoint for uploading mental health + climate data,
    then calling the R-based mental_health_func endpoint.
    """
    if request.method == "POST":
        # 1. Grab the uploaded file
        file = request.files.get("file")
        if not file:
            return jsonify(error="No file uploaded"), 400

        # 2. Read CSV in Python to confirm structure (optional)
        df = pd.read_csv(file)
        df = df.fillna("")

        # 3. Gather form data for column mappings
        date_col = request.form.get("date_col")
        region_col = request.form.get("region_col") or None
        temperature_col = request.form.get("temperature_col")
        population_col = request.form.get("population_col")
        health_outcome_col = request.form.get("health_outcome_col")

        # Check for missing parameters
        missing_params = [name for name, val in [
            ("date_col", date_col),
            ("region_col", region_col),
            ("temperature_col", temperature_col),
            ("population_col", population_col),
            ("health_outcome_col", health_outcome_col)]
            if not val]
        if missing_params:
            return jsonify(
                error=f"Missing required parameters in the form: {', '.join(missing_params)}"
            ), 400

        # Optional confounders from the UI, comma-separated
        independent_cols = request.form.get("independent_cols", "")
        control_cols = request.form.get("control_cols", "")

        independent_cols = [col.strip() for col in independent_cols.split(
            ",") if col.strip()] or None
        control_cols = [col.strip()
                        for col in control_cols.split(",") if col.strip()] or None

        # Country + meta toggles from UI
        country = request.form.get("country") or "National"
        meta_analysis = request.form.get(
            "meta_analysis", "false").lower() == "true"

        # DLNM/lag parameters — defaults match suicides_heat_do_analysis().
        # Currently the calculator UI doesn't expose these, so the form
        # values will be absent and the R defaults will apply.
        def _int_or(default, name):
            try:
                return int(request.form.get(name, default))
            except (TypeError, ValueError):
                return default

        def _float_or(default, name):
            try:
                return float(request.form.get(name, default))
            except (TypeError, ValueError):
                return default

        var_fun = request.form.get("var_fun", "bs")
        var_degree = _int_or(2, "var_degree")
        lag_fun = request.form.get("lag_fun", "strata")
        lag_breaks = _int_or(1, "lag_breaks")
        lag_days = _int_or(2, "lag_days")
        cenper = _float_or(50, "cenper")
        attr_thr = _float_or(97.5, "attr_thr")

        df_records = df.to_dict(orient="records")

        payload = {
            "data_path": df_records,
            "date_col": date_col,
            "region_col": region_col,
            "temperature_col": temperature_col,
            "population_col": population_col,
            "health_outcome_col": health_outcome_col,
            "country": country,
            "meta_analysis": meta_analysis,
            "independent_cols": independent_cols,
            "control_cols": control_cols,
            "var_fun": var_fun,
            "var_degree": var_degree,
            "lag_fun": lag_fun,
            "lag_breaks": lag_breaks,
            "lag_days": lag_days,
            "cenper": cenper,
            "attr_thr": attr_thr,
            "save_fig": False,
            "save_csv": False,
        }

        # 7. Call the R-based endpoint
        #    Adjust 'mental_health_url' to be your R API's actual location
        # mental_health_url = current_app.config.get("MENTAL_HEALTH_URL",
        # "http://127.0.0.1:8000/mental_health")
        api_url = current_app.config.get("API_URL", "http://127.0.0.1:8000")
        if api_url.endswith("/"):
            api_url = api_url[:-1]
        mental_health_url = f"{api_url}/mental_health"
        try:
            api_response = requests.post(
                mental_health_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                verify=False
            )
        except requests.RequestException as e:
            current_app.logger.error(f"Error calling mental health R API: {e}")
            return jsonify(error=f"R API call failed: {str(e)}"), 502

        # Use centralized error handling for API responses
        api_result = handle_api_response(api_response, endpoint="/mental_health")
        if isinstance(api_result, APIErrorResponse):
            return make_error_response(api_result)

        try:
            result_json = api_result.json()

            rr_rows = _as_records(result_json.get("rr_results"))

            mapped_rr = [
                {
                    "disagg": row.get("Area") or "National",
                    "Temperature": row.get("Temperature"),
                    "RRfit": row.get("RR"),
                    "RRhigh": row.get("RR_upper_CI"),
                    "RRlow": row.get("RR_lower_CI"),
                }
                for row in rr_rows
            ]

            response_body = {
                "rr_results": mapped_rr,
                "qaic_results": result_json.get("qaic_results"),
                "vif_results": result_json.get("vif_results"),
                "attr_yr_list": result_json.get("attr_yr_list"),
                "attr_mth_list": result_json.get("attr_mth_list"),
            }

            # Check if results returned okay
            current_app.logger.info("R /mental_health returned %s RR rows | qaic:%s vif:%s attr_yr:%s attr_mth:%s", len(rr_rows),
                                    bool(response_body["qaic_results"]),
                                    bool(response_body["vif_results"]),
                                    bool(response_body["attr_yr_list"]),
                                    bool(response_body["attr_mth_list"]),
                                    )

        except ValueError:
            current_app.logger.error(
                "R /mental_health returned invalid JSON body")
            return jsonify(error="R /mental_health returned invalid JSON body"), 500

        #    The R code returns a 'results' DataFrame or object with cumulative relative risk, etc.
        #    We can pass it to a template or just JSONify it:
        return jsonify(response_body)

    # If GET, show a form for the user to upload CSV + specify columns
    return render_template("mental_health_form.html")

# -----------------------------------------------------------------------------
# 3. Wildfires Indicator
# -----------------------------------------------------------------------------


@indicator_bp.route("/wildfires", methods=["GET", "POST"])
def wildfires_indicator():
    """
    Endpoint for uploading wildfire + health data,
    then calling the R-based /wildfires endpoint.
    """
    if request.method == "POST":
        current_app.logger.info(
            "Received POST request for /wildfires indicator")

        # 1. Grab the uploaded file (health data CSV)
        file = request.files.get("file")
        if not file:
            return jsonify(error="No health data file uploaded"), 400

        current_app.logger.info(
            "Wildfires health data file received: %s", file.filename)

        # 2. Convert the CSV to a Pandas DataFrame (optional, for validation)
        try:
            health_df = pd.read_csv(file)
        except Exception as e:
            current_app.logger.error(f"Error reading health data CSV: {e}")
            return jsonify(error=f"Failed to read health data CSV: {str(e)}"), 400

        health_df = health_df.fillna("")
        current_app.logger.info("Wildfires health data CSV shape: %s rows x %s cols",
                                health_df.shape[0],
                                health_df.shape[1])

        # 3. Gather form data for user-provided parameters
        join_wildfire_data = request.form.get(
            "join_wildfire_data", "false").lower() == "true"
        ncdf_path = request.form.get("ncdf_path") or None
        shp_path = request.form.get("shp_path") or None

        date_col = request.form.get("date_col", "date")
        region_col = request.form.get("region_col") or None
        shape_region_col = request.form.get("shape_region_col") or None
        mean_temperature_col = request.form.get(
            "mean_temperature_col", "tmean")
        health_outcome_col = request.form.get(
            "health_outcome_col", "health_outcome")
        pm_2_5_col = request.form.get("pm_25_col") or None
        population_col = request.form.get("population_col") or None
        rh_col = request.form.get("rh_col") or None
        wind_speed_col = request.form.get("wind_speed_col") or None

        wildfire_lag = int(request.form.get("wildfire_lag", 3))
        temperature_lag = int(request.form.get("temperature_lag", 1))
        spline_temp_dof = int(request.form.get(
            "spline_temperature_degrees_freedom", 6))

        scale_factor = float(request.form.get("scale_factor_wildfire_pm", 10))
        rr_by_region = request.form.get("relative_risk_by_region")
        calculate_by_region = str(rr_by_region).lower() == "true" \
            if rr_by_region is not None else False

        # Optional VIF predictors (comma-separated list)
        predictors_vif_raw = request.form.get("predictors_vif")
        if predictors_vif_raw:
            predictors_vif = [
                p.strip() for p in predictors_vif_raw.split(",") if p.strip()
            ] or None
        else:
            predictors_vif = None

        # Convert the health_df to records
        health_data_records = health_df.to_dict(orient="records")

        # Parameter names must match wildfire_do_analysis()
        payload = {
            "health_path": health_data_records,
            "join_wildfire_data": join_wildfire_data,
            "ncdf_path": ncdf_path,
            "shp_path": shp_path,
            "date_col": date_col,
            "region_col": region_col,
            "shape_region_col": shape_region_col,
            "mean_temperature_col": mean_temperature_col,
            "health_outcome_col": health_outcome_col,
            "population_col": population_col,
            "rh_col": rh_col,
            "wind_speed_col": wind_speed_col,
            "pm_2_5_col": pm_2_5_col,
            "wildfire_lag": wildfire_lag,
            "temperature_lag": temperature_lag,
            "spline_temperature_degrees_freedom": spline_temp_dof,
            "predictors_vif": predictors_vif,
            "calculate_by_region": calculate_by_region,
            "scale_factor_wildfire_pm": scale_factor,
        }

        # Replace empty strings with None for cleaner JSON
        for (nm, val) in payload.items():
            if isinstance(val, str) and val.strip() == "":
                payload[nm] = None

        # current_app.logger.debug("Wildfires payload to R: %s", payload)

        # 6. Call the R-based /wildfires endpoint
        # wildfires_url = current_app.config.get("WILDFIRES_URL", "http://127.0.0.1:8000/wildfires")
        api_url = current_app.config.get("API_URL", "http://127.0.0.1:8000")
        if api_url.endswith("/"):
            api_url = api_url[:-1]
        wildfires_url = f"{api_url}/wildfires"
        # current_app.logger.info("Calling R /wildfires API at: %s", wildfires_url)

        try:
            api_response = requests.post(
                wildfires_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                verify=False
            )
            current_app.logger.info(
                "R /wildfires HTTP status code: %s", api_response.status_code)
            current_app.logger.debug(
                "R /wildfires response text: %s", api_response.text[:1000])

            # Use centralized error handling for API responses
            api_result = handle_api_response(api_response, endpoint="/wildfires")
            if isinstance(api_result, APIErrorResponse):
                return make_error_response(api_result)

            result_json = api_result.json()
            if isinstance(result_json, dict):
                current_app.logger.debug(
                    "R /wildfires API returned keys: %s", list(result_json.keys()))

        except requests.RequestException as e:
            # Include response text if available
            resp_text = ""
            if e.response is not None:
                resp_text = e.response.text
                current_app.logger.error(
                    "Error calling R /wildfires API: %s; response: %s",
                    str(e),
                    resp_text)
            else:
                current_app.logger.error(
                    f"Error calling wildfires R API: {str(e)}")

            return jsonify(error=f"R API call failed",
                           details=str(e),
                           response=resp_text or None), 502

        # 7. Return the JSON result to the UI
        return jsonify(
            rr_results=result_json.get("RR_results"),
            an_af_results=result_json.get("AF_AN_results"),
            ar_pm_results=result_json.get("AR_PM_monthly"),
        )

    # If GET, show a form to upload CSV and specify parameters
    return render_template("wildfires_form.html")

# -----------------------------------------------------------------------------
# 4. Air pollution indicator
# -----------------------------------------------------------------------------


@indicator_bp.route("/airpollution", methods=["GET", "POST"])
def airpollution_indicator():
    """
    Endpoint for uploading PM2.5 + mortality data, then calling the R-based
    /airpollution endpoint (climatehealth::air_pollution_do_analysis).
    """
    if request.method == "POST":
        current_app.logger.info(
            "Received POST request for /airpollution indicator")

        file = request.files.get("file")
        if not file:
            return jsonify(error="No file uploaded"), 400

        try:
            df = pd.read_csv(file)
        except Exception as e:
            current_app.logger.error(f"Error reading air pollution CSV: {e}")
            return jsonify(error=f"Failed to read CSV: {str(e)}"), 400

        df = df.fillna("")
        current_app.logger.info(
            "Air pollution CSV shape: %s rows x %s cols",
            df.shape[0], df.shape[1]
        )

        # --- Column mappings (must match R defaults: date, region, pm25,
        # deaths, population, humidity, precipitation, tmax, wind_speed) ---
        date_col = request.form.get("date_col", "date")
        region_col = request.form.get("region_col", "region")
        pm25_col = request.form.get("pm25_col", "pm25")
        deaths_col = request.form.get("deaths_col", "deaths")
        population_col = request.form.get("population_col", "population")
        humidity_col = request.form.get("humidity_col", "humidity")
        precipitation_col = request.form.get("precipitation_col", "precipitation")
        tmax_col = request.form.get("tmax_col", "tmax")
        wind_speed_col = request.form.get("wind_speed_col", "wind_speed")

        # --- Optional extra covariates (comma-separated lists) ---
        def split_or_none(name):
            raw = request.form.get(name)
            if not raw:
                return None
            parts = [p.strip() for p in raw.split(",") if p.strip()]
            return parts or None

        categorical_others = split_or_none("categorical_others")
        continuous_others = split_or_none("continuous_others")

        # --- Analysis parameters ---
        def int_or(default, name):
            try:
                return int(request.form.get(name, default))
            except (TypeError, ValueError):
                return default

        def float_or(default, name):
            try:
                return float(request.form.get(name, default))
            except (TypeError, ValueError):
                return default

        max_lag = int_or(14, "max_lag")
        df_seasonal = int_or(6, "df_seasonal")
        family = request.form.get("family", "quasipoisson")
        moving_average_window = int_or(3, "moving_average_window")
        attr_thr = float_or(95, "attr_thr")

        # --- Reference standards: accept JSON string or default to WHO 15 ---
        reference_standards_raw = request.form.get("reference_standards")
        if reference_standards_raw:
            try:
                reference_standards = _json.loads(reference_standards_raw)
            except (ValueError, TypeError):
                reference_standards = [{"value": 15, "name": "WHO"}]
        else:
            reference_standards = [{"value": 15, "name": "WHO"}]

        # --- Filters ---
        years_filter_raw = request.form.get("years_filter")
        if years_filter_raw:
            try:
                years_filter = [
                    int(y.strip()) for y in years_filter_raw.split(",")
                    if y.strip()
                ] or None
            except ValueError:
                years_filter = None
        else:
            years_filter = None
        regions_filter = split_or_none("regions_filter")

        include_national = request.form.get(
            "include_national", "true").lower() == "true"
        run_descriptive = request.form.get(
            "run_descriptive", "false").lower() == "true"
        run_power = request.form.get(
            "run_power", "false").lower() == "true"

        # Build payload — names MUST match air_pollution_do_analysis() args
        payload = {
            "data_path": df.to_dict(orient="records"),
            "date_col": date_col,
            "region_col": region_col,
            "pm25_col": pm25_col,
            "deaths_col": deaths_col,
            "population_col": population_col,
            "humidity_col": humidity_col,
            "precipitation_col": precipitation_col,
            "tmax_col": tmax_col,
            "wind_speed_col": wind_speed_col,
            "categorical_others": categorical_others,
            "continuous_others": continuous_others,
            "max_lag": max_lag,
            "df_seasonal": df_seasonal,
            "family": family,
            "reference_standards": reference_standards,
            "save_outputs": False,
            "run_descriptive": run_descriptive,
            "run_power": run_power,
            "moving_average_window": moving_average_window,
            "include_national": include_national,
            "years_filter": years_filter,
            "regions_filter": regions_filter,
            "attr_thr": attr_thr,
        }

        # Replace empty strings with None for cleaner JSON
        for nm, val in payload.items():
            if isinstance(val, str) and val.strip() == "":
                payload[nm] = None

        api_url = current_app.config.get("API_URL", "http://127.0.0.1:8000")
        if api_url.endswith("/"):
            api_url = api_url[:-1]
        airpollution_url = f"{api_url}/airpollution"

        try:
            api_response = requests.post(
                airpollution_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                verify=False,
            )
            current_app.logger.info(
                "R /airpollution HTTP status: %s", api_response.status_code)

            api_result = handle_api_response(
                api_response, endpoint="/airpollution")
            if isinstance(api_result, APIErrorResponse):
                return make_error_response(api_result)

            result_json = api_result.json()
            if isinstance(result_json, dict):
                current_app.logger.debug(
                    "R /airpollution returned keys: %s",
                    list(result_json.keys()))
        except requests.RequestException as e:
            resp_text = e.response.text if e.response is not None else ""
            current_app.logger.error(
                "Error calling R /airpollution API: %s; response: %s",
                str(e), resp_text)
            return jsonify(
                error="R API call failed",
                details=str(e),
                response=resp_text or None,
            ), 502

        return jsonify(
            meta_results=result_json.get("meta_results"),
            analysis_results=result_json.get("analysis_results"),
            power_results=result_json.get("power_results"),
            descriptive_stats=result_json.get("descriptive_stats"),
        )

    # GET: standalone form for ad-hoc / developer use
    return render_template("airpollution_form.html")

# -----------------------------------------------------------------------------
# 5. Waterborne diseases indicator -diarrhoea
# -----------------------------------------------------------------------------


@indicator_bp.route("/waterborne", methods=["GET", "POST"])
def waterborne_indicator():
    """
    Waterborne Diseases: Diarrhea.
    Calls climatehealth::diarrhea_do_analysis via the /diarrhea plumber endpoint.
    """
    if request.method == "POST":
        health_file = request.files.get("health_file")
        climate_file = request.files.get("climate_file")
        geo_zip_file = request.files.get("geo_zip_file")
        if not health_file or not climate_file or not geo_zip_file:
            return jsonify(error="Missing one or more required files (health, climate, geo_zip_file)"), 400

        health_df = pd.read_csv(health_file).fillna("")
        climate_df = pd.read_csv(climate_file).fillna("")

        payload = _disease_payload_from_form(
            health_df, climate_df, geo_zip_file, case_col_form_key="diarrhea_case_col"
        )

        return _call_disease_endpoint(payload, endpoint_path="/diarrhea")

# -----------------------------------------------------------------------------
# 6. Vectorborne diseases indicator - malaria
# -----------------------------------------------------------------------------


@indicator_bp.route("/vectorborne", methods=["GET", "POST"])
def vectorborne_indicator():
    """
    Vectorborne Diseases: Malaria.
    Calls climatehealth::malaria_do_analysis via the /malaria plumber endpoint.
    """
    if request.method == "POST":
        health_file = request.files.get("health_file")
        climate_file = request.files.get("climate_file")
        geo_zip_file = request.files.get("geo_zip_file")
        if not health_file or not climate_file or not geo_zip_file:
            return jsonify(error="Missing one or more required files (health, climate, geo_zip_file)"), 400

        health_df = pd.read_csv(health_file).fillna("")
        climate_df = pd.read_csv(climate_file).fillna("")

        payload = _disease_payload_from_form(
            health_df, climate_df, geo_zip_file, case_col_form_key="malaria_case_col"
        )

        return _call_disease_endpoint(payload, endpoint_path="/malaria")

    return render_template("indicator_calculators.html", indicator="vectorborne indicator")


@indicator_bp.route("/floods", methods=["GET", "POST"])
def floods_indicator():
    """
    Placeholder route for flood-related health impacts.
    """
    return jsonify({"message": "Floods indicator coming soon."})


@indicator_bp.route("/airborne", methods=["GET", "POST"])
def airborne_indicator():
    """
    Placeholder route for airborne diseases indicator.
    """
    return jsonify({"message": "airborne indicator coming soon."})


@indicator_bp.route("/foodborne_and_malnutrition", methods=["GET", "POST"])
def foodborne_and_malnutrition_indicator():
    """
    Placeholder route for malnutrition and foodborne diseases indicator.
    """
    return jsonify({"message": "foodborne_and_malnutrition indicator coming soon."})


@indicator_bp.route("/water_related", methods=["GET", "POST"])
def water_related_indicator():
    """
    Placeholder route for water_related health impacts indicator.
    """
    return jsonify({"message": "water_related indicator coming soon."})


@indicator_bp.route("/healthcare_systems", methods=["GET", "POST"])
def healthcare_systems_indicator():
    """
    Placeholder route for healthcare_systems indicator.
    """
    return jsonify({"message": "healthcare_systems documentation coming soon."})
