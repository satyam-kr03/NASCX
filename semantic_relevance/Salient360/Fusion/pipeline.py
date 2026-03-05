"""
Main CLI entry point for the learned saliency fusion pipeline.

Usage:
    cd ~/Projects/NASCX/semantic_relevance/Salient360/Fusion
    conda activate mlc

    # Train the fusion model
    python pipeline.py train

    # Evaluate and compare all branches
    python pipeline.py eval --checkpoint /path/to/best_model.pt

    # Generate fused saliency maps
    python pipeline.py fuse --checkpoint /path/to/best_model.pt

    # Full pipeline: generate inputs → train → evaluate
    python pipeline.py all --video 10_Cows
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import torch

from config import (
    PipelineConfig, DataConfig, ModelConfig, LossConfig, TrainConfig,
    CHECKPOINT_DIR, FUSED_OUTPUT_DIR,
)
from dataset import build_dataloaders
from model import build_model
from train import train
from evaluate import evaluate_all, print_comparison_table, save_fused_maps


def parse_args():
    parser = argparse.ArgumentParser(
        description="Learned Fusion of Gaze + Object Saliency Maps",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python pipeline.py train
  python pipeline.py train --model conv1x1 --epochs 50 --lr 0.001
  python pipeline.py eval  --checkpoint data/Salient360/fusion_checkpoints/best_model.pt
  python pipeline.py fuse  --checkpoint data/Salient360/fusion_checkpoints/best_model.pt
  python pipeline.py all   --video 10_Cows
""",
    )

    sub = parser.add_subparsers(dest="command", help="Pipeline stage")

    # ── train ───────────────────────────────────────────────────────────
    p_train = sub.add_parser("train", help="Train the fusion model")
    _add_common_args(p_train)
    _add_train_args(p_train)

    # ── eval ────────────────────────────────────────────────────────────
    p_eval = sub.add_parser("eval", help="Evaluate and compare branches")
    _add_common_args(p_eval)
    p_eval.add_argument("--checkpoint", type=str, default=None)
    p_eval.add_argument("--split", choices=["val", "all"], default="val")
    p_eval.add_argument("--save-json", type=str, default=None,
                        help="Save metrics to JSON file")

    # ── fuse ────────────────────────────────────────────────────────────
    p_fuse = sub.add_parser("fuse", help="Generate fused saliency maps")
    _add_common_args(p_fuse)
    p_fuse.add_argument("--checkpoint", type=str, required=True)
    p_fuse.add_argument("--output-dir", type=str, default=None)

    # ── all ─────────────────────────────────────────────────────────────
    p_all = sub.add_parser("all", help="Full pipeline: train → eval")
    _add_common_args(p_all)
    _add_train_args(p_all)

    return parser.parse_args()


def _add_common_args(p):
    """Arguments shared across all commands."""
    p.add_argument("--video", type=str, nargs="*", default=None,
                   help="Restrict to specific video(s) (e.g. 10_Cows 16_Turtle)")
    p.add_argument("--device", type=str, default="cuda")
    p.add_argument("--model", type=str, default="conv1x1",
                   choices=["conv1x1", "mlp", "conv3x3"],
                   help="Fusion model variant")
    p.add_argument("--hidden", type=int, default=16,
                   help="Hidden layer width")
    p.add_argument("--n-hidden", type=int, default=2,
                   help="Number of hidden layers")
    p.add_argument("--height", type=int, default=480)
    p.add_argument("--width", type=int, default=960)


def _add_train_args(p):
    """Training-specific arguments."""
    p.add_argument("--epochs", type=int, default=50)
    p.add_argument("--batch-size", type=int, default=4)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--kl-weight", type=float, default=1.0)
    p.add_argument("--cc-weight", type=float, default=0.5)
    p.add_argument("--nss-weight", type=float, default=0.0)
    p.add_argument("--patience", type=int, default=10)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--train-ratio", type=float, default=0.75)
    p.add_argument("--dropout", type=float, default=0.0)
    p.add_argument("--num-workers", type=int, default=0)


def build_config(args) -> PipelineConfig:
    """Build a PipelineConfig from parsed CLI arguments."""
    data = DataConfig(
        height=args.height,
        width=args.width,
        video_names=args.video,
        train_ratio=getattr(args, "train_ratio", 0.75),
    )

    model = ModelConfig(
        variant=args.model,
        hidden_channels=args.hidden,
        n_hidden=args.n_hidden,
        dropout=getattr(args, "dropout", 0.0),
    )

    loss_cfg = LossConfig(
        kl_weight=getattr(args, "kl_weight", 1.0),
        cc_weight=getattr(args, "cc_weight", 0.5),
        nss_weight=getattr(args, "nss_weight", 0.0),
    )

    train_cfg = TrainConfig(
        n_epochs=getattr(args, "epochs", 50),
        batch_size=getattr(args, "batch_size", 4),
        learning_rate=getattr(args, "lr", 1e-3),
        patience=getattr(args, "patience", 10),
        device=args.device,
        seed=getattr(args, "seed", 42),
        num_workers=getattr(args, "num_workers", 0),
    )

    return PipelineConfig(
        data=data,
        model=model,
        loss=loss_cfg,
        train=train_cfg,
    )


def cmd_train(args):
    """Train the fusion model."""
    cfg = build_config(args)
    train_loader, val_loader, n_total = build_dataloaders(
        cfg.data, cfg.train, cfg.train.seed
    )
    model, history = train(cfg, train_loader, val_loader)

    # Also run evaluation after training
    best_ckpt = os.path.join(cfg.train.checkpoint_dir, "best_model.pt")
    if os.path.isfile(best_ckpt):
        print(f"\n{'='*60}")
        print("Post-training evaluation (val split)")
        print(f"{'='*60}")
        summary = evaluate_all(cfg, checkpoint_path=best_ckpt, split="val")
        print_comparison_table(summary)


def cmd_eval(args):
    """Evaluate and compare branches."""
    cfg = build_config(args)
    ckpt = args.checkpoint
    if ckpt is None:
        ckpt = os.path.join(CHECKPOINT_DIR, "best_model.pt")
        if not os.path.isfile(ckpt):
            ckpt = None

    summary = evaluate_all(cfg, checkpoint_path=ckpt, split=args.split)
    table = print_comparison_table(summary)

    if args.save_json:
        with open(args.save_json, "w") as f:
            json.dump(summary, f, indent=2)
        print(f"Metrics saved to {args.save_json}")


def cmd_fuse(args):
    """Generate fused saliency maps."""
    cfg = build_config(args)
    save_fused_maps(cfg, args.checkpoint, args.output_dir)


def cmd_all(args):
    """Full pipeline: train → evaluate."""
    print("=" * 60)
    print("STEP 1: Training fusion model")
    print("=" * 60)
    cmd_train(args)

    best_ckpt = os.path.join(CHECKPOINT_DIR, "best_model.pt")
    if os.path.isfile(best_ckpt):
        print("\n" + "=" * 60)
        print("STEP 2: Generating fused saliency maps")
        print("=" * 60)
        cfg = build_config(args)
        save_fused_maps(cfg, best_ckpt)


def main():
    args = parse_args()

    if args.command is None:
        print("Usage: python pipeline.py {train,eval,fuse,all} [options]")
        print("Run 'python pipeline.py <command> --help' for details.")
        return

    commands = {
        "train": cmd_train,
        "eval": cmd_eval,
        "fuse": cmd_fuse,
        "all": cmd_all,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
