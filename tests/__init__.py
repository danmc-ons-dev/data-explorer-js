def test_shapefile_load(client):
    response = client.get('/')
    assert response.status_code == 200