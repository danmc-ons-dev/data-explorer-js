from flask import Flask, render_template, jsonify
import psycopg2
import pandas as pd
import geopandas as gpd
import yaml
import plotly.graph_objects as go
import plotly.io as pio

# Added this to accommodate docker-compose patterns
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()


app = Flask(__name__, template_folder = 'app/templates', static_folder = 'app/static')

# Countries shapefile
countries = gpd.read_file('app/static/data/shp/countries_incl_uk.shp')
countries.rename(columns={'COUNTRY':'geography'}, inplace = True)

def load_config_from_yaml():
    try:
        with open('config.yml', 'r') as file:
            return yaml.safe_load(file)
    except (FileNotFoundError, yaml.YAMLError):
        return None

def load_config_from_env():
    load_dotenv()
    return {
        'host': os.getenv('HOST'),
        'dbname': os.getenv('DBNAME'),
        'user': os.getenv('USER'),
        'password': os.getenv('PASSWORD'),
        'port': os.getenv('PORT')
    }

# Try loading from YAML first
config = load_config_from_yaml()

# If YAML loading fails, fall back to .env file
if not config:
    config = load_config_from_env()

# Extract variables
host = config.get('host')
dbname = config.get('dbname')
user = config.get('user')
password = config.get('password')
port = config.get('port')

@app.route('/')
def index():
    # Render main page
    return render_template('index.html')

@app.route('/data_explorer')
def data_explorer():
    return render_template('data_explorer.html')

@app.route('/data_plots')
def data_plots():
    return render_template('data_plots.html')

@app.route('/framework')
def framework():
    return render_template('framework.html')

@app.route('/indicator_calculators')
def indicator_calculators():
    return render_template('indicator_calculators.html')

@app.route('/upload')
def upload():
    return render_template('upload.html')

@app.route('/about')
def about():
    return render_template('about.html')
    
# Pair geographies in indicator data dropdown selection with countries shapefile
@app.route('/get_shapefile_joined')
def get_shapefile_joined():
    joined_data = gpd.read_file('app/static/data/shp/temp_averages_joined.shp')
    return joined_data.to_json()

# Populate dropdown with indicators in database
@app.route('/get_averages/')
def get_averages():
    
    temps = pd.read_csv('app/static/data/csv/long_country_ann_temp_change.csv')
    averages = pd.read_csv('app/static/data/csv/temp_averages.csv')
    all_averages = pd.read_csv('app/static/data/csv/temp_all_averages.csv')

    temps = temps.to_json(orient = 'records')
    averages = averages.to_json(orient = 'records')
    all_averages = all_averages.to_json(orient = 'records')

    return jsonify(temps = temps, averages = averages, all_averages = all_averages)

# Populate dropdown with indicators in database
@app.route('/populate_indicator_dropdown/')
def populate_indicator_dropdown():
    conn = psycopg2.connect(host = host, dbname = dbname, user = user, password = password, port = port)
    query = 'SELECT DISTINCT indicator_id FROM data;'
    df = pd.read_sql_query(query, conn)
    conn.close()
    unique_rows = df['indicator_id'].tolist()
    unique_rows = sorted(unique_rows)
    return jsonify(unique_rows)

def get_dataframe(selected_row):
    # Get data from SQL
    conn = psycopg2.connect(host = host, dbname = dbname, user = user, password = password, port = port)
    query = f'SELECT * FROM data WHERE indicator_id = {selected_row};'
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

# Get data for given indicator dropdown and split by geography
@app.route('/plot_indicator_data/<selected_row>')
def plot_indicator_data(selected_row):
    df = get_dataframe(selected_row)

    # Make plot for each geography
    traces = []
    for geography in df.geography.unique():
        df_geo = df[df['geography'] == geography]
        traces.append(go.Scatter(x = df_geo['exposure_value'], y = df_geo['outcome_value'], mode = 'lines+markers', name = geography,
                                 line_width = 5, marker = dict(size = 10)))
        
    layout = go.Layout(title = f'Indicator {df.indicator_id.unique()[0]}', paper_bgcolor = "white", plot_bgcolor = "white",
                       xaxis_title = f'{df.exposure_type.unique()[0]} ({df.exposure_unit.unique()[0]})', 
                       yaxis_title = f'{df.outcome_type.unique()[0]} ({df.outcome_unit.unique()[0]})',
                       font_family = "Arial, sans-serif", font_size = 25, font_color = 'black')
    
    fig = go.Figure(data = traces, layout = layout)
    graphjson = pio.to_json(fig)
    return jsonify(graphjson = graphjson)

# Pair geographies in indicator data dropdown selection with countries shapefile
@app.route('/get_shapefile_data/<selected_row>')
def get_shapefile_data(selected_row):
    df = get_dataframe(selected_row)
    filtered_data = countries[countries['geography'].isin(df.geography.unique())]
    return filtered_data.to_json()

if __name__ == '__main__':
    app.run(debug = True)