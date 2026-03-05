"""
FastAPI server for Stage 2 Compression Selector inference.

Hosts the 9 TorchScript models (2–10 users) and exposes an endpoint
that returns optimal compression levels for each user given their
current video characteristics and channel quality.

Usage:
    python model_server.py                    # default: port 8000
    python model_server.py --port 8080        # custom port
    python model_server.py --device cuda      # force GPU
"""

import argparse
import json
import logging
import os
import pickle
import time
from contextlib import asynccontextmanager

import numpy as np
import torch
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# ── Paths ─────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR  = os.path.join(SCRIPT_DIR, "models_stage2")

# ── Logging ───────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("model_server")

# ── Global state (populated on startup) ───────────────────────
models: dict[int, torch.jit.ScriptModule] = {}
scaler = None
config: dict = {}
DEVICE = torch.device("cpu")


# ── Request / Response schemas ────────────────────────────────
class UserFeatures(BaseModel):
    meantrafficsize: float = Field(..., description="Mean traffic size of the user's video")
    stdtrafficsize: float  = Field(..., description="Std of traffic size")
    frameComplexity: float = Field(..., description="Frame complexity metric")
    cqi: int               = Field(..., ge=6, le=15, description="Channel Quality Indicator (6–15)")


class PredictRequest(BaseModel):
    users: list[UserFeatures] = Field(
        ..., min_length=2, max_length=10,
        description="List of per-user features (2–10 users)",
    )


class UserPrediction(BaseModel):
    user_id: int
    optimal_components: int = Field(..., description="Chosen compression level (25–400)")
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
    global models, scaler, config, DEVICE

    # Parse device from env or default
    device_str = os.environ.get("MODEL_DEVICE", "cpu")
    DEVICE = torch.device(device_str)
    log.info(f"Using device: {DEVICE}")

    # Load config
    config_path = os.path.join(MODEL_DIR, "config.json")
    with open(config_path) as f:
        config = json.load(f)
    log.info(f"Config loaded: {config_path}")

    # Load scaler
    scaler_path = os.path.join(MODEL_DIR, "static_scaler.pkl")
    with open(scaler_path, "rb") as f:
        scaler = pickle.load(f)
    log.info(f"Scaler loaded: {scaler_path}")

    # Load TorchScript models
    for n_u in range(2, 11):
        path = os.path.join(MODEL_DIR, f"selector_{n_u}users_scripted.pt")
        model = torch.jit.load(path, map_location=DEVICE)
        model.eval()
        models[n_u] = model
        log.info(f"  Loaded {n_u}-user model from {path}")

    log.info(f"✓ All {len(models)} models ready for inference.")
    yield
    log.info("Shutting down model server.")


# ── App ───────────────────────────────────────────────────────
app = FastAPI(
    title="Compression Selector API",
    description="Stage 2 neural network for dynamic adaptive XR compression.",
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
            detail=f"No model for {n_users} users. Supported: 2–10.",
        )

    comp_levels = config["comp_levels"]
    cqi_min = config["cqi_min"]

    # ── Build input tensors ───────────────────────────────────
    static_raw = np.array(
        [[u.meantrafficsize, u.stdtrafficsize, u.frameComplexity] for u in req.users],
        dtype=np.float32,
    )  # (N, 3)
    cqi_idx = np.array([u.cqi - cqi_min for u in req.users], dtype=np.int64)  # (N,)

    # Normalise
    static_scaled = scaler.transform(static_raw).reshape(1, n_users, 3)
    x_cont = torch.tensor(static_scaled, dtype=torch.float32).to(DEVICE)
    x_cqi  = torch.tensor(cqi_idx.reshape(1, n_users), dtype=torch.long).to(DEVICE)

    # ── Inference ─────────────────────────────────────────────
    t0 = time.perf_counter()
    with torch.no_grad():
        logits = models[n_users](x_cont, x_cqi)  # (1, N, 16)
    if DEVICE.type == "cuda":
        torch.cuda.synchronize()
    inference_us = (time.perf_counter() - t0) * 1e6

    # ── Post-process ──────────────────────────────────────────
    probs = torch.softmax(logits[0], dim=-1).cpu().numpy()  # (N, 16)
    pred_idx = probs.argmax(axis=1)                          # (N,)

    predictions = []
    for u in range(n_users):
        top3_idx = np.argsort(probs[u])[::-1][:3]
        top3 = [
            {"components": comp_levels[int(i)], "probability": round(float(probs[u, i]), 4)}
            for i in top3_idx
        ]
        predictions.append(UserPrediction(
            user_id=u,
            optimal_components=comp_levels[int(pred_idx[u])],
            confidence=round(float(probs[u, pred_idx[u]]), 4),
            top3=top3,
        ))

    return PredictResponse(
        num_users=n_users,
        inference_us=round(inference_us, 1),
        predictions=predictions,
    )


# ── Entry point ───────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compression Selector API")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address")
    parser.add_argument("--port", type=int, default=8000, help="Port")
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"],
                        help="Inference device")
    args = parser.parse_args()

    os.environ["MODEL_DEVICE"] = args.device

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
