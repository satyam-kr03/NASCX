#!/usr/bin/env python3
"""
FastAPI Model Server for Dynamic Per-Frame Compression Prediction

This server hosts the dynamic per-frame model (compression_model_dynamic.joblib)
that predicts per-frame compression based on frame complexity.

Features: num_users, cqi, fps, frame_complexity

Usage:
    python3 model_server.py

Endpoints:
    GET  /health             - Health check
    POST /predict_per_frame  - Dynamic: per-frame compression for a user
"""

import os
from typing import List
import numpy as np
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uvicorn
import joblib

# Configuration
DYNAMIC_MODEL_PATH = Path(__file__).parent / "compression_model_dynamic.joblib"
VALID_COMPRESSION_LEVELS = np.array([5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80])

# Feature columns expected by the dynamic model
FEATURE_COLUMNS = ['num_users', 'cqi', 'fps', 'frame_complexity']

# FastAPI app
app = FastAPI(
    title="Compression Model API",
    description="Predicts optimal per-frame XR video compression level based on network conditions",
    version="4.0.0"
)

# Global model variables
dynamic_model = None
dynamic_scaler = None


class PerFrameBatchRequest(BaseModel):
    """Batch request for per-frame compression prediction."""
    num_users: int = Field(..., ge=1, le=20, description="Number of users in the cell")
    avg_cqi: float = Field(..., ge=1.0, le=15.0, description="Average CQI for this user")
    fps: int = Field(default=60, ge=30, le=144, description="Frame rate")
    frame_complexities: List[float] = Field(..., description="List of frame complexities (size at max components, bytes)")


class PerFrameBatchResponse(BaseModel):
    """Response for per-frame batch prediction."""
    per_frame_compression: List[int] = Field(..., description="Compression level per frame")
    raw_predictions: List[float] = Field(..., description="Raw predictions before snapping")


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
    """Load the dynamic per-frame model on startup."""
    global dynamic_model, dynamic_scaler
    
    if DYNAMIC_MODEL_PATH.exists():
        dynamic_data = joblib.load(DYNAMIC_MODEL_PATH)
        if isinstance(dynamic_data, dict):
            dynamic_model = dynamic_data.get('model')
            dynamic_scaler = dynamic_data.get('scaler')
            feature_cols = dynamic_data.get('feature_columns', FEATURE_COLUMNS)
            model_type = dynamic_data.get('model_type', 'unknown')
            print(f"Dynamic model loaded from {DYNAMIC_MODEL_PATH}")
            print(f"  Type: {model_type}")
            print(f"  Features: {feature_cols}")
            print(f"  Scaler: {'loaded' if dynamic_scaler else 'not found'}")
        else:
            dynamic_model = dynamic_data
            dynamic_scaler = None
            print(f"Dynamic model loaded from {DYNAMIC_MODEL_PATH} (legacy format)")
    else:
        print(f"ERROR: Dynamic model not found at {DYNAMIC_MODEL_PATH}")
        print(f"  Train with: python3 train_dynamic_model.py")


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check server health and model status."""
    return HealthResponse(
        status="healthy",
        model_loaded=dynamic_model is not None,
        feature_columns=FEATURE_COLUMNS if dynamic_model is not None else []
    )


@app.post("/predict_per_frame", response_model=PerFrameBatchResponse)
async def predict_per_frame(request: PerFrameBatchRequest):
    """
    Predict per-frame compression levels based on frame complexity.
    
    This endpoint uses the dynamic model to predict a different compression
    level for each frame, based on the frame's inherent complexity
    (size at max components).
    
    Args:
        request: Contains num_users, avg_cqi, fps, and a list of frame_complexities
    
    Returns:
        Per-frame compression levels and raw predictions
    """
    if dynamic_model is None:
        raise HTTPException(
            status_code=503,
            detail="Dynamic per-frame model not loaded. Train with train_dynamic_model.py first."
        )
    
    n_frames = len(request.frame_complexities)
    
    # Build feature matrix: [num_users, cqi, fps, frame_complexity] for each frame
    features = np.array([
        [request.num_users, request.avg_cqi, request.fps, fc]
        for fc in request.frame_complexities
    ])
    
    # Scale features
    if dynamic_scaler is not None:
        features = dynamic_scaler.transform(features)
    
    # Batch prediction (efficient)
    raw_preds = dynamic_model.predict(features)
    per_frame_comp = [snap_to_compression_level(float(p)) for p in raw_preds]
    
    return PerFrameBatchResponse(
        per_frame_compression=per_frame_comp,
        raw_predictions=[float(p) for p in raw_preds]
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
