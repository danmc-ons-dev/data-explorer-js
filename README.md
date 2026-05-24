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
heat_api_url: "http://localhost:8000"
```

Alternatively, you can use environment variables as follows: 

* `RUN_MIGRATIONS`: Set to true if the application will run migrations automatically (default); otherwise set to false if migrations will be run manually. 
* `LOAD_DUMMY_DATA`: Set to true if the application should load dummy data (default); otherwise set to false. 

... need to add examples

### File and folder descriptions

- `run.py`: Initiates Flask app.
- `config.yml`: Credentials for PostgreSQL database (see app.py). Hidden in repository. Populate your own config.yml with database credentials. Can also use the .env pattern interchangeably.
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
- 'indicator_calculators.js' will only work locally if the API found in the [climatehealth package](https://github.com/onssoschi/climatehealth) is running. [Email us](climate.health@ons.gov.uk) if you require access to this repo and the associated [climatehealth pipelines](https://github.com/onssoschi/climatehealth_pipelines) repo.
- 'data_explorer.js' will only work if the PostgreSQL database is available locally and a config.yml file has been created to store its credentials (see **init**.py).

<!-- ## Project status

Next steps:

- Modify the database SQL migration file; add column in metadata table for dummy data
- Modify the write_dummy_data function to record that it is dummy data
- Modify the endpoint to select data based on dummy data condition
- Add toggle in frontend for dummy data use; query parameter based on toggle -->

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
