import io
import json


def _make_csv():
    return "date,health_outcome,tmean,region,pm\n2020-01-01,5,10,North,1.2\n"


def test_wildfires_post_success(client, monkeypatch):
    """
    WHEN posting a valid CSV to /wildfires
    THEN we return the proxied R payload and send the expected JSON to the R API
    """

    captured = {}

    def fake_post(url, json, headers=None, verify=None):
        captured["url"] = url
        captured["json"] = json

        class Resp:
            status_code = 200
            text = ""

            def json(self):
                return {
                    "RR_results": ["rr"],
                    "AF_AN_results": ["af_an"],
                    "AR_PM_monthly": ["ar_pm"],
                }

        return Resp()

    monkeypatch.setattr(
        "data_explorer.routes.indicator_routes.requests.post", fake_post)

    dummy_payload = {
        "file": (io.BytesIO(_make_csv().encode()), "wildfire.csv"),
        "join_wildfire_data": "false",
        "ncdf_path": "",
        "shp_path": "",
        "date_col": "date",
        "region_col": "region",
        "mean_temperature_col": "tmean",
        "health_outcome_col": "death",
        "wildfire_lag": "3",
        "temperature_lag": "1",
        "spline_temperature_degrees_freedom": "6",
        "scale_factor_wildfire_pm": "10",
        "relative_risk_by_region": "true",
        "pm_25_col": "pm",
    }

    resp = client.post(
        "/wildfires",
        data=dummy_payload,
        content_type="multipart/form-data",
    )

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["rr_results"] == ["rr"]
    assert payload["an_af_results"] == ["af_an"]
    assert payload["ar_pm_results"] == ["ar_pm"]

    # Verify the app called the R endpoint with the param names
    # wildfire_do_analysis() actually accepts.
    sent = captured["json"]
    assert sent["health_path"]
    assert sent["join_wildfire_data"] is False
    assert sent["ncdf_path"] is None
    assert sent["shp_path"] is None
    assert sent["date_col"] == "date"
    assert sent["region_col"] == "region"
    assert sent["mean_temperature_col"]
    assert sent["health_outcome_col"]
    assert sent["wildfire_lag"] == 3
    assert sent["temperature_lag"] == 1
    assert sent["spline_temperature_degrees_freedom"] == 6
    assert sent["scale_factor_wildfire_pm"] == 10
    assert sent["calculate_by_region"] is True
    assert sent["pm_2_5_col"] == "pm"
    # spline_temperature_lag is not part of wildfire_do_analysis() and must not leak through.
    assert "spline_temperature_lag" not in sent
    # Newly exposed optional cols default to None when the form omits them.
    assert sent["population_col"] is None
    assert sent["rh_col"] is None
    assert sent["wind_speed_col"] is None


def test_wildfires_missing_file(client):
    """
    WHEN no file is provided
    THEN /wildfires returns 400
    """
    resp = client.post("/wildfires", data={},
                       content_type="multipart/form-data")
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "No health data file uploaded"


def test_wildfires_api_error(client, monkeypatch):
    """
    WHEN the R API responds with non-200
    THEN /wildfires surfaces a 500 error with structured error response
    """

    def fake_post(url, json, headers=None, verify=None):
        class Resp:
            status_code = 500
            text = "boom"
            headers = {}

            def json(self):
                raise ValueError("No JSON")

        return Resp()

    monkeypatch.setattr(
        "data_explorer.routes.indicator_routes.requests.post", fake_post)

    resp = client.post(
        "/wildfires",
        data={
            "file": (io.BytesIO(_make_csv().encode()), "wildfire.csv"),
            "region_col": "region",
            "pm_25_col": "pm",
            "relative_risk_by_region": "true",
        },
        content_type="multipart/form-data",
    )

    assert resp.status_code == 500
    body = resp.get_json()
    # New structured error format
    assert body["error"] is True
    assert body["error_type"] == "api_error"
    assert body["status_code"] == 500


def test_mental_health_post_success(client, monkeypatch):

    captured = {}

    client.application.config["API_URL"] = "http://r-api/"

    def fake_post(url, json=None, headers=None, verify=None):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["verify"] = verify

        class Resp:
            status_code = 200
            text = ""

            def json(self):
                return {
                    "rr_results": [
                        {
                            "Area": "National",
                            "Temperature": 20,
                            "RR": 1.1,
                            "RR_upper_CI": 1.3,
                            "RR_lower_CI": 0.9,
                        }
                    ],
                    "qaic_results": {"qaic": 123},
                    "vif_results": {"vif": 2.0},
                    "attr_yr_list": [{"year": 2020, "attr": 0.1}],
                    "attr_mth_list": [{"month": 1, "attr": 0.2}],
                }

            def raise_for_status(self):
                return None

        return Resp()

    monkeypatch.setattr(
        "data_explorer.routes.indicator_routes.requests.post", fake_post)

    resp = client.post(
        "/mental_health",
        data={
            "file": (io.BytesIO(_make_csv().encode()), "mh.csv"),
            "date_col": "date",
            "region_col": "region",
            "temperature_col": "tmean",
            "population_col": "population",
            "health_outcome_col": "health_outcome",
            "save_fig": "true",
            "save_csv": "false",
        },
        content_type="multipart/form-data",
    )

    assert resp.status_code == 200
    body = resp.get_json()

    # Endpoint returns mapped RR rows (list), not boolean
    assert isinstance(body["rr_results"], list)
    assert len(body["rr_results"]) == 1
    assert body["rr_results"][0] == {
        "disagg": "National",
        "Temperature": 20,
        "RRfit": 1.1,
        "RRhigh": 1.3,
        "RRlow": 0.9,
    }

    assert body["qaic_results"] == {"qaic": 123}
    assert body["vif_results"] == {"vif": 2.0}
    assert body["attr_yr_list"] == [{"year": 2020, "attr": 0.1}]
    assert body["attr_mth_list"] == [{"month": 1, "attr": 0.2}]

    # payload sent to R API
    sent = captured["json"]
    assert captured["url"] == "http://r-api/mental_health"
    assert captured["headers"] == {"Content-Type": "application/json"}
    assert captured["verify"] is False

    assert isinstance(sent["data_path"], list)
    assert sent["data_path"]  # non-empty records list
    assert sent["date_col"] == "date"
    assert sent["region_col"] == "region"
    assert sent["temperature_col"] == "tmean"
    assert sent["population_col"] == "population"
    assert sent["health_outcome_col"] == "health_outcome"
    assert sent["independent_cols"] is None
    assert sent["control_cols"] is None

    # forced by endpoint for API calls
    assert sent["save_fig"] is False
    assert sent["save_csv"] is False


def test_mental_health_missing_file(client):
    resp = client.post("/mental_health", data={},
                       content_type="multipart/form-data")
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "No file uploaded"


def test_mental_health_api_error(client, monkeypatch):
    """
    WHEN the R API responds with non-200
    THEN /mental_health surfaces a 500 error with structured error response
    """

    def fake_post(url, json=None, headers=None, verify=None):
        class Resp:
            status_code = 500
            text = "boom"
            headers = {}

            def json(self):
                raise ValueError("No JSON")

        return Resp()

    monkeypatch.setattr(
        "data_explorer.routes.indicator_routes.requests.post", fake_post
    )

    resp = client.post(
        "/mental_health",
        data={
            "file": (io.BytesIO(_make_csv().encode()), "mh.csv"),
            "date_col": "date",
            "region_col": "region",
            "temperature_col": "tmean",
            "population_col": "population",
            "health_outcome_col": "health_outcome",
        },
        content_type="multipart/form-data",
    )

    assert resp.status_code == 500
    body = resp.get_json()
    # New structured error format
    assert body["error"] is True
    assert body["error_type"] == "api_error"
    assert body["status_code"] == 500


def test_vectorborne_post_success(client, monkeypatch):
    captured = {}

    def fake_post(url, json=None, headers=None, verify=None):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers

        class Resp:
            status_code = 200
            headers = {}
            text = ""

            def json(self):
                # R API returns rr_df and an_ar_results
                return {"rr_df": [{"rr": 1.5}], "an_ar_results": {"region": "data"}}

        return Resp()

    monkeypatch.setattr(
        "data_explorer.routes.indicator_routes.requests.post", fake_post
    )

    resp = client.post(
        "/vectorborne",
        data={
            "health_file": (io.BytesIO(_make_csv().encode()), "health.csv"),
            "climate_file": (io.BytesIO(_make_csv().encode()), "climate.csv"),
            "geo_zip_file": (io.BytesIO(b"zip"), "shapes.zip"),
            "region_col": "region",
            "district_col": "district",
            "date_col": "date",
            "year_col": "year",
            "month_col": "month",
            "malaria_case_col": "cases",
            "tot_pop_col": "pop",
            "tmin_col": "tmin",
            "tmean_col": "tmean",
            "tmax_col": "tmax",
            "rainfall_col": "rain",
            "r_humidity_col": "humid",
            "runoff_col": "runoff",
            "geometry_col": "geom",
            "spi_col": "spi",
            "ndvi_col": "ndvi",
            "max_lag": "2",
            "basis_matrices_choices": "bm1,bm2",
            "inla_param": "p1,p2",
            "param_term": "term",
            "level": "country",
            "param_threshold": "2.5",
        },
        content_type="multipart/form-data",
    )

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["rr_df"] == [{"rr": 1.5}]
    assert body["an_ar_results"] == {"region": "data"}

    # Pure JSON now — no multipart payload wrapper, no separate file upload.
    sent = captured["json"]
    assert captured["headers"] == {"Content-Type": "application/json"}
    assert sent["health_data_path"], "health CSV records sent under R param name"
    assert sent["climate_data_path"], "climate CSV records sent under R param name"
    assert sent["region_col"] == "region"
    assert sent["district_col"] == "district"
    # Malaria's "malaria_case_col" form field maps to R's single case_col arg.
    assert sent["case_col"] == "cases"
    assert sent["ndvi_col"] == "ndvi"
    assert sent["basis_matrices_choices"] == ["bm1", "bm2"]
    assert sent["inla_param"] == ["p1", "p2"]
    assert sent["param_threshold"] == 2.5
    # geo_zip_file is now base64-encoded inside the JSON body.
    import base64
    assert base64.b64decode(sent["map_zip_b64"]) == b"zip"


def test_vectorborne_missing_file(client):
    resp = client.post(
        "/vectorborne",
        data={
            "health_file": (io.BytesIO(_make_csv().encode()), "health.csv"),
            # missing climate_file and geo_zip_file
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    assert "Missing one or more required files" in resp.get_json()["error"]


def test_vectorborne_api_error(client, monkeypatch):
    """
    WHEN the R API responds with non-200
    THEN /vectorborne surfaces an error with structured error response
    """

    def fake_post(url, json=None, headers=None, verify=None):
        class Resp:
            status_code = 500
            text = "boom"
            headers = {}

            def json(self):
                raise ValueError("No JSON")

        return Resp()

    monkeypatch.setattr(
        "data_explorer.routes.indicator_routes.requests.post", fake_post
    )

    # Provide all mandatory fields to reach the API call
    resp = client.post(
        "/vectorborne",
        data={
            "health_file": (io.BytesIO(_make_csv().encode()), "malaria_health.csv"),
            "climate_file": (io.BytesIO(_make_csv().encode()), "malaria_climate.csv"),
            "geo_zip_file": (io.BytesIO(b"dummyzip"), "shp.zip"),
            "region_col": "region",
            "district_col": "district",
            "date_col": "date",
            "year_col": "year",
            "month_col": "month",
            "malaria_case_col": "malaria",
            "tot_pop_col": "pop",
            "tmin_col": "tmin",
            "tmean_col": "tmean",
            "tmax_col": "tmax",
            "rainfall_col": "rain",
            "r_humidity_col": "humid",
            "runoff_col": "runoff",
            "param_term": "term",
            "level": "country",
        },
        content_type="multipart/form-data",
    )

    assert resp.status_code == 500
    body = resp.get_json()
    # New structured error format
    assert body["error"] is True
    assert body["error_type"] == "api_error"
    assert body["status_code"] == 500


def test_airpollution_post_success(client, monkeypatch):
    """
    WHEN posting a valid CSV to /airpollution with the full set of column mappings
    THEN the route forwards a JSON payload matching air_pollution_do_analysis()
    AND returns the meta/analysis/power/descriptive keys back to the UI.
    """
    captured = {}

    def fake_post(url, json=None, headers=None, verify=None):
        captured["url"] = url
        captured["json"] = json

        class Resp:
            status_code = 200
            text = ""

            def json(self):
                return {
                    "meta_results": {"region": "pooled"},
                    "analysis_results": {"WHO": [{"af": 0.1}]},
                    "power_results": {"WHO": {"power": 0.8}},
                    "descriptive_stats": None,
                }

            def raise_for_status(self):
                return None

        return Resp()

    monkeypatch.setattr(
        "data_explorer.routes.indicator_routes.requests.post", fake_post)

    resp = client.post(
        "/airpollution",
        data={
            "file": (io.BytesIO(_make_csv().encode()), "air.csv"),
            "date_col": "date",
            "region_col": "region",
            "pm25_col": "pm25",
            "deaths_col": "deaths",
            "population_col": "population",
            "humidity_col": "humidity",
            "precipitation_col": "precipitation",
            "tmax_col": "tmax",
            "wind_speed_col": "wind_speed",
            "max_lag": "14",
            "df_seasonal": "6",
            "moving_average_window": "3",
            "attr_thr": "95",
            "reference_standards": '[{"value": 15, "name": "WHO"}]',
            "include_national": "true",
            "run_descriptive": "false",
            "run_power": "true",
        },
        content_type="multipart/form-data",
    )

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["meta_results"] == {"region": "pooled"}
    assert body["analysis_results"] == {"WHO": [{"af": 0.1}]}
    assert body["power_results"] == {"WHO": {"power": 0.8}}

    sent = captured["json"]
    # All column mappings reach R under the names the R function accepts.
    assert isinstance(sent["data_path"], list) and sent["data_path"]
    assert sent["date_col"] == "date"
    assert sent["region_col"] == "region"
    assert sent["pm25_col"] == "pm25"
    assert sent["deaths_col"] == "deaths"
    assert sent["population_col"] == "population"
    assert sent["humidity_col"] == "humidity"
    assert sent["precipitation_col"] == "precipitation"
    assert sent["tmax_col"] == "tmax"
    assert sent["wind_speed_col"] == "wind_speed"
    # Tuning params are coerced to native types and reference_standards parsed.
    assert sent["max_lag"] == 14
    assert sent["df_seasonal"] == 6
    assert sent["moving_average_window"] == 3
    assert sent["attr_thr"] == 95.0
    assert sent["reference_standards"] == [{"value": 15, "name": "WHO"}]
    assert sent["include_national"] is True
    assert sent["run_descriptive"] is False
    assert sent["run_power"] is True
    # save_outputs is forced to False in API mode regardless of form input.
    assert sent["save_outputs"] is False


def test_airpollution_missing_file(client):
    resp = client.post(
        "/airpollution", data={}, content_type="multipart/form-data")
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "No file uploaded"
