"""
FastAPI server for Classifier Compression Selector inference.

Hosts the PyTorch classifier model and exposes an endpoint that returns
optimal compression levels for each user given their current network
state and video characteristics.

Usage:
    python model_server.py                    # default: port 8000
    python model_server.py --port 8080        # custom port
    python model_server.py --device cuda      # force GPU
"""

import argparse
import logging
import os
import pickle
import time
from contextlib import asynccontextmanager
from pathlib import Path

import numpy as np
import torch
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from classifier import (
    MultiUserCompressionNet,
    class_to_components,
    predict_with_probabilities,
    MAX_USERS,
    FEATURES_PER_USER,
    NUM_CL_LEVELS,
)

# ── Paths & Logging ──────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent.resolve()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("model_server")

# ── Global state (populated on startup) ──────────────────────────────────
model: MultiUserCompressionNet = None
scaler: object = None
DEVICE = torch.device("cpu")


# ── Request / Response schemas ───────────────────────────────────────────
class UserFeatures(BaseModel):
    mse_vector: list[float] = Field(
        ..., min_length=NUM_CL_LEVELS, max_length=NUM_CL_LEVELS,
        description="MSE error vector at all 16 CLs (5,10,...,80)",
    )
    frame_rate: float = Field(..., description="Video frame rate in fps")
    cqi: int = Field(..., ge=5, le=15, description="Channel Quality Indicator (5–15)")
    prev_delay_ms: float = Field(..., description="End-to-end delay of previous frame")
    buffer_bytes: int = Field(..., description="DL MAC buffer occupancy in bytes")
    mcs_index: int = Field(..., description="Current MCS index")


class PredictRequest(BaseModel):
    users: list[UserFeatures] = Field(
        ..., min_length=2, max_length=10,
        description="List of per-user features (2–10 users)",
    )
    dl_utilization: float = Field(..., description="DL scheduler utilization (0.0-1.0)")
    n_active_ues: int = Field(..., description="Number of actively scheduled UEs")


class UserPrediction(BaseModel):
    user_id: int
    optimal_components: int = Field(..., description="Chosen compression level (5-80)")
    confidence: float = Field(..., description="Softmax probability of chosen level")
    top3: list[dict] = Field(..., description="Top-3 predictions with probabilities")


class PredictResponse(BaseModel):
    num_users: int
    inference_us: float = Field(..., description="Inference latency in microseconds")
    predictions: list[UserPrediction]


class HealthResponse(BaseModel):
    status: str
    device: str
    max_users_supported: int


# ── Startup / shutdown ───────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global model, scaler, DEVICE

    model_dir = SCRIPT_DIR / "models"
    log.info(f"Model dir: {model_dir}")

    device_str = os.environ.get("MODEL_DEVICE", "cpu")
    DEVICE = torch.device(device_str)
    log.info(f"Using device: {DEVICE}")

    # Load unified model
    stem = model_dir / "compression_unified"
    model_path = stem.with_suffix(".pth")
    scaler_path = Path(str(stem) + "_scaler.pkl")

    if not model_path.exists() or not scaler_path.exists():
        log.warning(f"Model or scaler not found at {stem}. Skipping.")
    else:
        model = MultiUserCompressionNet(MAX_USERS)
        model.load_state_dict(
            torch.load(str(model_path), map_location=DEVICE, weights_only=True)
        )
        model.to(DEVICE)
        model.eval()

        with open(scaler_path, "rb") as f:
            scaler = pickle.load(f)

        log.info(f"  Loaded unified {MAX_USERS}-user model from {model_dir}")

    if model is None:
        log.warning("No model loaded! Train via classifier.py first.")
    else:
        log.info("✓ Model ready for inference.")
    yield
    log.info("Shutting down model server.")


# ── App ──────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Compression Selector API",
    description="Model server for adaptive XR compression level selection.",
    version="2.0.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="ok",
        device=str(DEVICE),
        max_users_supported=MAX_USERS if model is not None else 0,
    )


@app.post("/predict", response_model=PredictResponse)
async def predict(req: PredictRequest):
    n_users = len(req.users)

    if model is None:
        raise HTTPException(
            status_code=503,
            detail="Model not loaded. Server configuration error.",
        )
    if n_users > MAX_USERS:
        raise HTTPException(
            status_code=400,
            detail=f"Too many users: {n_users}. Max supported: {MAX_USERS}.",
        )

    # Build raw state vector from request
    raw_state = []
    for u in req.users:
        raw_state.extend(u.mse_vector)
        raw_state.append(u.cqi)
        raw_state.append(u.frame_rate)
        raw_state.append(u.prev_delay_ms)
        raw_state.append(u.buffer_bytes)
        raw_state.append(u.mcs_index)
    raw_state.append(req.dl_utilization)
    raw_state.append(req.n_active_ues)

    # Run inference using shared helper (no duplicate scaling logic)
    t0 = time.perf_counter()
    results = predict_with_probabilities(
        model, scaler, raw_state, n_users, str(DEVICE)
    )
    if DEVICE.type == "cuda":
        torch.cuda.synchronize()
    inference_us = (time.perf_counter() - t0) * 1e6

    # Build response
    predictions = []
    for u_idx, res in enumerate(results):
        probs = res["probabilities"]
        top3_idx = np.argsort(probs)[::-1][:3]
        top3 = [
            {
                "components": class_to_components(int(i)),
                "probability": round(float(probs[i]), 4),
            }
            for i in top3_idx
        ]
        predictions.append(UserPrediction(
            user_id=u_idx,
            optimal_components=res["optimal_components"],
            confidence=round(res["confidence"], 4),
            top3=top3,
        ))

    log.info(
        f"Predict: {n_users} users → "
        f"{[p.optimal_components for p in predictions]} "
        f"({inference_us:.0f}μs)"
    )

    return PredictResponse(
        num_users=n_users,
        inference_us=round(inference_us, 1),
        predictions=predictions,
    )


# ── Entry point ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compression Selector API")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address")
    parser.add_argument("--port", type=int, default=8000, help="Port")
    parser.add_argument(
        "--device", default="cpu", choices=["cpu", "cuda"],
        help="Inference device",
    )
    args = parser.parse_args()

    os.environ["MODEL_DEVICE"] = args.device
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
