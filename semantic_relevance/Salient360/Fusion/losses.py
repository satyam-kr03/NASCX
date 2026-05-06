"""
Saliency loss functions and evaluation metrics.

Standard saliency metrics from the literature, implemented as differentiable
PyTorch losses (for training) and numpy functions (for evaluation).

Training losses:
  - KL Divergence       (primary)
  - Correlation Coeff.  (complementary)

Evaluation metrics:
  - KL Divergence
  - CC  (Correlation Coefficient)
  - NSS (Normalized Scanpath Saliency)
  - SIM (Similarity / histogram intersection)
  - AUC-Judd
"""

from __future__ import annotations

import torch
import torch.nn.functional as F
import numpy as np
from typing import Dict

from config import LossConfig


EPS = 1e-7


def _to_distribution(x: torch.Tensor) -> torch.Tensor:
    """Normalise a non-negative map so it sums to 1 (per sample)."""
    B = x.shape[0]
    x = x.view(B, -1)
    x = x - x.min(dim=1, keepdim=True).values  # ensure non-negative
    s = x.sum(dim=1, keepdim=True) + EPS
    return x / s


def kl_divergence(pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    """
    KL(target || pred) — standard saliency KL.

    Both maps are normalised to probability distributions internally.
    """
    B = pred.shape[0]
    p = _to_distribution(pred)          # predicted distribution
    q = _to_distribution(target)        # GT distribution

    # KL(q || p) = Σ q * log(q / p)
    kl = q * torch.log((q + EPS) / (p + EPS))
    return kl.sum(dim=1).mean()


def correlation_coefficient(pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    """
    Pearson correlation coefficient between pred and target maps.
    Returns *negative* CC so it can be minimised as a loss.
    """
    B = pred.shape[0]
    p = pred.view(B, -1)
    q = target.view(B, -1)

    p_mean = p.mean(dim=1, keepdim=True)
    q_mean = q.mean(dim=1, keepdim=True)

    p_centered = p - p_mean
    q_centered = q - q_mean

    num = (p_centered * q_centered).sum(dim=1)
    den = torch.sqrt(
        (p_centered ** 2).sum(dim=1) * (q_centered ** 2).sum(dim=1) + EPS
    )

    cc = num / den
    return -cc.mean()  # negate: minimising loss → maximising CC


def nss_loss(pred: torch.Tensor, fixmap: torch.Tensor) -> torch.Tensor:
    """
    Normalized Scanpath Saliency.

    pred   : [B, 1, H, W] — predicted saliency map
    fixmap : [B, 1, H, W] — binary fixation map (1 at fixation points)

    Returns negative mean NSS (for minimisation).
    """
    B = pred.shape[0]
    p = pred.view(B, -1).float()
    f = fixmap.view(B, -1).float()

    # Z-score normalise the prediction per sample
    p_mean = p.mean(dim=1, keepdim=True)
    p_std = p.std(dim=1, keepdim=True) + EPS
    p_norm = (p - p_mean) / p_std

    # NSS = mean of normalised prediction at fixation locations
    n_fix = f.sum(dim=1) + EPS
    nss = (p_norm * f).sum(dim=1) / n_fix

    return -nss.mean()  # negate for minimisation


class FusionLoss(torch.nn.Module):
    """Combined saliency loss for training."""

    def __init__(self, cfg: LossConfig):
        super().__init__()
        self.kl_w = cfg.kl_weight
        self.cc_w = cfg.cc_weight
        self.nss_w = cfg.nss_weight

    def forward(
        self,
        pred: torch.Tensor,
        target: torch.Tensor,
        fixmap: torch.Tensor | None = None,
    ) -> Dict[str, torch.Tensor]:
        losses = {}

        if self.kl_w > 0:
            losses["kl"] = kl_divergence(pred, target)

        if self.cc_w > 0:
            losses["neg_cc"] = correlation_coefficient(pred, target)

        if self.nss_w > 0 and fixmap is not None:
            losses["neg_nss"] = nss_loss(pred, fixmap)

        total = sum(
            w * losses[k]
            for k, w in [
                ("kl", self.kl_w),
                ("neg_cc", self.cc_w),
                ("neg_nss", self.nss_w),
            ]
            if k in losses
        )
        losses["total"] = total
        return losses


def eval_kl(pred: np.ndarray, gt: np.ndarray) -> float:
    """KL divergence (gt || pred). Lower is better."""
    p = pred.astype(np.float64).ravel()
    q = gt.astype(np.float64).ravel()

    # Normalise to distributions
    p = np.maximum(p, 0)
    q = np.maximum(q, 0)
    p = p / (p.sum() + EPS)
    q = q / (q.sum() + EPS)

    return float(np.sum(q * np.log((q + EPS) / (p + EPS))))


def eval_cc(pred: np.ndarray, gt: np.ndarray) -> float:
    """Pearson correlation coefficient. Higher is better."""
    p = pred.ravel().astype(np.float64)
    q = gt.ravel().astype(np.float64)

    p -= p.mean()
    q -= q.mean()

    num = np.sum(p * q)
    den = np.sqrt(np.sum(p ** 2) * np.sum(q ** 2) + EPS)
    return float(num / den)


def eval_nss(pred: np.ndarray, fixmap: np.ndarray) -> float:
    """Normalized Scanpath Saliency. Higher is better."""
    p = pred.ravel().astype(np.float64)
    f = fixmap.ravel().astype(np.float64)
    f = (f > 0.5).astype(np.float64)

    if f.sum() == 0:
        return 0.0

    p_mean = p.mean()
    p_std = p.std() + EPS
    p_norm = (p - p_mean) / p_std

    return float(np.sum(p_norm * f) / f.sum())


def eval_sim(pred: np.ndarray, gt: np.ndarray) -> float:
    """
    Similarity metric (histogram intersection). Higher is better.
    Both maps are normalised to sum to 1 before comparing.
    """
    p = pred.ravel().astype(np.float64)
    q = gt.ravel().astype(np.float64)

    p = np.maximum(p, 0)
    q = np.maximum(q, 0)
    p = p / (p.sum() + EPS)
    q = q / (q.sum() + EPS)

    return float(np.sum(np.minimum(p, q)))


def eval_auc_judd(pred: np.ndarray, fixmap: np.ndarray, n_splits: int = 100) -> float:
    """
    AUC-Judd: area under the ROC curve using fixation points as positives.
    Higher is better.
    """
    p = pred.ravel().astype(np.float64)
    f = (fixmap.ravel() > 0.5).astype(bool)

    if f.sum() == 0 or (~f).sum() == 0:
        return 0.5

    pos = p[f]
    neg = p[~f]

    thresholds = np.linspace(0, 1, n_splits + 1)
    tpr = np.zeros(len(thresholds))
    fpr = np.zeros(len(thresholds))

    for i, th in enumerate(thresholds):
        tpr[i] = (pos >= th).mean()
        fpr[i] = (neg >= th).mean()

    # Sort by FPR for proper AUC integration
    idx = np.argsort(fpr)
    fpr = fpr[idx]
    tpr = tpr[idx]

    return float(np.trapz(tpr, fpr))


def compute_all_metrics(
    pred: np.ndarray,
    gt: np.ndarray,
    fixmap: np.ndarray | None = None,
) -> Dict[str, float]:
    """Compute all saliency metrics. Returns a dict."""
    metrics = {
        "KL": eval_kl(pred, gt),
        "CC": eval_cc(pred, gt),
        "SIM": eval_sim(pred, gt),
    }
    if fixmap is not None:
        metrics["NSS"] = eval_nss(pred, fixmap)
        metrics["AUC-J"] = eval_auc_judd(pred, fixmap)
    return metrics
