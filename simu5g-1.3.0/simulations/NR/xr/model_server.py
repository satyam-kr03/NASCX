#!/usr/bin/env python3
"""
FastAPI Model Server for Optimal Compression Prediction

This server hosts the trained XGBoost model and provides an API
for predicting optimal compression levels based on network conditions.

The model uses 5 features:
  - num_users: Number of users in the cell
  - avg_cqi: Average Channel Quality Indicator
  - fps: Frame rate (60, 72, 90, 120)
  - size_mean_kb: Mean frame size in KB
  - size_std_kb: Standard deviation of frame size in KB

Usage:
    python3 model_server.py

Endpoints:
    GET  /health  - Health check
    POST /predict - Predict optimal compression level
"""

import os
import numpy as np
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uvicorn
import joblib

# Configuration
MODEL_PATH = Path(__file__).parent / "compression_model.joblib"
VALID_COMPRESSION_LEVELS = np.array([5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80])

# Feature columns expected by the model (must match training)
FEATURE_COLUMNS = ['num_users', 'cqi_midpoint', 'fps', 'size_mean_kb', 'size_std_kb']

# FastAPI app
app = FastAPI(
    title="Compression Model API",
    description="Predicts optimal XR video compression level based on network conditions",
    version="2.0.0"
)

# Global model variables
model = None
scaler = None


class PredictionRequest(BaseModel):
    """Request schema for compression prediction."""
    num_users: int = Field(..., ge=1, le=20, description="Number of users in the cell")
    avg_cqi: float = Field(..., ge=1.0, le=15.0, description="Average Channel Quality Indicator")
    fps: int = Field(default=60, ge=30, le=144, description="Frame rate (e.g., 60, 72, 90, 120)")
    size_mean_kb: float = Field(default=65.0, ge=1.0, le=500.0, description="Mean frame size in KB")
    size_std_kb: float = Field(default=34.8, ge=0.0, le=200.0, description="Standard deviation of frame size in KB")


class PredictionResponse(BaseModel):
    """Response schema for compression prediction."""
    optimal_compression: int = Field(..., description="Optimal compression level (5, 10, 15, ..., 80)")
    raw_prediction: float = Field(..., description="Raw model prediction before snapping")


class HealthResponse(BaseModel):
    """Response schema for health check."""
    status: str
    model_loaded: bool
    feature_columns: list[str] = []


def snap_to_compression_level(pred: float) -> int:
    """Snap regression output to nearest valid compression level."""
    idx = np.abs(VALID_COMPRESSION_LEVELS - pred).argmin()
    return int(VALID_COMPRESSION_LEVELS[idx])


@app.on_event("startup")
async def load_model():
    """Load the trained model on startup."""
    global model, scaler
    if MODEL_PATH.exists():
        model_data = joblib.load(MODEL_PATH)
        
        # Handle both old (direct model) and new (dict with model + scaler) formats
        if isinstance(model_data, dict):
            model = model_data.get('model')
            scaler = model_data.get('scaler')
            feature_cols = model_data.get('feature_columns', FEATURE_COLUMNS)
            print(f"Model loaded from {MODEL_PATH}")
            print(f"  Features: {feature_cols}")
            print(f"  Scaler: {'loaded' if scaler else 'not found'}")
        else:
            # Legacy format: model_data is the model itself
            model = model_data
            scaler = None
            print(f"Model loaded from {MODEL_PATH} (legacy format, no scaler)")
    else:
        print(f"WARNING: Model file not found at {MODEL_PATH}")


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check server health and model status."""
    return HealthResponse(
        status="healthy",
        model_loaded=model is not None,
        feature_columns=FEATURE_COLUMNS if model is not None else []
    )


@app.post("/predict", response_model=PredictionResponse)
async def predict_compression(request: PredictionRequest):
    """
    Predict optimal compression level for given network conditions.
    
    Args:
        request: Contains num_users, avg_cqi, fps, size_mean_kb, size_std_kb
    
    Returns:
        Optimal compression level (5, 10, 15, ..., 80)
    """
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    # Create feature array: [num_users, cqi_midpoint, fps, size_mean_kb, size_std_kb]
    features = np.array([[
        request.num_users,
        request.avg_cqi,
        request.fps,
        request.size_mean_kb,
        request.size_std_kb
    ]])
    
    # Scale features if scaler is available
    if scaler is not None:
        features = scaler.transform(features)
    
    # Get raw prediction
    raw_pred = float(model.predict(features)[0])
    
    # Snap to valid compression level
    optimal = snap_to_compression_level(raw_pred)
    
    return PredictionResponse(
        optimal_compression=optimal,
        raw_prediction=raw_pred
    )


@app.post("/predict_batch")
async def predict_batch(requests: list[PredictionRequest]):
    """
    Predict optimal compression levels for multiple users.
    
    Args:
        requests: List of prediction requests
    
    Returns:
        List of optimal compression levels
    """
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    results = []
    for req in requests:
        # Create feature array: [num_users, cqi_midpoint, fps, size_mean_kb, size_std_kb]
        features = np.array([[
            req.num_users,
            req.avg_cqi,
            req.fps,
            req.size_mean_kb,
            req.size_std_kb
        ]])
        
        # Scale features if scaler is available
        if scaler is not None:
            features = scaler.transform(features)
        
        raw_pred = float(model.predict(features)[0])
        optimal = snap_to_compression_level(raw_pred)
        results.append({
            "optimal_compression": optimal,
            "raw_prediction": raw_pred
        })
    
    return results


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
