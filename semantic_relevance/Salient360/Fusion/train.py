"""
Training loop for the fusion model.

Handles:
  - Training with combined KL + CC loss
  - Validation with full saliency metrics
  - Early stopping
  - Checkpoint saving / loading
  - Learning-rate scheduling
"""

from __future__ import annotations

import os
import time
from typing import Dict, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from config import PipelineConfig
from model import build_model
from losses import FusionLoss, compute_all_metrics


def train_one_epoch(
    model: nn.Module,
    loader: DataLoader,
    criterion: FusionLoss,
    optimiser: torch.optim.Optimizer,
    device: torch.device,
    log_every: int = 5,
) -> Dict[str, float]:
    """Train for one epoch. Returns average losses."""
    model.train()
    running = {}
    n_batches = 0

    for i, (inp, target, fixmap) in enumerate(loader):
        inp = inp.to(device)
        target = target.to(device)
        fixmap = fixmap.to(device)

        pred = model(inp)
        losses = criterion(pred, target, fixmap)

        optimiser.zero_grad()
        losses["total"].backward()
        optimiser.step()

        for k, v in losses.items():
            running[k] = running.get(k, 0.0) + v.item()
        n_batches += 1

        if log_every > 0 and (i + 1) % log_every == 0:
            avg_total = running["total"] / n_batches
            print(f"    batch {i + 1}/{len(loader)}  loss={avg_total:.4f}")

    return {k: v / max(n_batches, 1) for k, v in running.items()}


@torch.no_grad()
def validate(
    model: nn.Module,
    loader: DataLoader,
    criterion: FusionLoss,
    device: torch.device,
) -> Tuple[Dict[str, float], Dict[str, float]]:
    """
    Validate the model.

    Returns:
      (avg_losses, avg_metrics)  where avg_metrics includes KL, CC, NSS, SIM.
    """
    model.eval()
    running_losses = {}
    all_metrics = []
    n_batches = 0

    for inp, target, fixmap in loader:
        inp = inp.to(device)
        target = target.to(device)
        fixmap = fixmap.to(device)

        pred = model(inp)
        losses = criterion(pred, target, fixmap)

        for k, v in losses.items():
            running_losses[k] = running_losses.get(k, 0.0) + v.item()
        n_batches += 1

        # Compute numpy metrics per sample
        pred_np = pred.squeeze(1).cpu().numpy()
        target_np = target.squeeze(1).cpu().numpy()
        fixmap_np = fixmap.squeeze(1).cpu().numpy()

        for b in range(pred_np.shape[0]):
            m = compute_all_metrics(pred_np[b], target_np[b], fixmap_np[b])
            all_metrics.append(m)

    avg_losses = {k: v / max(n_batches, 1) for k, v in running_losses.items()}

    # Average metrics across all samples
    avg_metrics = {}
    if all_metrics:
        for key in all_metrics[0]:
            avg_metrics[key] = float(np.mean([m[key] for m in all_metrics]))

    return avg_losses, avg_metrics


def train(cfg: PipelineConfig, train_loader: DataLoader, val_loader: DataLoader):
    """
    Full training procedure with early stopping and checkpointing.
    """
    device = torch.device(cfg.train.device if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    # Build model
    model = build_model(cfg.model).to(device)

    # Loss, optimiser, scheduler
    criterion = FusionLoss(cfg.loss)
    optimiser = torch.optim.AdamW(
        model.parameters(),
        lr=cfg.train.learning_rate,
        weight_decay=cfg.train.weight_decay,
    )

    if cfg.train.scheduler == "cosine":
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            optimiser, T_max=cfg.train.n_epochs
        )
    elif cfg.train.scheduler == "step":
        scheduler = torch.optim.lr_scheduler.StepLR(
            optimiser,
            step_size=cfg.train.step_size,
            gamma=cfg.train.gamma,
        )
    else:
        scheduler = None

    os.makedirs(cfg.train.checkpoint_dir, exist_ok=True)

    best_val_cc = -1.0     # CC: higher is better
    patience_counter = 0
    history = {"train": [], "val": []}

    print(f"\n{'='*60}")
    print(f"Training: {cfg.train.n_epochs} epochs, "
          f"lr={cfg.train.learning_rate}, bs={cfg.train.batch_size}")
    print(f"Loss: KL×{cfg.loss.kl_weight} + CC×{cfg.loss.cc_weight}"
          + (f" + NSS×{cfg.loss.nss_weight}" if cfg.loss.nss_weight > 0 else ""))
    print(f"{'='*60}\n")

    for epoch in range(1, cfg.train.n_epochs + 1):
        t0 = time.time()
        lr = optimiser.param_groups[0]["lr"]

        # ── Train ───────────────────────────────────────────────────
        train_losses = train_one_epoch(
            model, train_loader, criterion, optimiser, device, cfg.train.log_every
        )

        # ── Validate ────────────────────────────────────────────────
        val_losses, val_metrics = validate(model, val_loader, criterion, device)

        elapsed = time.time() - t0
        history["train"].append(train_losses)
        history["val"].append({"losses": val_losses, "metrics": val_metrics})

        # ── Print summary ───────────────────────────────────────────
        print(
            f"Epoch {epoch:3d}/{cfg.train.n_epochs}  "
            f"lr={lr:.6f}  "
            f"train_loss={train_losses['total']:.4f}  "
            f"val_loss={val_losses['total']:.4f}  "
            f"KL={val_metrics.get('KL', 0):.4f}  "
            f"CC={val_metrics.get('CC', 0):.4f}  "
            f"NSS={val_metrics.get('NSS', 0):.4f}  "
            f"SIM={val_metrics.get('SIM', 0):.4f}  "
            f"({elapsed:.1f}s)"
        )

        # ── Checkpoint (use CC for early stopping — scale-invariant, ──
        #     directly measures spatial structure quality)              ──
        val_cc = val_metrics.get("CC", -1.0)
        if val_cc > best_val_cc:
            best_val_cc = val_cc
            patience_counter = 0
            ckpt_path = os.path.join(cfg.train.checkpoint_dir, "best_model.pt")
            torch.save({
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "optimiser_state_dict": optimiser.state_dict(),
                "val_cc": val_cc,
                "val_metrics": val_metrics,
                "config": {
                    "model": cfg.model.__dict__,
                    "loss": cfg.loss.__dict__,
                    "train": cfg.train.__dict__,
                },
            }, ckpt_path)
            print(f"  ✓ New best CC={val_cc:.4f} — saved to {ckpt_path}")
        else:
            patience_counter += 1

        # ── LR schedule ─────────────────────────────────────────────
        if scheduler is not None:
            scheduler.step()

        # ── Early stopping ──────────────────────────────────────────
        if cfg.train.patience > 0 and patience_counter >= cfg.train.patience:
            print(f"\nEarly stopping at epoch {epoch} "
                  f"(no improvement for {cfg.train.patience} epochs)")
            break

    # Save final model
    final_path = os.path.join(cfg.train.checkpoint_dir, "final_model.pt")
    torch.save({
        "epoch": epoch,
        "model_state_dict": model.state_dict(),
        "config": {
            "model": cfg.model.__dict__,
            "loss": cfg.loss.__dict__,
            "train": cfg.train.__dict__,
        },
    }, final_path)
    print(f"\nTraining complete. Final model: {final_path}")
    print(f"Best validation CC: {best_val_cc:.4f}")

    return model, history
