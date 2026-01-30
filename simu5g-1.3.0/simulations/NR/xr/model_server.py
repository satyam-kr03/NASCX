#!/usr/bin/env python3
"""
FastAPI Model Server for Optimal Compression Prediction

This server hosts the trained XGBoost model and provides an API
for predicting optimal compression levels based on network conditions.

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

# FastAPI app
app = FastAPI(
    title="Compression Model API",
    description="Predicts optimal XR video compression level based on network conditions",
    version="1.0.0"
)

# Global model variable
model = None


class PredictionRequest(BaseModel):
    """Request schema for compression prediction."""
    num_users: int = Field(..., ge=1, le=20, description="Number of users in the cell")
    avg_cqi: float = Field(..., ge=1.0, le=15.0, description="Average Channel Quality Indicator")


class PredictionResponse(BaseModel):
    """Response schema for compression prediction."""
    optimal_compression: int = Field(..., description="Optimal compression level (5, 10, 15, ..., 80)")
    raw_prediction: float = Field(..., description="Raw model prediction before snapping")


class HealthResponse(BaseModel):
    """Response schema for health check."""
    status: str
    model_loaded: bool


def snap_to_compression_level(pred: float) -> int:
    """Snap regression output to nearest valid compression level."""
    idx = np.abs(VALID_COMPRESSION_LEVELS - pred).argmin()
    return int(VALID_COMPRESSION_LEVELS[idx])


@app.on_event("startup")
async def load_model():
    """Load the trained model on startup."""
    global model
    if MODEL_PATH.exists():
        model = joblib.load(MODEL_PATH)
        print(f"Model loaded from {MODEL_PATH}")
    else:
        print(f"WARNING: Model file not found at {MODEL_PATH}")


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check server health and model status."""
    return HealthResponse(
        status="healthy",
        model_loaded=model is not None
    )


@app.post("/predict", response_model=PredictionResponse)
async def predict_compression(request: PredictionRequest):
    """
    Predict optimal compression level for given network conditions.
    
    Args:
        request: Contains num_users (1-20) and avg_cqi (1-15)
    
    Returns:
        Optimal compression level (5, 10, 15, ..., 80)
    """
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    # Create feature array
    features = np.array([[request.num_users, request.avg_cqi]])
    
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
        features = np.array([[req.num_users, req.avg_cqi]])
        raw_pred = float(model.predict(features)[0])
        optimal = snap_to_compression_level(raw_pred)
        results.append({
            "optimal_compression": optimal,
            "raw_prediction": raw_pred
        })
    
    return results


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
