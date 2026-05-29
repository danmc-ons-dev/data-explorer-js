import pytest
from data_explorer import create_app
from flask_session import Session

@pytest.fixture
def app():
    app = create_app()
    app.config.update(
        TESTING=True,
        SESSION_PERMANENT=False,
        SESSION_TYPE="filesystem",
        ENABLE_FULL_UI=True,
    )
    Session(app)
    return app

@pytest.fixture
def client(app):
    with app.test_client() as client:
        with client.session_transaction() as session:
            session["global_dummy_data"] = True
        yield client
