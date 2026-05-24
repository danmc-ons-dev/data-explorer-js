# data_explorer/routes/data_routes.py

import datetime
import io
import json
import os
import pathlib
import requests
import shutil
import tempfile
import zipfile

import numpy as np
import pandas as pd
import geopandas as gpd
import sqlalchemy as db
import seaborn as sns
from flask import (
    Blueprint,
    render_template,
    request,
    session,
    jsonify,
    current_app,
    send_file,
    abort
)

data_bp = Blueprint("data_bp", __name__)

# Hash allowlists for top-level tab sections.
# These lists drive both header link visibility and hash-based access checks.
# When ENABLE_FULL_UI is false we use LIVE_* lists; when true we use DEV_* lists.

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
    # "descriptive-statistics",
    # "heat-and-cold",
    "extreme-weather-events",
    # "waterborne-diseases",
    # "vectorborne-diseases",
    "mental-health"
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
    "mental-health"
]


def get_allowed_framework_hashes():
    if not current_app.config.get("ENABLE_FULL_UI", False):
        return LIVE_FRAMEWORK_HASHES
    return DEV_FRAMEWORK_HASHES


def get_allowed_indicator_calculator_hashes():
    if not current_app.config.get("ENABLE_FULL_UI", False):
        return LIVE_INDICATOR_CALCULATOR_HASHES
    return DEV_INDICATOR_CALCULATOR_HASHES


@data_bp.app_context_processor
def inject_allowed_framework_hashes():
    return {
        "allowed_framework_hashes": get_allowed_framework_hashes(),
        "allowed_indicator_calculator_hashes": get_allowed_indicator_calculator_hashes(),
    }


# Set up Shapefile
current_dir = os.path.dirname(os.path.abspath(__file__))

countries_path = os.path.join(
    current_dir, "..", "static", "data", "shp", "countries_incl_uk.shp"
)
regions_path = os.path.join(
    current_dir, "..", "static", "data", "shp", "RGN_DEC_2022_EN_BUC.shp"
)

TOOLTIPS_PATH = pathlib.Path(current_dir) / ".." / \
    "static" / "data" / "csv" / "tooltips.json"


def load_tooltips():
    if not TOOLTIPS_PATH.exists():
        return {}
    try:
        with TOOLTIPS_PATH.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except json.JSONDecodeError:
        return {}
    tooltips = {}
    for key, value in raw.items():
        if isinstance(value, list):
            tooltips[key] = value[0] if value else ""
        else:
            tooltips[key] = value
    return tooltips


# Countries shapefile
countries = gpd.read_file(countries_path)
countries.rename(columns={"COUNTRY": "geography"}, inplace=True)

eng_wales_regions = gpd.read_file(regions_path)
eng_wales_regions.to_crs("epsg:4326", inplace=True)


def get_db_engine():
    """
    Builds and returns a SQLAlchemy engine using
    config values from current_app.config.
    """
    host = current_app.config.get("SQL_HOST", "localhost")
    port = current_app.config.get("SQL_PORT", 5432)
    user = current_app.config.get("SQL_USER", "postgres")
    password = current_app.config.get("SQL_PASSWORD", "password")
    dbname = current_app.config.get("SQL_DBNAME", "app_db")

    engine_str = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}"
    return db.create_engine(engine_str)

# @data_bp.route("/")
# def index():
#     """
#     Home or index route. Shows the main landing page.
#     """
#     user_info = session.get("user")
#     return render_template("index.html", user_info=user_info)


@data_bp.route("/about")
def about():
    """
    Simple 'About' page to render about.html template.
    """
    return render_template("about.html")


@data_bp.route("/data_plots")
def data_plots():
    """
    Renders a page with data visualizations (graphs, charts).
    """
    return render_template("data_plots.html")


@data_bp.route("/framework")
def framework():
    """
    Renders a page describing the conceptual framework
    (e.g., how climate indicators link to health outcomes).
    """
    allowed_hashes = get_allowed_framework_hashes()
    return render_template("framework.html", allowed_hashes=allowed_hashes)


@data_bp.route("/indicator_calculators")
def indicator_calculators():
    """
    Protected page that lists or provides access to
    various climate-health calculators.
    Redirects to /login if user is not authenticated.
    """
    # if "user" not in session:
    #     # Save the desired URL so we can redirect after login
    #     session["next_url"] = request.url
    #     session.modified = True
    #     return redirect(url_for("auth_bp.login"))
    return render_template(
        "indicator_calculators.html",
        tooltips=load_tooltips(),
        allowed_indicator_hashes=get_allowed_indicator_calculator_hashes(),
    )


@data_bp.route("/data_explorer")
def data_explorer():
    """
    Renders a data exploration interface.
    """
    session["global_dummy_data"] = False
    return render_template("data_explorer.html")


@data_bp.route("/dummy_data_toggle", methods=["POST"])
def dummy_data_toggle():
    """
    Toggles dummy data usage (on/off) via a POST form.
    Stores the state in session and reloads page.
    """
    if request.form.get("dummy_toggle") == "on":
        session["global_dummy_data"] = True
        message = "Using dummy data"
    else:
        session["global_dummy_data"] = False
        message = "Using real data"

    return render_template(
        "data_explorer.html",
        message=message,
        global_dummy_data=session["global_dummy_data"],
    )


@data_bp.route("/get_shapefile_joined")
def get_shapefile_joined():
    """
    Example route returning a GeoJSON of some
    joined or processed shapefile data.
    """
    # Adjust path as needed:
    shp_path = os.path.join(
        current_app.root_path, "static", "data", "shp", "temp_averages_joined.shp"
    )
    joined_data = gpd.read_file(shp_path)
    return joined_data.to_json()


@data_bp.route("/get_averages/")
def get_averages():
    """
    Returns JSON of average temperature data or similar CSV-based stats.
    """
    # Example CSV paths:
    temps_path = os.path.join(current_app.root_path, "static",
                              "data", "csv", "long_country_ann_temp_change.csv")
    averages_path = os.path.join(
        current_app.root_path, "static", "data", "csv", "temp_averages.csv")
    all_averages_path = os.path.join(
        current_app.root_path, "static", "data", "csv", "temp_all_averages.csv")

    temps_df = pd.read_csv(temps_path)
    averages_df = pd.read_csv(averages_path)
    all_averages_df = pd.read_csv(all_averages_path)

    temps_json = temps_df.to_json(orient="records")
    averages_json = averages_df.to_json(orient="records")
    all_averages_json = all_averages_df.to_json(orient="records")

    return jsonify(
        temps=temps_json,
        averages=averages_json,
        all_averages=all_averages_json
    )


@data_bp.route("/populate_indicator_dropdown/")
def populate_indicator_dropdown():
    """
    Example route that queries the DB for a list of
    indicators (exposure types) and returns JSON.
    """
    engine = get_db_engine()
    global_dummy_data = session.get("global_dummy_data", False)

    # Adjust query logic based on dummy_data usage:
    if global_dummy_data is True:
        query = """
        SELECT DISTINCT indicator.exposure_type
        FROM indicator NATURAL JOIN metadata
        WHERE metadata.dummy_data = 1;
        """
    else:
        query = """
        SELECT DISTINCT indicator.exposure_type
        FROM indicator NATURAL JOIN metadata
        WHERE metadata.dummy_data = 0;
        """
    with engine.connect() as conn:
        df = pd.read_sql_query(query, conn)

    unique_rows = df["exposure_type"].dropna().sort_values().tolist()
    return jsonify(unique_rows)


def get_dataframe(selected_row, dummy_data=False):
    """
    Helper function to retrieve a DataFrame from the DB
    for a given 'selected_row' (indicator), optionally
    filtering dummy vs. real data.
    """
    if current_app.config.get("TESTING"):
        data_path = pathlib.Path(
            current_app.root_path) / "static" / "data" / "csv" / "dummy_indicator_data.csv"
        df = pd.read_csv(data_path)
        df = df[df["exposure_type"] == selected_row].copy()
        df["dummy_data"] = 1 if dummy_data else 0
        return df

    engine = get_db_engine()
    if dummy_data:
        query = """
        SELECT data.*, indicator.exposure_type, indicator.exposure_unit, indicator.outcome_unit,
               metadata.dummy_data
        FROM data
        NATURAL JOIN indicator
        NATURAL JOIN metadata
        WHERE indicator.exposure_type = %s AND metadata.dummy_data = 1;
        """
    else:
        query = """
        SELECT data.*, indicator.exposure_type, indicator.exposure_unit, indicator.outcome_unit,
               metadata.dummy_data
        FROM data
        NATURAL JOIN indicator
        NATURAL JOIN metadata
        WHERE indicator.exposure_type = %s AND metadata.dummy_data = 0;
        """
    with engine.connect() as conn:
        df = pd.read_sql_query(query, conn, params=(selected_row,))
    return df


@data_bp.route("/plot_indicator_data/<selected_row>")
def plot_indicator_data(selected_row):
    """
    Example route to get full & grouped JSON for plotting
    data of a given indicator/exposure.
    """
    dummy_data = session.get("global_dummy_data", False)
    df = get_dataframe(selected_row, dummy_data)

    # pivot / melt as needed for plotting
    pivoted = df.pivot_table(
        index="exposure_value",
        columns="geography",
        values="outcome_value",
        aggfunc="mean",
    ).reset_index()
    pivoted_melt = pivoted.melt(
        id_vars="exposure_value", var_name="geography", value_name="outcome_value"
    )

    full_query_json = df.to_json(orient="records")
    grouped_query_json = pivoted_melt.to_json(orient="records")
    return jsonify(full_query=full_query_json, grouped_query=grouped_query_json)


@data_bp.route("/get_shapefile_data/<selected_row>")
def get_shapefile_data(selected_row):
    """
    Example of pairing shapefile geometry with the DB data
    for a chosen indicator.
    """
    dummy_data = session.get("global_dummy_data", False)
    df = get_dataframe(selected_row, dummy_data)

    # Suppose you have a countries GeoDataFrame loaded somewhere
    # or stored in memory, else load from a shapefile
    shp_path = os.path.join(
        current_app.root_path, "static", "data", "shp", "countries.shp"
    )
    countries_gdf = gpd.read_file(shp_path)

    # Filter by the unique geographies in the data
    filtered_shp = countries_gdf[countries_gdf["geography"].isin(
        df["geography"].unique())]

    # Join relevant columns:
    df_min = df[["geography", "sub_geography",
                 "start_year", "end_year"]].drop_duplicates()
    joined_shp = filtered_shp.merge(
        df_min, on="geography", how="left").drop_duplicates("geometry")

    return joined_shp.to_json()


@data_bp.route("/upload", methods=["GET"])
def upload():
    """
    Shows an upload form (upload.html).
    """
    return render_template("upload.html")


@data_bp.route("/reshape_input_data", methods=["POST", "GET"])
def reshape_input_data():
    """
    Handles CSV upload, extracting form fields,
    writing data + metadata to the DB, etc.
    """
    if request.method == "POST":
        file = request.files["file"]
        df = pd.read_csv(file)

        # get inputs from web form
        indicator_name = request.form.get("indicatorName")
        subgeo = request.form.get("subgeo")
        subgeotype = request.form.get("subgeotype")
        country = request.form.get("country")
        exposure = request.form.get("exposure")
        outcome = request.form.get("outcome")
        lower = request.form.get("lower")
        higher = request.form.get("higher")
        timescale = request.form.get("timescale")
        start = request.form.get("start")
        end = request.form.get("end")
        permissions = request.form.get("permissions")
        sex = request.form.get("sex")
        age = request.form.get("age")
        socio = request.form.get("socio")
        urban = request.form.get("urban")

        # parse dates if needed
        start_day, start_month, start_year = start[8:10], start[5:7], start[0:4]
        end_day, end_month, end_year = end[8:10], end[5:7], end[0:4]
        if timescale != "Daily":
            # If not daily, zero-out day/month
            start_day = end_day = None
            start_month = end_month = None

        engine = get_db_engine()
        conn = engine.connect()

        # 1. fetch the indicator_id
        ind_query = "SELECT * FROM indicator WHERE indicator_name = %s"
        indicator_df = pd.read_sql_query(
            ind_query, conn, params=(indicator_name,))
        indicator_id = indicator_df["indicator_id"].iloc[0] if not indicator_df.empty else None

        # 2. fetch last_dataset_id from metadata
        meta_query = "SELECT * FROM metadata"
        metadata_df = pd.read_sql_query(meta_query, conn)
        last_dataset_id = metadata_df["indicator_dataset_id"].max(
        ) if not metadata_df.empty else 0

        # 3. insert new metadata row
        upload_metadata = pd.DataFrame({
            "indicator_dataset_id": [last_dataset_id + 1],
            "uploader_id": [1],  # link to user ID
            "verifier_id": [1],  # link to verifier ID
            "data_permissions": [permissions],
            "upload_date_time": [datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
            "upload_n_rows": [len(df)],
            "dataset_doi": [None],
            "approval_status": ["unapproved"],
            "approved_date_time": [None],
            "dummy_data": [0],
        })
        upload_metadata.to_sql(
            "metadata", conn, if_exists="append", index=False)

        # 4. fetch last_data_row_id from data table
        data_query = "SELECT * FROM data"
        data_df = pd.read_sql_query(data_query, conn)
        last_data_row_id = data_df["data_row_id"].max(
        ) if not data_df.empty else 0

        # rename columns if user provided them
        df = df.replace({np.nan: None})
        if subgeo:
            df.rename(columns={subgeo: "sub_geography"}, inplace=True)
        else:
            df["sub_geography"] = None
        if subgeotype:
            df.rename(columns={subgeotype: "sub_geography_type"}, inplace=True)
        else:
            df["sub_geography_type"] = None
        if exposure:
            df.rename(columns={exposure: "exposure_value"}, inplace=True)
        else:
            df["exposure_value"] = None
        if outcome:
            df.rename(columns={outcome: "outcome_value"}, inplace=True)
        else:
            df["outcome_value"] = None
        if lower:
            df.rename(columns={lower: "outcome_value_lower"}, inplace=True)
        else:
            df["outcome_value_lower"] = None
        if higher:
            df.rename(columns={higher: "outcome_value_higher"}, inplace=True)
        else:
            df["outcome_value_higher"] = None
        if sex:
            df.rename(columns={sex: "sex"}, inplace=True)
        else:
            df["sex"] = None
        if age:
            df.rename(columns={age: "age_group"}, inplace=True)
        else:
            df["age_group"] = None
        if socio:
            df.rename(columns={socio: "socioeconomic_group"}, inplace=True)
        else:
            df["socioeconomic_group"] = None
        if urban:
            df.rename(columns={urban: "degree_urbanisation"}, inplace=True)
        else:
            df["degree_urbanisation"] = None

        # Build the final DataFrame for insertion
        row_ids = list(range(last_data_row_id + 1,
                       last_data_row_id + len(df) + 1))
        data_to_insert = pd.DataFrame({
            "data_row_id": row_ids,
            "indicator_dataset_id": last_dataset_id + 1,
            "indicator_id": indicator_id,
            "exposure_value": df["exposure_value"],
            "outcome_value": df["outcome_value"],
            "outcome_value_lower": df.get("outcome_value_lower", None),
            "outcome_value_higher": df.get("outcome_value_higher", None),
            "start_year": start_year,
            "start_month": start_month,
            "start_day": start_day,
            "end_year": end_year,
            "end_month": end_month,
            "end_day": end_day,
            "geography": country,
            "sub_geography": df["sub_geography"],
            "sub_geography_type": df["sub_geography_type"],
            "sex": df["sex"],
            "age_group": df["age_group"],
            "socioeconomic_group": df["socioeconomic_group"],
            "degree_urbanisation": df["degree_urbanisation"],
        })

        data_to_insert.to_sql("data", conn, if_exists="append", index=False)
        conn.close()

        message = "success"
        return render_template("upload.html", message=message)

    # If GET, just show the same page
    return render_template("upload.html")


# functions for DLNM desc stats saving
def cleanup_tmp_dir(path: pathlib.Path):
    """Delete a temporary directory if it still exists."""
    if os.path.exists(path):
        shutil.rmtree(path)


def zip_directory_as_bytes(path: pathlib.Path):
    """Zip a directory and return it as encoded bytes (utf-8)."""
    if not (os.path.exists(path)):
        return None
    zip_bytes = io.BytesIO()
    with zipfile.ZipFile(zip_bytes, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(path):
            for file_ in files:
                fpath = os.path.join(root, file_)
                archive_name = os.path.relpath(fpath, start=path)
                zf.write(fpath, archive_name)
    zip_bytes.seek(0)
    return zip_bytes


@data_bp.route("/get_zip_file", methods=["POST"])
def get_zip_file():
    """Get a zip file for use in JS."""
    # Parse request
    data = request.json
    path = data["path"]
    fname = data["fname"]
    if "desc_stats_temporary" not in str(path):
        return None
    # Convert directory to bytes (zip format)
    zip_bytes = zip_directory_as_bytes(path)
    if (len(fname.split(".")) < 2):
        fname = f"{fname}.zip"
    elif (fname.split(".")[1] != "zip"):
        fname = f"{fname.split('.')[0]}.zip"
    # cleanup_tmp_dir(path)
    return send_file(zip_bytes, mimetype="application/zip", as_attachment=True, download_name=fname)


# @data_bp.route("/dlnm", methods=["GET", "POST"])
# def dlnm():
#     """
#     Example route that calls an external R-based API
#     for a distributed lag non-linear model (or other
#     specialized climate-health regression).
#     """
#     if request.method == "POST":
#         file = request.files["file"]
#         df = pd.read_csv(file).fillna("")
#         # gather form inputs
#         deaths = request.form.get("deaths")
#         time = request.form.get("time")
#         temp = request.form.get("temp")
#         pop = request.form.get("pop")
#         country = request.form.get("country")
#         subgeo = request.form.get("subgeo")
#         ind1 = request.form.get("ind1")
#         ind2 = request.form.get("ind2")
#         ind3 = request.form.get("ind3")
#         ind4 = request.form.get("ind4")
#         # disagg = request.form.get("disagg")
#         meta = request.form.get("meta")
#         rr_dist = int(request.form.get("rr_dist") or 0)
#         output_year = int(request.form.get("output_year") or 0)
#         lag = int(request.form.get("lag") or 21)
#         seasonal = int(request.form.get("seasonal") or 8)

#         # Convert booleans
#         # disagg_val = "TRUE" if disagg == "true" else "FALSE"
#         meta_val = "TRUE" if meta == "true" else "FALSE"
#         independent_cols = None if ind1 == "" else [ind1, ind2, ind3, ind4]

#         # Build payload
#         df_records = df.to_dict(orient="records")
#         subgeo = None if subgeo.strip().lower() in ["", None] else subgeo
#         payload = {
#             "input_csv_path_": df_records,
#             "meta_analysis_": meta_val,
#             "by_region_": True if subgeo else False,
#             "RR_distribution_length_": rr_dist,
#             "output_year_": output_year,
#             "dependent_col_": deaths,
#             "time_col_": time,
#             "region_col_": subgeo,
#             "temp_col_": temp,
#             "population_col_": pop,
#             "country_col_": country,
#             "indepedent_cols_": independent_cols,
#             "varfun_": "bs",
#             "vardegree_": 2,
#             "lag_": int(lag),
#             "lagnk_": 3,
#             "dfseas_": seasonal,
#             "nsim__": 1000
#         }

#         # Call the R-based API
#         # heat_api_url = current_app.config.get("HEAT_API_URL", "http://127.0.0.1:5671/regression")
#         heat_api_url = current_app.config.get("HEAT_API_URL", "http://127.0.0.1:5671/temperature")
#         auth_user = current_app.config.get("API_USERNAME", "")
#         auth_pass = current_app.config.get("API_PASSWORD", "")

#         try:
#             import requests
#             api_response = requests.post(
#                 heat_api_url,
#                 json=payload,
#                 headers={"Content-Type": "application/json"},
#                 auth=(auth_user, auth_pass),
#                 verify=False,
#             )
#             json_response = api_response.json()
#             # current_app.logger.info(json_response)
#             # Do any post-processing, e.g. merging with shapefiles
#             # or categorizing results
#             # return jsonify(json_response=json_response)

#             ######

#             # Get relative risk and attributable rate
#             output_df = pd.json_normalize(json_response[0])
#             # temp_df = pd.json_normalize(json_response[1])
#             # anregions_publication = pd.json_normalize(json_response[2])
#             # antot_bind = pd.json_normalize(json_response[3])
#             arregions_pub = pd.json_normalize(json_response[4])


#             #######

#             # Get key data columns and rename spatial column for spatial merge
#             arregions_pub["regions"] = arregions_pub["_row"]
#             high_heat = arregions_pub[["regions", "high_heat"]]
#             high_heat.rename(columns={"regions": "RGN22NM"}, inplace=True)

#             high_cold = arregions_pub[["regions", "high_cold"]]
#             high_cold.rename(columns={"regions": "RGN22NM"}, inplace=True)

#             df_upper = output_df[output_df.temp > 0]
#             max_rr = df_upper.groupby("regions")["rel_risk"].max().reset_index()
#             max_rr.rename(columns={"regions": "RGN22NM"}, inplace=True)


#             return jsonify(
#                 json_response=json_response,
#                 joined_gdf=pd.DataFrame().to_json()
#             )

#         except Exception as e:
#             current_app.logger.error(f"Error calling R-based API: {str(e)}")
#             return jsonify(error=str(e)), 500

#     # If GET, show a basic form or page
#     return render_template("dlnm_form.html")

# @data_bp.route("/wildfires", methods=["GET", "POST"])
# def wildfires_indicator():
#     """
#     Endpoint for uploading wildfire + health data,
#     then calling the R-based /wildfires endpoint.
#     """
#     if request.method == "POST":
#         # 1. Grab the uploaded file (health data CSV)
#         file = request.files.get("file")
#         if not file:
#             return jsonify(error="No health data file uploaded"), 400

#         # 2. Convert the CSV to a Pandas DataFrame (optional, for validation)
#         health_df = pd.read_csv(file)
#         health_df = health_df.fillna("")

#         # 3. Gather form data for user-provided parameters
#         join_wildfire_data = request.form.get("join_wildfire_data", "false").lower() == "true"
#         ncdf_path = request.form.get("ncdf_path") or None
#         shp_path = request.form.get("shp_path") or None

#         date_col = request.form.get("date_col", "date")
#         region_col = request.form.get("region_col")
#         mean_temperature_col = request.form.get("mean_temperature_col", "tmean")
#         health_outcome_col = request.form.get("health_outcome_col", "health_outcome")
#         pm_2_5_col = request.form.get("pm_25_col")

#         wildfire_lag = int(request.form.get("wildfire_lag") or 3)
#         temperature_lag = int(request.form.get("temperature_lag") or 1)
#         spline_temperature_lag = int(request.form.get("spline_temperature_lag") or 0)
#         spline_temp_df = int(request.form.get("spline_temperature_degrees_freedom") or 6)

#         scale_factor = float(request.form.get("scale_factor_wildfire_pm") or 10)
#         rr_by_region = request.form.get("relative_risk_by_region")

#         # 4. Convert the health_df to dict or send as raw data
#         health_data_records = health_df.to_dict(orient="records")

#         # 5. Build the JSON payload for the R API call
#         payload = {
#             "health_path": health_data_records,  # Instead of local file path, we embed the data
#             "join_wildfire_data": join_wildfire_data,
#             "ncdf_path": ncdf_path,
#             "shp_path": shp_path,
#             "date_col": date_col,
#             "region_col": region_col if region_col not in ["", None] else None,
#             "mean_temperature_col": mean_temperature_col,
#             "health_outcome_col": health_outcome_col,
#             "pm_2_5_col": pm_2_5_col,
#             "wildfire_lag": wildfire_lag,
#             "temperature_lag": temperature_lag,
#             "spline_temperature_lag": spline_temperature_lag,
#             "spline_temperature_degrees_freedom": spline_temp_df,
#             "scale_factor_wildfire_pm": scale_factor,
#             "calc_relative_risk_by_region": rr_by_region
#         }

#         # 6. Call the R-based /wildfires endpoint
#         wildfires_url = current_app.config.get("WILDFIRES_URL", "http://127.0.0.1:8000/wildfires")
#         #return {"message": "success"}

#         try:
#             api_response = requests.post(
#                 wildfires_url,
#                 json=payload,
#                 headers={"Content-Type": "application/json"},
#                 verify=False
#             )
#             api_response.raise_for_status()  # Raises HTTPError if status >= 400
#             result_json = api_response.json()
#         except requests.RequestException as e:
#             current_app.logger.error(f"Error calling wildfires R API: {e}")
#             return jsonify(error=f"R API call failed: {str(e)}"), 500

#         # 7. Return or render results
#         return jsonify(rr_results=result_json[0], an_af_results=result_json[1])

#     # If GET, show a form to upload CSV and specify parameters
#     return render_template("wildfires_form.html")

# @data_bp.route("/mental_health", methods=["GET", "POST"])
# def mental_health():
#     """
#     Example route that calls an external R-based API
#     for a distributed lag non-linear model (or other
#     specialized climate-health regression).
#     """

#     if request.method == "POST":

#         file = request.files.get("file")
#         if not file:
#             return jsonify(error="No health data file uploaded"), 400

#         df = pd.read_csv(file)
#         df = df.fillna("")

#         # gather form inputs
#         date_col = request.form.get("date_col")
#         region_col = request.form.get("region_col") or None
#         temperature_col = request.form.get("temperature_col")
#         health_outcome_col = request.form.get("health_outcome_col")
#         var_fun = request.form.get("var_fun") or "ns"
#         var_dof = int(request.form.get("var_dof") or 4)
#         lag_fun = request.form.get("lag_fun") or "ns"
#         lag_dof = int(request.form.get("lag_dof") or 4)
#         lag_days = int(request.form.get("lag_days") or 3)

#         # Build payload
#         df_records = df.to_dict(orient="records")
#         payload = {
#             "data_path": df_records,
#             "date_col": date_col,
#             "region_col": region_col,
#             "temperature_col": temperature_col,
#             "health_outcome_col": health_outcome_col,
#             "var_fun": var_fun,
#             "var_dof": var_dof,
#             "lag_fun": lag_fun,
#             "lag_dof": lag_dof,
#             "lag_days": lag_days
#         }

#         # Call the R-based API
#         mental_health_url = current_app.config.get("MENTAL_HEALTH_API_URL", "http://127.0.0.1:8000/mental_health")
#         auth_user = current_app.config.get("API_USERNAME", "")
#         auth_pass = current_app.config.get("API_PASSWORD", "")

#         try:
#             import requests
#             api_response = requests.post(
#                 mental_health_url,
#                 json=payload,
#                 headers={"Content-Type": "application/json"},
#                 auth=(auth_user, auth_pass),
#                 verify=False,
#             )

#             json_response = api_response.json()
#             current_app.logger.info(json_response)

#             # Placeholder for MH data
#             data = pd.DataFrame(json_response)

#             # Melt the dataset so that each temperature has one row
#             melted = data.melt(value_vars=data.columns[1:], id_vars=["Temperature"])

#             # create individual cols for region/RR category (low, high, fit)
#             melted["RR_cat"] = melted["variable"].apply(lambda x: x.split("_")[0])
#             melted["disagg"] = melted["variable"].apply(lambda x: "_".join(x.split("_")[1:]))

#             # drop combined value
#             melted.drop("variable", inplace=True, axis=1)

#             # pivot the table in order to get all RR values for each region on one row
#             pivot = melted.pivot_table(
#                 index=["Temperature", "disagg"], columns="RR_cat", values="value", aggfunc='first'
#             ).reset_index().reset_index(drop=True)

#             # remove index name
#             pivot.columns.name = None

#             pivot["disagg"] = pivot["disagg"].apply(lambda x: x.replace("_", " ").title())

#             json_data = pivot.to_json(orient="records")

#             return jsonify(
#                 json_response=json_data
#             )

#         except Exception as e:
#             current_app.logger.error(f"Error calling R-based API: {str(e)}")
#             return jsonify(error=str(e), status=500)

#     # If GET, show a basic form or page
#     return render_template("mentalhealth_form.html")
