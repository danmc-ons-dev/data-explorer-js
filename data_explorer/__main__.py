from data_explorer import create_app

if __name__ == "__main__":

    app = create_app()
    # Respect the DEBUG_MODE configuration instead of hardcoding
    app.run(host="0.0.0.0", port=5001, debug=app.config.get("DEBUG_MODE", False))
