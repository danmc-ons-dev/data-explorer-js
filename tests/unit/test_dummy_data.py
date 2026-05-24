import json
import pandas as pd
from data_explorer.routes.data_routes import get_dataframe


def test_dummy_data_on(client):
    """
    GIVEN A Flask app instance
    WHEN the dummy data toggle is on
    THEN check session variable is True and the message is correct
    """
    response = client.post("/dummy_data_toggle", data={"dummy_toggle": "on"})
    assert response.status_code == 200
    with client.session_transaction() as session:
        assert session["global_dummy_data"] is True


def test_dummy_data_off(client):
    """
    GIVEN A Flask app instance
    WHEN the dummy data toggle is off
    THEN check session variable is False and the message is correct
    """
    response = client.post("/dummy_data_toggle", data={"dummy_toggle": "off"})
    assert response.status_code == 200
    with client.session_transaction() as session:
        assert session["global_dummy_data"] is False


def test_get_dataframe_dummy_on(app):
    """
    GIVEN A SQL request to the dummy dataset
    WHEN the dummy data session is True
    THEN check the dataframe returns the dummy data
    """
    with app.app_context():
        df_on = get_dataframe("temperature", dummy_data=True)

    assert (
        df_on.exposure_type.unique() == "temperature"
    ), "The wrong dummy data has been loaded."
    assert df_on.dummy_data.unique() == 1, "The wrong dummy data has been loaded."


def test_get_dataframe_dummy_off(app):
    """
    GIVEN A SQL request to the dummy dataset
    WHEN the dummy data session is False
    THEN check the dataframe returns no data
    """
    with app.app_context():
        df_off = get_dataframe("temperature", dummy_data=False)

    assert (df_off.dummy_data.unique() == 0) or len(
        df_off
    ) == 0, "Real data has been loaded instead of dummy data."


# Work on session variables in init for global dummy data
def test_plot_indicator_data(client):
    """
    GIVEN A request to plot data from the database
    WHEN the dummy data session is True
    THEN check the queried dataframes are in the correct format
    """
    response = client.get("/plot_indicator_data/temperature")
    my_response = response.get_json()

    full_query_json = json.loads(my_response["full_query"])
    full_query_df = pd.json_normalize(full_query_json)

    grouped_query_json = json.loads(my_response["grouped_query"])
    grouped_query_df = pd.json_normalize(grouped_query_json)

    assert len(full_query_df.columns) > 0, "No data in full query dataframe."
    assert len(grouped_query_df.columns) > 0, "No data in grouped query dataframe."
    assert full_query_df.exposure_type.unique() == "temperature"
    assert all(
        item in ["exposure_value", "geography", "outcome_value"]
        for item in grouped_query_df.columns
    ), "Columns in grouped query not correct."
