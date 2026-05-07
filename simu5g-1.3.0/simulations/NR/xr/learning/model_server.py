"""
FastAPI server for Classifier Compression Selector inference.

Hosts the PyTorch classifier model (2–10 users) and exposes an endpoint
that returns optimal compression levels for each user given their
current video characteristics (fps) and channel quality (cqi).

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

# Import architecture and utilities from classifier script
from classifier import (
    MultiUserCompressionNet,
    class_to_components,
    MAX_USERS,
    NUM_CL_LEVELS,
    predict_with_probabilities,
)

# ── Paths ─────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
MODEL_DIR = None

# ── Logging ───────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("model_server")

# ── Global state (populated on startup) ───────────────────────
model: MultiUserCompressionNet | None = None
scaler: object | None = None
DEVICE = torch.device("cpu")


# ── Request / Response schemas ────────────────────────────────
# We keep the exact same Request format to avoid changes in client code.
class UserFeatures(BaseModel):
    mse_vector: list[float] = Field(..., min_length=NUM_CL_LEVELS, max_length=NUM_CL_LEVELS,
                                     description="MSE error vector at all 16 CLs (5,10,...,80)")
    frame_rate: float      = Field(..., description="Video frame rate in fps (e.g. 45, 60, 72, 90, 120)")
    cqi: int               = Field(..., ge=5, le=15, description="Channel Quality Indicator (5–15)")
    prev_delay_ms: float   = Field(..., description="End to end delay of previous frame")
    buffer_bytes: int      = Field(..., description="DL MAC buffer occupancy in bytes")
    mcs_index: int         = Field(..., description="Current MCS index")


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
    confidence: float       = Field(..., description="Softmax probability of the chosen level")
    top3: list[dict]        = Field(..., description="Top-3 predictions with probabilities")


class PredictResponse(BaseModel):
    num_users: int
    inference_us: float = Field(..., description="Inference latency in microseconds")
    predictions: list[UserPrediction]


class HealthResponse(BaseModel):
    status: str
    device: str
    max_users_supported: int


# ── Startup / shutdown ────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global model, scaler, DEVICE, MODEL_DIR

    MODEL_DIR = SCRIPT_DIR / "models"
    log.info("Model dir: %s", MODEL_DIR)

    # Parse device from env or default
    device_str = os.environ.get("MODEL_DEVICE", "cpu")
    DEVICE = torch.device(device_str)
    log.info("Using device: %s", DEVICE)

    # Load unified model
    stem = MODEL_DIR / "compression_unified"
    model_path = stem.with_suffix(".pth")
    scaler_path = Path(f"{stem}_scaler.pkl")

    if not model_path.exists() or not scaler_path.exists():
        log.warning("Unified model or scaler not found (tried %s). Skipping.", model_path)
    else:
        model = MultiUserCompressionNet(MAX_USERS)
        model.load_state_dict(
            torch.load(model_path, map_location=DEVICE, weights_only=True)
        )
        model.to(DEVICE)
        model.eval()

        with open(scaler_path, "rb") as f:
            scaler = pickle.load(f)

        log.info("  Loaded unified %s-user model and scaler from %s", MAX_USERS, MODEL_DIR)

    if model is None:
        log.warning("No model loaded! Make sure to train models via classifier.py first.")
    else:
        log.info("✓ Unified model ready for inference.")
    yield
    log.info("Shutting down model server.")


# ── App ───────────────────────────────────────────────────────
app = FastAPI(
    title="Classifier Compression Selector API",
    description="Classifier model server for XR compression.",
    version="1.0.0",
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

    if model is None or scaler is None:
        raise HTTPException(
            status_code=503,
            detail="Model not loaded. Server configuration error.",
        )

    if n_users > MAX_USERS:
        raise HTTPException(
            status_code=400,
            detail=f"Too many users: {n_users}. Max supported: {MAX_USERS}.",
        )

    raw_state = []
    for u in req.users:
        raw_state.extend(u.mse_vector)  # 16 MSE values
        raw_state.append(u.cqi)
        raw_state.append(u.frame_rate)
        raw_state.append(u.prev_delay_ms)
        raw_state.append(u.buffer_bytes)
        raw_state.append(u.mcs_index)

    raw_state.append(req.dl_utilization)
    raw_state.append(req.n_active_ues)

    t0 = time.perf_counter()
    components_list, probabilities = predict_with_probabilities(
        model, scaler, raw_state, n_users, str(DEVICE)
    )
    if DEVICE.type == "cuda":
        torch.cuda.synchronize()
    inference_us = (time.perf_counter() - t0) * 1e6

    predictions = []
    for u in range(n_users):
        probs = np.array(probabilities[u])
        pred_idx = int(np.argmax(probs))

        top3_idx = np.argsort(probs)[::-1][:3]
        top3 = [
            {"components": class_to_components(int(i)), "probability": round(float(probs[i]), 4)}
            for i in top3_idx
        ]

        predictions.append(UserPrediction(
            user_id=u,
            optimal_components=components_list[u],
            confidence=round(float(probs[pred_idx]), 4),
            top3=top3,
        ))

    log.info("/predict users=%s inference_us=%.1f", n_users, inference_us)

    return PredictResponse(
        num_users=n_users,
        inference_us=round(inference_us, 1),
        predictions=predictions,
    )


# ── Entry point ───────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Classifier Compression Selector API")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address")
    parser.add_argument("--port", type=int, default=8000, help="Port")
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"],
                        help="Inference device")
    args = parser.parse_args()

    os.environ["MODEL_DEVICE"] = args.device

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
