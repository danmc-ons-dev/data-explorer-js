from functools import wraps
from flask import Blueprint, current_app, session, redirect, request, url_for, jsonify
from requests_oauthlib import OAuth2Session
import requests

auth_bp = Blueprint("auth_bp", __name__)


# def login_required(f):
#     @wraps(f)
#     def decorated_function(*args, **kwargs):
#         if "user" not in session:
#             session["next_url"] = request.url
#             return redirect(url_for("login"))
#         return f(*args, **kwargs)

#     return decorated_function


@auth_bp.before_app_request
def load_logged_in_user():
    user = session.get("user")
    if not user:
        session["next_url"] = request.url
        redirect(url_for("auth_bp.login"))


def get_oauth_session(state=None, token=None):
    """
    Helper function to create and return an OAuth2Session
    for Keycloak or any OpenID provider.
    """
    # Retrieve config settings from current_app.config
    client_id = current_app.config["CLIENT_ID"]
    client_secret = current_app.config["CLIENT_SECRET"]
    redirect_uri = current_app.config["REDIRECT_URI"]
    oidc_config = get_oidc_config()

    return OAuth2Session(
        client_id,
        redirect_uri=redirect_uri,
        scope=["openid", "profile", "email"],
        state=state,
        token=token,
        auto_refresh_url=oidc_config.get("token_endpoint"),
        auto_refresh_kwargs={"client_id": client_id, "client_secret": client_secret},
        token_updater=lambda t: session.update({"oauth_token": t}),
    )


def get_oidc_config():
    """
    Fetch OIDC configuration from Keycloak (Could also cache this to avoid repeated calls).
    """
    keycloak_url = current_app.config["KEYCLOAK_URL"]
    realm_name = current_app.config["REALM_NAME"]

    oidc_config_url = (
        f"{keycloak_url}/realms/{realm_name}/.well-known/openid-configuration"
    )
    try:
        resp = requests.get(
            oidc_config_url, verify=False
        )  # Change verify in deployment
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        current_app.logger.error(f"Failed to load OIDC config: {str(e)}")
        raise


@auth_bp.route("/login")
def login():
    """
    Initiate the OAuth2 login flow.
    Stores state in session, then redirects user to Keycloak's login page.
    """
    oauth = get_oauth_session()
    oidc_config = get_oidc_config()
    authorization_endpoint = oidc_config["authorization_endpoint"]

    authorization_url, state = oauth.authorization_url(authorization_endpoint)

    # Store state in session (for callback validation)
    session["oauth_state"] = state
    session.modified = True

    # Optionally handle a 'next' parameter if you want to remember the original URL
    next_url = request.args.get("next")
    if next_url:
        session["next_url"] = next_url
        session.modified = True

    current_app.logger.debug(f"Login initiated with state={state}")
    return redirect(authorization_url)


@auth_bp.route("/callback")
def callback():
    """
    Handle the OAuth2 callback from the Keycloak (or OIDC) provider.
    Validates state and fetches tokens, user info, etc.
    """
    expected_state = session.get("oauth_state")
    if not expected_state:
        current_app.logger.error("No 'oauth_state' in session. Redirecting to /login.")
        return redirect(url_for("auth_bp.login"))

    current_state = request.args.get("state")
    if current_state != expected_state:
        current_app.logger.error(f"State mismatch: {expected_state} != {current_state}")
        return redirect(url_for("auth_bp.login"))

    try:
        oauth = get_oauth_session(state=expected_state)
        oidc_config = get_oidc_config()
        token_endpoint = oidc_config["token_endpoint"]

        token = oauth.fetch_token(
            token_endpoint,
            authorization_response=request.url,
            client_secret=current_app.config["CLIENT_SECRET"],
            verify=True,  # or verify=True with valid SSL
        )
        session["oauth_token"] = token
        session.modified = True

        # Optionally fetch user info
        userinfo_endpoint = oidc_config["userinfo_endpoint"]
        userinfo = oauth.get(userinfo_endpoint, verify=False).json()
        session["user"] = userinfo
        session.modified = True

        # If we stored a 'next_url', redirect there; else go to home
        next_url = session.pop("next_url", url_for("main_bp.index"))
        return redirect(next_url)

    except Exception as e:
        current_app.logger.error(f"Callback error: {str(e)}")
        return redirect(url_for("auth_bp.login"))


@auth_bp.route("/logout")
def logout():
    """
    Clears the session and redirects user to Keycloak's end_session endpoint,
    if available, to fully log out from the identity provider.
    """
    oidc_config = get_oidc_config()
    end_session_endpoint = oidc_config.get("end_session_endpoint")

    # Clear local session
    token = session.pop("oauth_token", None)
    id_token = token["id_token"] if token else None
    session.clear()

    if not end_session_endpoint or not id_token:
        current_app.logger.warning(
            "No end_session_endpoint or ID token. Local session cleared."
        )
        return redirect(url_for("main_bp.index"))

    redirect_uri = url_for("main_bp.index", _external=True)
    client_id = current_app.config["CLIENT_ID"]

    # Build the logout URL
    logout_url = (
        f"{end_session_endpoint}"
        f"?client_id={client_id}"
        f"&id_token_hint={id_token}"
        f"&post_logout_redirect_uri={redirect_uri}"
    )
    return redirect(logout_url)


@auth_bp.route("/clear-session")
def clear_session():
    """
    Example debug route to manually clear user session data.
    """
    session.clear()
    return "Session cleared. You have been logged out locally."
