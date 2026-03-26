"""
FastAPI server for Classifier Compression Selector inference.

Hosts the PyTorch classifier models (2–10 users) and exposes an endpoint
that returns optimal compression levels for each user given their
current video characteristics (fps) and channel quality (cqi).

Usage:
    python classifier_model_server.py                    # default: port 8000
    python classifier_model_server.py --port 8080        # custom port
    python classifier_model_server.py --device cuda      # force GPU
"""

import argparse
import logging
import os
import pickle
import time
import warnings
from contextlib import asynccontextmanager

import numpy as np
import torch
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# Import architecture and utilities from classifier script
from classifier import MultiUserCompressionNet, clamp_components

# ── Paths ─────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = None

# ── Logging ───────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("classifier_model_server")

# ── Global state (populated on startup) ───────────────────────
models: dict[int, MultiUserCompressionNet] = {}
scalers_X: dict[int, object] = {}
scalers_Y: dict[int, object] = {}
DEVICE = torch.device("cpu")


# ── Request / Response schemas ────────────────────────────────
# We keep the exact same Request format to avoid changes in client code,
# even though this classifier model only uses frame_rate and cqi.
class UserFeatures(BaseModel):
    error_at_80: float = Field(..., description="Error metric at 80 components")
    error_ratio: float = Field(..., description="Error ratio metric")
    frame_rate: float      = Field(..., description="Video frame rate in fps (e.g. 45, 60, 72, 90, 120)")
    cqi: int               = Field(..., ge=5, le=15, description="Channel Quality Indicator (5–15)")
    prev_delay_ms: float   = Field(..., description="End to end delay of previous frame")


class PredictRequest(BaseModel):
    users: list[UserFeatures] = Field(
        ..., min_length=2, max_length=10,
        description="List of per-user features (2–10 users)",
    )


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
    loaded_models: list[int]


# ── Startup / shutdown ────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global models, scalers_X, scalers_Y, DEVICE, MODEL_DIR

    MODEL_DIR = os.path.join(SCRIPT_DIR, "models")
    log.info(f"Model dir: {MODEL_DIR}")

    # Parse device from env or default
    device_str = os.environ.get("MODEL_DEVICE", "cpu")
    DEVICE = torch.device(device_str)
    log.info(f"Using device: {DEVICE}")

    # Load models
    for n_u in range(2, 11):
        stem = os.path.join(MODEL_DIR, f"compression_{n_u}users")
        model_path = stem + ".pth"
        scaler_X_path = stem + "_scaler_X.pkl"
        scaler_Y_path = stem + "_scaler_Y.pkl"
        
        if not os.path.exists(model_path) or not os.path.exists(scaler_X_path) or not os.path.exists(scaler_Y_path):
            log.warning(f"Model or scalers for {n_u} users not found (tried {stem}.pth). Skipping.")
            continue

        model = MultiUserCompressionNet(n_u)
        model.load_state_dict(
            torch.load(model_path, map_location=DEVICE, weights_only=True)
        )
        model.to(DEVICE)
        model.eval()
        models[n_u] = model
        
        with open(scaler_X_path, "rb") as f:
            scalers_X[n_u] = pickle.load(f)
        with open(scaler_Y_path, "rb") as f:
            scalers_Y[n_u] = pickle.load(f)
            
        log.info(f"  Loaded {n_u}-user model and scalers from {MODEL_DIR}")

    if not models:
        log.warning("No models loaded! Make sure to train models via classifier.py first.")
    else:
        log.info(f"✓ All {len(models)} models ready for inference.")
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
        loaded_models=sorted(models.keys()),
    )


@app.post("/predict", response_model=PredictResponse)
async def predict(req: PredictRequest):
    n_users = len(req.users)

    if n_users not in models:
        raise HTTPException(
            status_code=400,
            detail=f"No model for {n_users} users. Supported: {list(models.keys())}.",
        )

    # ── Build input tensors ───────────────────────────────────
    # classifier gives models interleaved [error_at_80, error_ratio, cqi0, fps0, prev_delay0, ...] inputs

    # Find the real error metrics (OMNeT++ sends 1000.0 / 2.0 as dummies for other users)
    real_err80 = next((u.error_at_80 for u in req.users if u.error_at_80 != 1000.0), 1000.0)
    real_errRat = next((u.error_ratio for u in req.users if u.error_ratio != 2.0), 2.0)

    raw_state = [real_err80, real_errRat]
    
    for u in req.users:
        raw_state.append(u.cqi)
        raw_state.append(u.frame_rate)
        raw_state.append(u.prev_delay_ms)
    
    arr = np.array(raw_state, dtype=np.float32).reshape(1, -1)
    
    # Scale
    scaler_X = scalers_X[n_users]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        scaled = scaler_X.transform(arr)
        
    x = torch.tensor(scaled, dtype=torch.float32).to(DEVICE)

    # ── Inference ─────────────────────────────────────────────
    t0 = time.perf_counter()
    with torch.no_grad():
        outputs = models[n_users](x)  # list of (1, NUM_CLASSES) tensors
    if DEVICE.type == "cuda":
        torch.cuda.synchronize()
    inference_us = (time.perf_counter() - t0) * 1e6

    # ── Post-process ──────────────────────────────────────────
    out_stacked = torch.stack(outputs, dim=1).cpu().numpy()
    unscaled_predictions = scalers_Y[n_users].inverse_transform(out_stacked)[0]

    predictions = []
    for u in range(n_users):
        pred_val = unscaled_predictions[u]
        optimal_components = clamp_components(pred_val)
        
        # Fake a response format so client simulation parsing doesn't break
        confidence = 1.0
        top3 = [
            {"components": optimal_components, "probability": 1.0},
        ]
        
        predictions.append(UserPrediction(
            user_id=u,
            optimal_components=optimal_components,
            confidence=confidence,
            top3=top3,
        ))

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
