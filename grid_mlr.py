"""Multiple Linear Regression (MLR) Model for Day-Ahead Grid Electricity Price Prediction.

This module loads historical 1-year hourly market data from `historical_grid_prices.csv`
and fits a Multiple Linear Regression model using:
- Cyclical hour features (sin/cos representation of 24h day)
- Ambient Temperature (°C)
- Regional Grid Demand Factor
- Renewable Availability (Solar Irradiance & Wind Speed)
"""

import os
import numpy as np
import pandas as pd
import requests
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error

CSV_PATH = os.path.join(os.path.dirname(__file__), "historical_grid_prices.csv")


def _load_training_dataset():
    """Loads training data from historical_grid_prices.csv.
    
    Returns X (features) and y (grid price in ₹/kWh).
    """
    if not os.path.exists(CSV_PATH):
        raise FileNotFoundError(f"Historical dataset file not found at: {CSV_PATH}")
        
    df = pd.read_csv(CSV_PATH)
    
    # Calculate demand_factor if demand_mw is present
    if "demand_factor" not in df.columns and "demand_mw" in df.columns:
        df["demand_factor"] = df["demand_mw"] / 500.0
        
    feature_cols = ["sin_hour", "cos_hour", "temperature_c", "demand_factor", "solar_wm2", "wind_ms"]
    X = df[feature_cols].values
    y = df["grid_price_inr_kwh"].values
    
    return X, y, len(df)


def train_mlr_model():
    """Trains the LinearRegression model on historical_grid_prices.csv."""
    X_train, y_train, dataset_size = _load_training_dataset()
    
    model = LinearRegression()
    model.fit(X_train, y_train)
    
    y_pred = model.predict(X_train)
    
    feature_names = ["sin(Hour)", "cos(Hour)", "Temperature (°C)", "Demand Factor", "Solar (W/m²)", "Wind Speed (m/s)"]
    coefficients = dict(zip(feature_names, [round(c, 4) for c in model.coef_]))
    
    metrics = {
        "dataset_source": "historical_grid_prices.csv",
        "sample_count": dataset_size,
        "r2_score": float(round(r2_score(y_train, y_pred), 4)),
        "mae": float(round(mean_absolute_error(y_train, y_pred), 4)),
        "rmse": float(round(np.sqrt(mean_squared_error(y_train, y_pred)), 4)),
        "intercept": float(round(model.intercept_, 4)),
        "coefficients": coefficients,
    }
    
    return model, metrics


# Globally trained model instance
_TRAINED_MODEL, MLR_METRICS = train_mlr_model()


def predict_grid_prices(lat=22.57, lon=88.36):
    """Fetches day-ahead weather forecast and predicts 24 hourly grid prices (₹/kWh) using MLR.
    
    Returns:
        grid_prices (list[float]): 24 predicted hourly prices
        mlr_info (dict): Model performance metrics & feature importances
    """
    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lon}&hourly=shortwave_radiation,wind_speed_10m,temperature_2m&forecast_days=1"
        )
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        
        solar = data["hourly"]["shortwave_radiation"]
        wind = data["hourly"]["wind_speed_10m"]
        temp = data["hourly"]["temperature_2m"]
    except Exception as e:
        print(f"Open-Meteo API notice ({e}), using default forecast profile.")
        solar = [max(0.0, 750.0 * np.sin(np.pi * (h - 6) / 12.0)) for h in range(24)]
        wind = [4.5 + 2.0 * np.cos(2 * np.pi * h / 24.0) for h in range(24)]
        temp = [24.0 + 7.0 * np.sin(2 * np.pi * (h - 8) / 24.0) for h in range(24)]

    # Construct feature matrix X for 24 hours
    hours = np.arange(24)
    sin_h = np.sin(2 * np.pi * hours / 24.0)
    cos_h = np.cos(2 * np.pi * hours / 24.0)
    
    # Regional demand factor curve
    demand = 0.5 + 0.35 * np.sin(2 * np.pi * (hours - 14) / 12.0)**2 + 0.15 * (np.array(temp) / 35.0)
    demand = np.clip(demand, 0.2, 1.2)
    
    X_pred = np.column_stack([sin_h, cos_h, temp, demand, solar, wind])
    
    predicted_prices = _TRAINED_MODEL.predict(X_pred)
    predicted_prices = np.clip(predicted_prices, 1.5, 9.0)
    
    grid_prices = [float(round(p, 4)) for p in predicted_prices]
    
    return grid_prices, MLR_METRICS


if __name__ == "__main__":
    prices, metrics = predict_grid_prices()
    print("Dataset Source:", metrics["dataset_source"])
    print("Dataset Sample Count:", metrics["sample_count"])
    print("Predicted 24h Grid Prices (INR/kWh):", prices)
    print("MLR Metrics:", metrics)
