import requests
import numpy as np

def generate_renewable_prices(lat=22.57, lon=88.36):   # default: Kolkata
    
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=shortwave_radiation,wind_speed_10m,temperature_2m&forecast_days=1"

    data = requests.get(url).json()
    
    solar = data["hourly"]["shortwave_radiation"]
    wind = data["hourly"]["wind_speed_10m"]
    
    hours = 24
    base_price = 3.0
    
    prices = []

    for h in range(hours):
        
        # normalize solar and wind
        solar_factor = solar[h] / 800          # typical max irradiance
        wind_factor = (wind[h] / 12)**3        # wind power relation
        
        renewable_supply = solar_factor + wind_factor
        
        # demand curve (evening peak)
        demand = 0.6 + 0.4*np.sin((h-18)/12*np.pi)**2
        
        price = base_price * demand / (renewable_supply + 0.3)
        
        prices.append(float(round(price,2)))
    
    return prices


print(generate_renewable_prices())