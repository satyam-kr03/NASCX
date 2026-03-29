with open("classifier_model_server.py", "w") as f:
    f.write("""import argparse
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

from classifier import SingleUserCompressionNet, class_to_components

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("classifier_model_server")

model: SingleUserCompressionNet = None
scaler: object = None
DEVICE = torch.device("cpu")

class UserFeatures(BaseModel):
    error_at_80: float = Field(...)
    error_ratio: float = Field(...)
    frame_rate: float = Field(...)
    cqi: int = Field(...)
    prev_delay_ms: float = Field(...)
    buffer_bytes: int = Field(...)
    mcs_index: int = Field(...)

class PredictRequest(BaseModel):
    users: list[UserFeatures] = Field(..., min_length=1, max_length=100)
    dl_utilization: float = Field(...)
    n_active_ues: int = Field(...)

class UserPrediction(BaseModel):
    user_id: int
    optimal_components: int = Field(...)
    confidence: float = Field(...)
    top3: list[dict] = Field(...)

class PredictResponse(BaseModel):
    num_users: int
    inference_us: float = Field(...)
    predictions: list[UserPrediction]

class HealthResponse(BaseModel):
    status: str
    device: str

@asynccontextmanager
async def lifespan(app: FastAPI):
    global model, scaler, DEVICE, MODEL_DIR
    MODEL_DIR = os.path.join(SCRIPT_DIR, "models")
    log.info(f"Model dir: {MODEL_DIR}")
    device_str = os.environ.get("MODEL_DEVICE", "cpu")
    DEVICE = torch.device(device_str)
    log.info(f"Using device: {DEVICE}")

    stem = os.path.join(MODEL_DIR, "compression_single")
    model_path = stem + ".pth"
    scaler_path = stem + "_scaler.pkl"
    
    if not os.path.exists(model_path) or not os.path.exists(scaler_path):
        log.warning(f"Single-agent model or scaler not found. Skipping.")
    else:
        model = SingleUserCompressionNet()
        model.load_state_dict(torch.load(model_path, map_location=DEVICE, weights_only=True))
        model.to(DEVICE)
        model.eval()
        with open(scaler_path, "rb") as f:
            scaler = pickle.load(f)
        log.info(f"  Loaded Single-Agent model and scaler from {MODEL_DIR}")
    yield
    log.info("Shutting down model server.")

app = FastAPI(title="Classifier Compression Selector API (Phase 3)", lifespan=lifespan)

@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok", device=str(DEVICE))

@app.post("/predict", response_model=PredictResponse)
async def predict(req: PredictRequest):
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded.")

    n_users = len(req.users)
    t0 = time.perf_counter()
    
    features = []
    for u in req.users:
        features.append([
            u.error_at_80, u.error_ratio, u.cqi, u.frame_rate, 
            u.prev_delay_ms, u.buffer_bytes, u.mcs_index, 
            req.dl_utilization, req.n_active_ues
        ])
    
    batch_arr = np.array(features, dtype=np.float32)
    
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        scaled = scaler.transform(batch_arr)
        
    x = torch.tensor(scaled, dtype=torch.float32).to(DEVICE)
    
    with torch.no_grad():
        outputs = model(x)  # (N, NUM_CLASSES)
        probs = torch.softmax(outputs, dim=1).cpu().numpy()
        
    if DEVICE.type == "cuda":
        torch.cuda.synchronize()
    inference_us = (time.perf_counter() - t0) * 1e6
    
    predictions = []
    for u in range(n_users):
        user_probs = probs[u]
        pred_idx = user_probs.argmax()
        top3_idx = np.argsort(user_probs)[::-1][:3]
        top3 = [{"components": class_to_components(int(i)), "probability": round(float(user_probs[i]), 4)} for i in top3_idx]
        
        predictions.append(UserPrediction(
            user_id=u,
            optimal_components=class_to_components(int(pred_idx)),
            confidence=round(float(user_probs[pred_idx]), 4),
            top3=top3,
        ))

    return PredictResponse(
        num_users=n_users,
        inference_us=round(inference_us, 1),
        predictions=predictions,
    )

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    args = parser.parse_args()
    os.environ["MODEL_DEVICE"] = args.device
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
""")
