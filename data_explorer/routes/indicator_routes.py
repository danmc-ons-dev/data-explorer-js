"""
This blueprint handles all indicator-related routes.
Currently includes:
- dlnm (heat/cold)
- wildfires (air pollution)
- mental health
Placeholders for future indicators are also included.
"""

import os
import pandas as pd
import requests
import tempfile
from flask import (
    Blueprint,
    json,
    request,
    jsonify,
    render_template,
    current_app,
    session
)

from data_explorer.routes.data_routes import cleanup_tmp_dir, get_zip_file
from data_explorer.utils.api_error_handler import (
    handle_api_response,
    make_error_response,
    APIErrorResponse
)

indicator_bp = Blueprint("indicator_bp", __name__)

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
# -----------------------------------------------------------------------------
# 0. Descriptive Stats
# -----------------------------------------------------------------------------


def preprocess_descriptives(form):
    """Read and reformat the form data for descriptive stats."""
    reformatted_form = {}
    # disagg col
    agg_col = form.get("aggregation_column") if form.get(
        "aggregation_column") != "no_column" else None
    reformatted_form["aggregation_column"] = agg_col
    # plotting switches
    switches = [
        "plot_dist_hists",
        "plot_ma",
        "plot_na_counts",
        "plot_scatter",
        "plot_correlation"
    ]
    for s in switches:
        value = form.get(s)
        reformatted_form[s] = True if value == "true" else False
    # reformatted multi-selects
    multis = [
        "independent_cols",
        "ma_columns",
        "dist_columns"
    ]
    for m in multis:
        list_format = form.get(m).split(",")
        if len(list_format) == 1 and list_format[0] == "null":
            reformatted_form[m] = None
        else:
            reformatted_form[m] = list_format
    # NULLs
    remaining_fields = [i for i in list(
        form) if i not in reformatted_form.keys()]
    for f in remaining_fields:
        reformatted_form[f] = None if form.get(
            f) in ["null", ""] else form.get(f)
    return reformatted_form


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
        country = request.form.get("country")  # Not currently enabled
        subgeo = request.form.get("subgeo")
        ind1 = request.form.get("ind1")
        ind2 = request.form.get("ind2")
        ind3 = request.form.get("ind3")
        ind4 = request.form.get("ind4")
        # disagg = request.form.get("disagg", "false")
        meta = request.form.get("meta")  # "true" or "false" from the UI
        rr_dist = int(request.form.get("rr_dist") or 0)
        output_year = int(request.form.get("output_year") or 0)
        lag = int(request.form.get("lag") or 21)
        seasonal = int(request.form.get("seasonal") or 8)

        # Convert booleans
        meta_val = True if meta == "true" else False
        independent_cols = [c for c in [
            ind1, ind2, ind3, ind4] if c not in ["", None]]
        if len(independent_cols) == 0:
            independent_cols = None

        df_records = df.to_dict(orient="records")
        subgeo = None if subgeo.strip().lower() in ["", None] else subgeo

        # Build the JSON payload for the R endpoint
        # Parameter names must match climatehealth_api.R /temperature endpoint
        payload = {
            "data_path": df_records,
            "date_col": time,
            "geography_col": subgeo,
            "temperature_col": temp,
            "dependent_col": deaths,
            "population_col": pop,
            "independent_cols": independent_cols,
            "var_fun": "bs",
            "var_degree": 2,
            "lagn": int(lag),
            "lagnk": 3,
            "dfseas": seasonal,
            "meta_analysis": meta_val,
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
            rr_results = json_response.get("rr_results", [])
            transformed_rr = []
            for row in rr_results:
                transformed_rr.append({
                    "regions": row.get("Area"),
                    "temp": row.get("Temperature"),
                    "rel_risk": row.get("RR"),
                    "upper": row.get("RR_upper_CI"),
                    "lower": row.get("RR_lower_CI"),
                    "optimal_temp_range_min": row.get("Attr_Threshold_Ligh_Temp"),
                    "optimal_temp_range_max": row.get("Attr_Threshold_High_Temp"),
                })

            # Transform AR results: map column names to what JS expects
            an_ar_results = json_response.get("an_ar_results", [])
            transformed_ar = []
            for row in an_ar_results:
                transformed_ar.append({
                    "_row": row.get("region"),
                    "high_heat": row.get("ar_heat"),
                    "high_cold": row.get("ar_cold"),
                    "high_heat_upper": row.get("ar_heat_upper_ci"),
                    "high_heat_lower": row.get("ar_heat_lower_ci"),
                    "high_cold_upper": row.get("ar_cold_upper_ci"),
                    "high_cold_lower": row.get("ar_cold_lower_ci"),
                })

            # Transform annual AN results for deaths (index 2 in old format)
            annual_results = json_response.get("annual_an_ar_results", {})
            transformed_deaths = []
            # annual_results is a dict keyed by region
            for region, data in annual_results.items():
                if isinstance(data, list) and len(data) > 0:
                    # Aggregate across years for the region
                    total_an_heat = sum(r.get("an_heat", 0) or 0 for r in data)
                    total_an_cold = sum(r.get("an_cold", 0) or 0 for r in data)
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

        # 4. DLNM/lag parameters
        # var_fun = request.form.get("var_fun", "bs")
        # var_dof = int(request.form.get("var_dof", 2))
        # lag_fun = request.form.get("lag_fun", "strata")
        # lag_dof = int(request.form.get("lag_dof", 1))
        # lag_days = int(request.form.get("lag_days", 2))

        # save_fig = request.form.get("save_fig", "false").lower() == "true"
        # save_csv = request.form.get("save_csv", "false").lower() == "true"
        save_fig = False  # always false for API calls
        save_csv = False   # always false for API calls

        # Usually the R API wants a path or direct data.
        # We'll pass it as JSON 'data_path' or we might convert to CSV on disk.
        # For example, we can embed the data in a JSON field "data_path"
        # that the R code is prepared to handle.

        # 5. Convert df to a list-of-records JSON
        df_records = df.to_dict(orient="records")

        # independent_cols = 'rainfall', 'humidity'

        # 6. Build the JSON payload for the R endpoint
        payload = {
            "data_path": df_records,              # Instead of file path, we send data
            "date_col": date_col,
            "region_col": region_col,
            "temperature_col": temperature_col,
            "population_col": population_col,
            "health_outcome_col": health_outcome_col,
            "independent_cols": independent_cols,
            "control_cols": control_cols,
            # "var_fun": var_fun,
            # "var_degree": var_dof,
            # "lag_fun": lag_fun,
            # "lag_breaks": lag_dof,
            # "lag_days": lag_days,
            "save_fig": save_fig,
            "save_csv": save_csv
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

            # map rr_results to what the UI expects and stringify it
            rr_rows = result_json.get("rr_results") or []

            # Ensure it's a list of dicts; if it isn't, coerce defensively
            if isinstance(rr_rows, dict):
                # Some R/JSON libs can return a named list; convert to values
                rr_rows = list(rr_rows.values())
            elif not isinstance(rr_rows, list):
                rr_rows = []

            mapped_rr = []
            for row in rr_rows:
                # Defensive gets in case of missing keys
                mapped_rr.append({
                    "disagg": row.get("Area") or "National",
                    "Temperature": row.get("Temperature"),
                    "RRfit": row.get("RR"),
                    "RRhigh": row.get("RR_upper_CI"),
                    "RRlow": row.get("RR_lower_CI"),
                })

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
        mean_temperature_col = request.form.get(
            "mean_temperature_col", "tmean")
        health_outcome_col = request.form.get(
            "health_outcome_col", "health_outcome")
        pm_2_5_col = request.form.get("pm_25_col")

        wildfire_lag = int(request.form.get("wildfire_lag", 3))
        temperature_lag = int(request.form.get("temperature_lag", 1))
        spline_temperature_lag = int(
            request.form.get("spline_temperature_lag", 0))
        spline_temp_dof = int(request.form.get(
            "spline_temperature_degrees_freedom", 6))

        scale_factor = float(request.form.get("scale_factor_wildfire_pm", 10))
        rr_by_region = request.form.get("relative_risk_by_region")

        current_app.logger.debug(
            "Wildfires indicator parameters: join_wildfire_data=%s, ncdf_path=%s, shp_path=%s,"
            "date_col=%s, region_col=%s, mean_temperature_col=%s, health_outcome_col=%s, pm_2_5_col=%s, "
            "wildfire_lag=%s, temperature_lag=%s, spline_temperature_lag    =%s, spline_temp_dof=%s, scale_factor=%s, rr_by_region=%s",
            join_wildfire_data, ncdf_path, shp_path, date_col, region_col,
            mean_temperature_col, health_outcome_col, pm_2_5_col,
            wildfire_lag, temperature_lag, spline_temperature_lag, spline_temp_dof,
            scale_factor, rr_by_region
        )

        # 4. Convert the health_df to dict or send as raw data
        health_data_records = health_df.to_dict(orient="records")

        # 5. Build the JSON payload for the R API call
        payload = {
            # Instead of local file path, we embed the data
            "health_path": health_data_records,
            "join_wildfire_data": join_wildfire_data,
            "ncdf_path": ncdf_path,
            "shp_path": shp_path,
            "date_col": date_col,
            "region_col": region_col,
            "mean_temperature_col": mean_temperature_col,
            "health_outcome_col": health_outcome_col,
            "wildfire_lag": wildfire_lag,
            "temperature_lag": temperature_lag,
            "spline_temperature_lag": spline_temperature_lag,
            "spline_temperature_degrees_freedom": spline_temp_dof,
            "scale_factor_wildfire_pm": scale_factor,
            "calc_relative_risk_by_region": (
                True if str(rr_by_region).lower() == "true" else False
                if rr_by_region is not None else False),
            "pm_2_5_col": pm_2_5_col,
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
    Example new indicator for air pollution impacts on health.
    Similar logic to the heat/cold endpoint.
    """
    if request.method == "POST":
        file = request.files.get("file")
        if not file:
            return jsonify(error="No file uploaded"), 400

        df = pd.read_csv(file).fillna("")
        # Gather form data
        outcome_col = request.form.get("outcome_col")
        pm25_col = request.form.get("pm25_col")
        region_col = request.form.get("region_col")

        payload = {
            "input_csv_path_": df.to_dict(orient="records"),
            "dependent_col_": outcome_col,
            "pm25_col_": pm25_col,
            "region_col_": region_col,
            # Possibly other form inputs
        }

        result = call_r_api(payload, endpoint="airpollution")
        return jsonify(result)

    # If GET, show a specialized form if you want
    return render_template("indicator_form.html", indicator="Air Pollution")

# -----------------------------------------------------------------------------
# 5. Waterborne diseases indicator -diarrhoea
# -----------------------------------------------------------------------------


@indicator_bp.route("/waterborne", methods=["GET", "POST"])
def waterborne_indicator():
    """
    Waterborne Diseases: Diarrhea.
    """
    if request.method == "POST":
        health_file = request.files.get("health_file")
        climate_file = request.files.get("climate_file")
        geo_zip_file = request.files.get("geo_zip_file")
        if not health_file or not climate_file or not geo_zip_file:
            return jsonify(error="Missing one or more required files (health, climate, geo_zip_file)"), 400

        health_df = pd.read_csv(health_file).fillna("")
        climate_df = pd.read_csv(climate_file).fillna("")

        # Required fields
        region_col = request.form.get("region_col")
        district_col = request.form.get("district_col")
        date_col = request.form.get("date_col")
        year_col = request.form.get("year_col")
        month_col = request.form.get("month_col")
        diarrhea_case_col = request.form.get("diarrhea_case_col")
        tot_pop_col = request.form.get("tot_pop_col")
        tmin_col = request.form.get("tmin_col")
        tmean_col = request.form.get("tmean_col")
        tmax_col = request.form.get("tmax_col")
        rainfall_col = request.form.get("rainfall_col")
        r_humidity_col = request.form.get("r_humidity_col")
        runoff_col = request.form.get("runoff_col")
        geometry_col = request.form.get("geometry_col")
        spi_col = request.form.get("spi_col")
        basis_matrices_choices = request.form.get("basis_matrices_choices")
        if isinstance(basis_matrices_choices, str):
            basis_matrices_choices = basis_matrices_choices.split(",")
        elif not isinstance(basis_matrices_choices, list):
            basis_matrices_choices = None
        inla_params = request.form.get("inla_param")
        if isinstance(inla_params, str):
            inla_params = inla_params.split(",")
        elif not isinstance(inla_params, list):
            inla_params = None
        param_term = request.form.get("param_term")
        level = request.form.get("level")
        param_threshold = request.form.get("param_threshold", 1)
        try:
            param_threshold = float(param_threshold)
        except Exception:
            param_threshold = 1

        max_lag = request.form.get("max_lag", 2)
        try:
            max_lag = int(max_lag)
        except Exception:
            max_lag = 2

        health_records = health_df.to_dict(orient="records")
        climate_records = climate_df.to_dict(orient="records")

        payload = {
            "health_data": health_records,
            "climate_data": climate_records,
            "region_col": region_col,
            "district_col": district_col,
            "date_col": date_col,
            "year_col": year_col,
            "month_col": month_col,
            "diarrhea_case_col": diarrhea_case_col,
            "tot_pop_col": tot_pop_col,
            "tmin_col": tmin_col,
            "tmean_col": tmean_col,
            "tmax_col": tmax_col,
            "rainfall_col": rainfall_col,
            "r_humidity_col": r_humidity_col,
            "runoff_col": runoff_col,
            "geometry_col": geometry_col,
            "spi_col": spi_col,
            "max_lag": max_lag,
            "basis_matrices_choices": basis_matrices_choices,
            "inla_param": inla_params,
            "param_term": param_term,
            "level": level,
            "param_threshold": param_threshold,
            "save_csv": True,
            "save_fig": True
        }

        # Replace empty strings
        for (nm, val) in payload.items():
            if isinstance(val, str) and val.strip() == "":
                payload[nm] = None

        # Create output directory (temp)
        tmp_dir = create_tmp_dir()
        payload["output_dir"] = os.path.abspath(tmp_dir)

        # Create files part of POST
        files = {
            "geo_zip_file": (geo_zip_file.filename, geo_zip_file.stream, geo_zip_file.mimetype)
        }

        api_url = current_app.config.get("API_URL", "http://127.0.0.1:8000")
        if api_url.endswith("/"):
            api_url = api_url[:-1]
        diarrhea_url = f"{api_url}/diarrhea"
        try:
            # Send JSON payload as a string in 'data', and the ZIP as file
            api_response = requests.post(
                diarrhea_url,
                data={"payload": jsonify(payload).get_data(as_text=True)},
                files=files,
                verify=False
            )
            # Use centralized error handling for API responses
            api_result = handle_api_response(api_response, endpoint="/diarrhea")
            if isinstance(api_result, APIErrorResponse):
                return make_error_response(api_result)

            result_json = api_result.json()
        except requests.RequestException as e:
            current_app.logger.error(f"Error calling diarrhea R API: {e}")
            return jsonify(error=f"R API call failed: {str(e)}"), 502

        return jsonify(result_json=result_json)

# -----------------------------------------------------------------------------
# 6. Vectorborne diseases indicator - malaria
# -----------------------------------------------------------------------------


@indicator_bp.route("/vectorborne", methods=["GET", "POST"])
def vectorborne_indicator():
    """
    Vectorborne Diseases: Malaria.
    """
    if request.method == "POST":
        health_file = request.files.get("health_file")
        climate_file = request.files.get("climate_file")
        geo_zip_file = request.files.get("geo_zip_file")
        if not health_file or not climate_file or not geo_zip_file:
            return jsonify(error="Missing one or more required files (health, climate, geo_zip_file)"), 400

        health_df = pd.read_csv(health_file).fillna("")
        climate_df = pd.read_csv(climate_file).fillna("")

        # Required fields
        fields = {
        "region_col": request.form.get("region_col"),
        "district_col": request.form.get("district_col"),
        "date_col": request.form.get("date_col"),
        "year_col": request.form.get("year_col"),
        "month_col": request.form.get("month_col"),
        "malaria_case_col": request.form.get("malaria_case_col"),
        "tot_pop_col": request.form.get("tot_pop_col"),
        "tmin_col": request.form.get("tmin_col"),
        "tmean_col": request.form.get("tmean_col"),
        "tmax_col": request.form.get("tmax_col"),
        "rainfall_col": request.form.get("rainfall_col"),
        "r_humidity_col": request.form.get("r_humidity_col"),
        "runoff_col": request.form.get("runoff_col"),
        "geometry_col": request.form.get("geometry_col") or "geometry",
        "spi_col": request.form.get("spi_col"),
        "param_term": request.form.get("param_term"),
        "level": request.form.get("level")
        }
        

        # Check for missing required fields
        mandatory_keys = [
            "region_col",
            "district_col",
            "year_col",
            "month_col",
            "malaria_case_col",
            "tot_pop_col",
            "tmin_col",
            "tmean_col",
            "tmax_col",
            "rainfall_col",
            "r_humidity_col",
            "runoff_col",
            "param_term",
            "level"
        ]

        missing = [key for key in mandatory_keys if not fields[key]]
        if missing:
            return jsonify(
                error=f"Missing required parameters in the form: {', '.join(missing)}"
            ), 400

        # Backwards-compat: if template still uses 'cvh_col', map it to ndvi_col
        ndvi_col = request.form.get("ndvi_col")
        if not ndvi_col:
            ndvi_col = request.form.get("cvh_col")
        # Multi-value fields
        basis_matrices_choices = request.form.get("basis_matrices_choices")
        if isinstance(basis_matrices_choices, str):
            # Split and filter out empty strings
            basis_matrices_choices = [s.strip() for s in basis_matrices_choices.split(",") if s.strip()]
        # Ensure it is None if empty list or keep if populated
        if not basis_matrices_choices:
            basis_matrices_choices = None

        inla_params = request.form.get("inla_param")
        if isinstance(inla_params, str):
            inla_params = [s.strip() for s in inla_params.split(",") if s.strip()]
        if not inla_params:
            inla_params = None

        # Numeric parameters
        param_threshold = request.form.get("param_threshold", 1)
        try:
            param_threshold = float(param_threshold)
        except Exception:
            param_threshold = 1.0

        max_lag = request.form.get("max_lag", 2)
        try:
            max_lag = int(max_lag)
        except Exception:
            max_lag = 2

        # Convert to records (as R reads as list or path)
        health_records = health_df.to_dict(orient="records")
        climate_records = climate_df.to_dict(orient="records")

        # Build the payload for malaria R API endpoint
        payload = {
            "health_data": health_records,
            "climate_data": climate_records,
            **fields,
            # "region_col": region_col,
            # "district_col": district_col,
            # "date_col": date_col,
            # "year_col": year_col,
            # "month_col": month_col,
            # "malaria_case_col": malaria_case_col,
            # "tot_pop_col": tot_pop_col,
            # "tmin_col": tmin_col,
            # "tmean_col": tmean_col,
            # "tmax_col": tmax_col,
            # "rainfall_col": rainfall_col,
            # "r_humidity_col": r_humidity_col,
            # "runoff_col": runoff_col,
            # "geometry_col": geometry_col,
            # "spi_col": spi_col,
            "ndvi_col": ndvi_col,
            "max_lag": max_lag,
            "basis_matrices_choices": basis_matrices_choices,
            "inla_param": inla_params,
            # "param_term": param_term,
            # "level": level,
            "param_threshold": param_threshold,
            # "save_csv": True,  # No longer exposed on the R side
            # "save_fig": True  # No longer exposed on the R side
        }

        # Replace empty strings with None for cleaner JSON
        for (nm, val) in payload.items():
            if isinstance(val, str) and val.strip() == "":
                payload[nm] = None
        # Create output directory (temp)
        tmp_dir = create_tmp_dir()
        payload["output_dir"] = os.path.abspath(tmp_dir)

        # Create files part of POST to add to JSON payload
        files = {
            "geo_zip_file": (
                geo_zip_file.filename,
                geo_zip_file.stream,
                geo_zip_file.mimetype
            )
        }

        api_url = current_app.config.get("API_URL", "http://127.0.0.1:8000")
        if api_url.endswith("/"):
            api_url = api_url[:-1]
        malaria_url = f"{api_url}/malaria"
        try:
            # Send JSON payload as a string in 'data', and the ZIP as file
            api_response = requests.post(
                malaria_url,
                data={"payload": jsonify(payload).get_data(as_text=True)},
                files=files,
                verify=False
            )
            # Use centralized error handling for API responses
            api_result = handle_api_response(api_response, endpoint="/malaria")
            if isinstance(api_result, APIErrorResponse):
                return make_error_response(api_result)

            result_json = api_result.json()
            # Extract csvs for plotting
            rr_df = result_json.get("rr_df", [])
            an_ar_results = result_json.get("an_ar_results", [])

            # Add logging so user knows which results were returned
            current_app.logger.info(
                "R /malaria returned rr_df rows: %s | an_ar_results keys: %s",
                len(rr_df),
                list(an_ar_results.keys()) if isinstance(
                    an_ar_results, dict) else type(an_ar_results)
            )
        except requests.RequestException as e:
            # Include response text if available
            resp_text = ""
            if e.response is not None:
                resp_text = e.response.text
                current_app.logger.error(
                    "Error calling malaria R API: %s; response: %s",
                    str(e),
                    resp_text
                )
            else:
                current_app.logger.error(
                    "Error calling malaria R API: %s", str(e))

            return (jsonify(
                error=f"R API call failed",
                details=str(e),
                response=resp_text or None
            ), 502)
        # Return the result JSON to the UI
        return jsonify(rr_df=rr_df, an_ar_results=an_ar_results)

    # If GET, show a form to upload CSV and specify parameters
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
