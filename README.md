# Climate and Health Data Explorer

---

## Description

A code repository for the development of the ONS-Wellcome Trust climate and health data platform.


## App Configuration: 

There are two supported ways to configure the application. One is by using a `config.yml` file with the following example configuration: 

```
run_migrations: "true"
debug_mode: "true"
dummy_mode: "true"
host: "localhost"
dbname: "data-explorer-db"
user: "myuser"
password: "mypassword"
port: 5432
API_URL: "http://localhost:8000"
```

Alternatively, you can use environment variables as follows:

* `RUN_MIGRATIONS`: Set to true if the application will run migrations automatically (default); otherwise set to false if migrations will be run manually.
* `DUMMY_MODE`: Set to true if the application should load dummy data; otherwise set to false (default).
* `API_URL`: Base URL of the climatehealth R API (e.g. `http://localhost:8000`). The indicator calculators call endpoints under this base URL.

... need to add examples

### File and folder descriptions

- `data_explorer/__main__.py`: Entrypoint that initiates the Flask app (run via `python -m data_explorer`).
- `config.yml`: Local configuration including database credentials and `API_URL`. Hidden from the repository — copy `config.yml.local.example` and customise. The `.env` pattern is also supported.
- `archive`: Contains archived scripts.
- `data_explorer`: Cotains all of the files for running Flask app.
- `data_explorer\__init__.py`: Contains the Flask app object and endpoints.
- `data_explorer\templates\`: Contains the HTML templates.
- `data_explorer\static\`: Contains the files and scripts used by the templates.
- `data_explorer\static\assets`: Contains images and tables for the templates.
- `data_explorer\static\css`: Contains CSS scripts for the templates. Note that Tailwind is primarily used for styling inline.
- `data_explorer\static\data`: Contains data for the templates.
- `data_explorer\static\js`: Contains Javascript scripts for the templates.

---

## Usage

- Navigate to root of the app. Run `python -m data_explorer` from the console to start the application.
- The indicator calculators (`indicator_calculators.js`) will only work locally if the API found in the [climatehealth package](https://github.com/onssoschi/climatehealth) is running and reachable at the configured `API_URL`. [Email us](climate.health@ons.gov.uk) if you require access to this repo.

---

## Setting up a development database

The following commmand will create a database for development purposes:

```
docker compose up db
```

## Building the containers and running in Rancher Desktop (containerd mode)

To build the migrations container, run `nerdctl --namespace k8s.io build -f migrations.Dockerfile -t data-explorer-migrations:latest .`

To build the data-explorer container, run `nerdctl --namespace k8s.io build -f data-explorer.Dockerfile -t data-explorer:latest .`

To deploy, run `kubectl apply -k ./k8s/resources`

## Authors

Climate and Global Health, Office for National Statistics
[Euan Soutter, Antony Brown, Paul Slocombe, Vijendra Ingole, Kenechi Omeke, Charlie Browning]

Statistics Division, Department of Economics and Social Affairs, United Nations
[Sean Lovell]
