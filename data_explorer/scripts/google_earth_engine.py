import ee

ee.Authenticate()
ee.Initialize()

# Example script to load and visualize ERA5 climate reanalysis parameters in
# Google Earth Engine

# Daily mean 2m air temperature
era5_2mt = (
    ee.ImageCollection('ECMWF/ERA5/DAILY')
    .select('mean_2m_air_temperature')
    .filter(ee.Filter.date('2019-07-01', '2019-07-31'))
)