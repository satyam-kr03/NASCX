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
from contextlib import asynccontextmanager

import numpy as np
import pandas as pd
import torch
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# Import architecture and utilities from classifier script
from classifier import MultiUserCompressionNet, class_to_components, MAX_USERS, FEATURES_PER_USER, NUM_CL_LEVELS

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
model: MultiUserCompressionNet = None
scaler: object = None
DEVICE = torch.device("cpu")


# ── Request / Response schemas ────────────────────────────────
# We keep the exact same Request format to avoid changes in client code,
# even though this classifier model only uses frame_rate and cqi.
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

    MODEL_DIR = os.path.join(SCRIPT_DIR, "models")
    log.info(f"Model dir: {MODEL_DIR}")

    # Parse device from env or default
    device_str = os.environ.get("MODEL_DEVICE", "cpu")
    DEVICE = torch.device(device_str)
    log.info(f"Using device: {DEVICE}")

    # Load unified model
    stem = os.path.join(MODEL_DIR, f"compression_unified")
    model_path = stem + ".pth"
    scaler_path = stem + "_scaler.pkl"
    
    if not os.path.exists(model_path) or not os.path.exists(scaler_path):
        log.warning(f"Unified model or scaler not found (tried {model_path}). Skipping.")
    else:
        model = MultiUserCompressionNet(MAX_USERS)
        model.load_state_dict(
            torch.load(model_path, map_location=DEVICE, weights_only=True)
        )
        model.to(DEVICE)
        model.eval()
        
        with open(scaler_path, "rb") as f:
            scaler = pickle.load(f)
            
        log.info(f"  Loaded unified {MAX_USERS}-user model and scaler from {MODEL_DIR}")

    if model is None:
        log.warning("No model loaded! Make sure to train models via classifier.py first.")
    else:
        log.info(f"✓ Unified model ready for inference.")
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

    # ── Build input tensors ───────────────────────────────────
    # We will use predict_components from classifier.py since it handles padding and scaling correctly
    from classifier import predict_components
    
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
    components_list = predict_components(model, scaler, raw_state, n_users, str(DEVICE))
    if DEVICE.type == "cuda":
        torch.cuda.synchronize()
    inference_us = (time.perf_counter() - t0) * 1e6

    # ── Post-process ──────────────────────────────────────────
    # Getting full probabilities is harder with predict_components, so we'll just run inference here
    # doing similar steps. Let's just inline the scaling/padding logic:
    
    per_user_feats = FEATURES_PER_USER
    globals_list = raw_state[-2:]
    users_list = raw_state[:-2]
    
    padded_users = users_list.copy()
    for _ in range(n_users, MAX_USERS):
        padded_users.extend([0.0] * per_user_feats)
        
    padded_state = padded_users + globals_list
    arr = np.array(padded_state, dtype=np.float32).reshape(1, -1)

    if hasattr(scaler, "feature_names_in_"):
        cols = list(scaler.feature_names_in_)
        arr_in = pd.DataFrame(arr, columns=cols)
    else:
        arr_in = arr

    scaled_full = scaler.transform(arr_in)
        
    scaled = np.zeros_like(arr)
    scaled[0, :] = scaled_full[0, :]
    
    for i in range(n_users, MAX_USERS):
        start_idx = i * per_user_feats
        end_idx = start_idx + per_user_feats
        scaled[0, start_idx:end_idx] = 0.0
        
    x = torch.tensor(scaled, dtype=torch.float32).to(DEVICE)

    # ── Inference ─────────────────────────────────────────────
    t0 = time.perf_counter()
    with torch.no_grad():
        outputs = model(x)  # list of (1, NUM_CLASSES) tensors
    if DEVICE.type == "cuda":
        torch.cuda.synchronize()
    inference_us = (time.perf_counter() - t0) * 1e6

    # ── Post-process ──────────────────────────────────────────
    # Only return predictions for the active n_users
    predictions = []
    for u in range(n_users):
        logits = outputs[u][0] # (NUM_CLASSES,)
        probs = torch.softmax(logits, dim=0).cpu().numpy()  # (NUM_CLASSES,)
        pred_idx = probs.argmax()
        
        top3_idx = np.argsort(probs)[::-1][:3]
        top3 = [
            {"components": class_to_components(int(i)), "probability": round(float(probs[i]), 4)}
            for i in top3_idx
        ]
        
        predictions.append(UserPrediction(
            user_id=u,
            optimal_components=class_to_components(int(pred_idx)),
            confidence=round(float(probs[pred_idx]), 4),
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
