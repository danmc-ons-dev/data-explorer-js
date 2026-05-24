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
