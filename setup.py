from setuptools import setup

setup(
    name="data_explorer",
    packages=["data_explorer"],
    version="0.9.22",
    include_package_data=True,
    install_requires=[
        "flask",
        "psycopg2",
        "pandas",
        "geopandas",
        "pyyaml",
        "plotly",
        "seaborn",
        "pytest",
        "python-dotenv",
        "SQLAlchemy",
        "flask-session",
        "requests",
    ],
)
