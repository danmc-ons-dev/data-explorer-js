def test_html_routes(client):
    """
    GIVEN a Flask app instance
    WHEN each route to a HTML endpoint is requested
    THEN check each route request was successful
    """

    endpoints = [
        "/",
        "/data_explorer",
        "/data_plots",
        "/framework",
        "/indicator_calculators",
        "/upload",
        "/about",
        "/search",
        "/r_package",
    ]

    response_status_codes = {}

    for endpoint in endpoints:
        response = client.get(endpoint)
        response_status_codes[endpoint] = response.status_code

    broken_endpoints = [
        key for key, value in response_status_codes.items() if value != 200
    ]

    if broken_endpoints == None:
        broken_endpoints = "None"

    assert all(
        value == 200 for value in response_status_codes.values()
    ), f"HTML endpoints(s) {broken_endpoints} broken."


def test_r_package_route_available_when_full_ui_disabled(client):
    client.application.config["ENABLE_FULL_UI"] = False

    response = client.get("/r_package")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "R Package" in html
    assert "CRAN Package Page" in html
    assert 'install.packages("climatehealth")' in html
    assert "coming soon" not in html.lower()
