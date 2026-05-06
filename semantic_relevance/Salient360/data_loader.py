"""
Salient360 Video Dataset — Data Loader
=======================================

Robust data loader for the Salient360! video dataset (David et al., MMSys 2018).
Supports gaze-based saliency models and object-level saliency models.

Dataset structure (expected at `data_root`):
    H/SalMaps/          – Binary saliency maps from head-only movements
    H/Scanpaths/        – CSV scanpath files   from head-only movements
    HE/SalMaps/         – Binary saliency maps from head+eye  movements
    HE/Scanpaths/L/     – CSV scanpaths (left  eye)
    HE/Scanpaths/R/     – CSV scanpaths (right eye)
    Stimuli/            – (optional) equirectangular MP4 video stimuli

Saliency map binaries
    Filename format : ``{id}_{name}_{W}x{H}x{F}_{bits}b.bin``
    Layout          : float32 values stored row-wise, frame after frame.

Scanpath CSVs
    Columns: ``Idx, lon, lat, start_ts, duration, start_frame, end_frame``
    Observer boundaries are signalled by ``Idx`` resetting to 0.
    Longitude / latitude are normalised to [0, 1].

Usage
-----
>>> from data_loader import Salient360Dataset
>>> ds = Salient360Dataset("/path/to/Salient360")
>>> ds.summary()                        # overview table
>>> sal = ds.load_saliency_map("H", "1_PortoRiverside", frame=10)
>>> scanpaths = ds.load_scanpaths("H", "1_PortoRiverside")
>>> fixmap = ds.fixation_map("H", "1_PortoRiverside", frame_range=(0, 25))

PyTorch integration
-------------------
>>> torch_ds = ds.to_torch(modality="H", output="saliency",
...                        frames_per_sample=5, transform=my_transform)
>>> loader = torch.utils.data.DataLoader(torch_ds, batch_size=8)

References
----------
E. David, J. Gutiérrez, P. Le Callet, A. Coutrot, M. Perreira Da Silva,
"A Dataset of Head and Eye Movements for 360° Videos",
ACM MMSys 2018 – dataset and toolbox track.
"""

from __future__ import annotations

import logging
import re
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    Sequence,
    Tuple,
    Union,
)

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MODALITIES = ("H", "HE")
_EYE_SIDES = ("L", "R")
_DTYPE_MAP = {16: np.float16, 32: np.float32, 64: np.float64}
_BIN_RE = re.compile(r"^(\d+_\w+?)_(\d+)x(\d+)x(\d+)_(\d+)b\.bin$")
_DEFAULT_RESOLUTION = (2048, 1024)  # (width, height) of equirectangular maps

Modality = Literal["H", "HE"]
EyeSide = Literal["L", "R"]


# ---------------------------------------------------------------------------
# Metadata container
# ---------------------------------------------------------------------------


@dataclass
class VideoMeta:
    """Metadata for a single Salient360 video stimulus."""

    video_id: int
    name: str  # e.g. "1_PortoRiverside"
    width: int = 0
    height: int = 0
    num_frames: int = 0
    dtype_bits: int = 32
    has_h_salmap: bool = False
    has_he_salmap: bool = False
    has_h_scanpath: bool = False
    has_he_scanpath_l: bool = False
    has_he_scanpath_r: bool = False
    h_salmap_path: Optional[Path] = None
    he_salmap_path: Optional[Path] = None
    h_scanpath_path: Optional[Path] = None
    he_scanpath_l_path: Optional[Path] = None
    he_scanpath_r_path: Optional[Path] = None
    h_preview_path: Optional[Path] = None
    he_preview_path: Optional[Path] = None

    @property
    def dtype(self) -> np.dtype:
        return np.dtype(_DTYPE_MAP.get(self.dtype_bits, np.float32))

    @property
    def frame_nbytes(self) -> int:
        """Number of bytes for a single saliency‑map frame."""
        return self.width * self.height * (self.dtype_bits // 8)


# ---------------------------------------------------------------------------
# Scanpath parsing helpers
# ---------------------------------------------------------------------------

# Column indices used across H and HE scanpath CSVs
_COL_IDX = 0
_COL_LON = 1
_COL_LAT = 2
_COL_TS = 3
_COL_DUR = 4
_COL_SFRAME = 5
_COL_EFRAME = 6

SCANPATH_COLUMNS = [
    "fixation_idx",
    "longitude",
    "latitude",
    "start_timestamp",
    "duration",
    "start_frame",
    "end_frame",
]


def _parse_scanpath_csv(path: Path) -> np.ndarray:
    """Load a scanpath CSV into an (N, 7) float64 array.

    Handles the header line starting with ``#`` and copes with blank
    trailing lines, NaNs, or inconsistent whitespace.
    """
    rows: list[np.ndarray] = []
    with open(path, "r") as fh:
        for lineno, raw in enumerate(fh, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(",")
            if len(parts) < 7:
                logger.warning(
                    "%s:%d – expected 7 columns, got %d; skipping.",
                    path.name,
                    lineno,
                    len(parts),
                )
                continue
            try:
                row = np.array([float(p) for p in parts[:7]], dtype=np.float64)
            except ValueError:
                logger.warning(
                    "%s:%d – non‑numeric value; skipping.", path.name, lineno
                )
                continue
            rows.append(row)
    if not rows:
        raise ValueError(f"No valid fixation rows found in {path}")
    return np.stack(rows)


def _split_observers(fixations: np.ndarray) -> list[np.ndarray]:
    """Split a merged fixation array into per‑observer sequences.

    Observer boundaries are detected where ``fixation_idx`` resets to 0.
    """
    idx_col = fixations[:, _COL_IDX]
    # The first row always starts a new observer
    starts = np.where(idx_col == 0)[0]
    observers: list[np.ndarray] = []
    for i, s in enumerate(starts):
        e = starts[i + 1] if i + 1 < len(starts) else len(fixations)
        observers.append(fixations[s:e])
    return observers


# ---------------------------------------------------------------------------
# Saliency‑map binary reader
# ---------------------------------------------------------------------------


class SaliencyMapReader:
    """Lazy, frame‑level reader for Salient360 binary saliency files.

    Parameters
    ----------
    path : Path
        Binary ``.bin`` file.
    width, height, num_frames : int
        Spatial and temporal dimensions (parsed from filename).
    dtype_bits : int
        Floating‑point precision in bits (16, 32, or 64).
    """

    def __init__(
        self,
        path: Path,
        width: int,
        height: int,
        num_frames: int,
        dtype_bits: int = 32,
    ) -> None:
        self.path = path
        self.width = width
        self.height = height
        self.num_frames = num_frames
        self.dtype = _DTYPE_MAP.get(dtype_bits, np.float32)
        self._pixels = width * height
        self._frame_bytes = self._pixels * np.dtype(self.dtype).itemsize
        # Validate file size
        actual = path.stat().st_size
        expected = self._frame_bytes * num_frames
        if actual < expected:
            warnings.warn(
                f"{path.name}: file is {actual} bytes but expected "
                f"≥ {expected} bytes for {num_frames} frames."
            )

    # --- single frame ---------------------------------------------------

    def read_frame(self, frame_idx: int) -> np.ndarray:
        """Return a single saliency frame as a (H, W) float array."""
        if frame_idx < 0 or frame_idx >= self.num_frames:
            raise IndexError(
                f"Frame {frame_idx} out of range [0, {self.num_frames})"
            )
        with open(self.path, "rb") as f:
            f.seek(self._frame_bytes * frame_idx)
            data = np.fromfile(f, count=self._pixels, dtype=self.dtype)
        return data.reshape(self.height, self.width)

    # --- batch frames ----------------------------------------------------

    def read_frames(
        self, start: int = 0, count: Optional[int] = None
    ) -> np.ndarray:
        """Return a (T, H, W) array for *count* consecutive frames starting at *start*."""
        if count is None:
            count = self.num_frames - start
        end = start + count
        if start < 0 or end > self.num_frames:
            raise IndexError(
                f"Frame range [{start}, {end}) out of [0, {self.num_frames})"
            )
        with open(self.path, "rb") as f:
            f.seek(self._frame_bytes * start)
            data = np.fromfile(
                f, count=self._pixels * count, dtype=self.dtype
            )
        return data.reshape(count, self.height, self.width)

    # --- aggregate (temporal mean) ---------------------------------------

    def mean_saliency(
        self,
        start: int = 0,
        count: Optional[int] = None,
        batch_size: int = 50,
    ) -> np.ndarray:
        """Compute the temporal‑mean saliency map without loading all frames at once."""
        if count is None:
            count = self.num_frames - start
        accum = np.zeros((self.height, self.width), dtype=np.float64)
        remaining = count
        offset = start
        while remaining > 0:
            n = min(batch_size, remaining)
            accum += self.read_frames(offset, n).astype(np.float64).sum(axis=0)
            offset += n
            remaining -= n
        return (accum / count).astype(np.float32)

    def __len__(self) -> int:
        return self.num_frames

    def __getitem__(self, idx: int) -> np.ndarray:
        return self.read_frame(idx)

    def __repr__(self) -> str:
        return (
            f"SaliencyMapReader({self.path.name}, "
            f"{self.width}×{self.height}×{self.num_frames})"
        )


# ---------------------------------------------------------------------------
# Main dataset class
# ---------------------------------------------------------------------------


class Salient360Dataset:
    """Unified loader for the Salient360! video eye‑tracking dataset.

    Parameters
    ----------
    data_root : str | Path
        Top‑level directory containing ``H/``, ``HE/``, etc.
    resolution : tuple[int, int], optional
        Target (width, height) for fixation‑map generation.
        Defaults to ``(2048, 1024)``.
    """

    def __init__(
        self,
        data_root: Union[str, Path],
        resolution: Tuple[int, int] = _DEFAULT_RESOLUTION,
    ) -> None:
        self.root = Path(data_root).expanduser().resolve()
        if not self.root.is_dir():
            raise FileNotFoundError(f"Dataset root not found: {self.root}")
        self.resolution = resolution  # (W, H)
        self._catalog: Dict[str, VideoMeta] = {}
        self._build_catalog()
        logger.info(
            "Salient360 dataset loaded: %d videos from %s",
            len(self._catalog),
            self.root,
        )

    # ----- catalogue construction ----------------------------------------

    def _register_bin(self, modality: Modality, path: Path) -> None:
        """Register a binary saliency‑map file into the catalogue."""
        m = _BIN_RE.match(path.name)
        if not m:
            return
        name, w, h, frames, bits = m.groups()
        w, h, frames, bits = int(w), int(h), int(frames), int(bits)
        meta = self._catalog.setdefault(
            name, VideoMeta(video_id=int(name.split("_")[0]), name=name)
        )
        # Update resolution info (prefer values from H; they should agree)
        if meta.width == 0:
            meta.width, meta.height = w, h
        meta.dtype_bits = bits
        if modality == "H":
            meta.has_h_salmap = True
            meta.h_salmap_path = path
            # Use H's frame count as primary; HE may differ slightly
            if meta.num_frames == 0:
                meta.num_frames = frames
        else:
            meta.has_he_salmap = True
            meta.he_salmap_path = path
            if meta.num_frames == 0:
                meta.num_frames = frames

    def _register_scanpath(
        self, modality: Modality, path: Path, eye: Optional[EyeSide] = None
    ) -> None:
        name_match = re.match(r"^(\d+_\w+?)_fixations\.csv$", path.name)
        if not name_match:
            return
        name = name_match.group(1)
        meta = self._catalog.setdefault(
            name, VideoMeta(video_id=int(name.split("_")[0]), name=name)
        )
        if modality == "H":
            meta.has_h_scanpath = True
            meta.h_scanpath_path = path
        elif eye == "L":
            meta.has_he_scanpath_l = True
            meta.he_scanpath_l_path = path
        elif eye == "R":
            meta.has_he_scanpath_r = True
            meta.he_scanpath_r_path = path

    def _register_preview(self, modality: Modality, path: Path) -> None:
        name_match = re.match(r"^(\d+_\w+?)_saliency\.png$", path.name)
        if not name_match:
            return
        name = name_match.group(1)
        meta = self._catalog.setdefault(
            name, VideoMeta(video_id=int(name.split("_")[0]), name=name)
        )
        if modality == "H":
            meta.h_preview_path = path
        else:
            meta.he_preview_path = path

    def _build_catalog(self) -> None:
        """Walk the directory tree and populate ``self._catalog``."""
        for mod in _MODALITIES:
            sal_dir = self.root / mod / "SalMaps"
            scan_dir = self.root / mod / "Scanpaths"

            # Saliency maps & preview PNGs
            if sal_dir.is_dir():
                for p in sorted(sal_dir.iterdir()):
                    if p.suffix == ".bin":
                        self._register_bin(mod, p)
                    elif p.suffix == ".png":
                        self._register_preview(mod, p)

            # Scanpaths
            if mod == "H" and scan_dir.is_dir():
                for p in sorted(scan_dir.iterdir()):
                    if p.suffix == ".csv":
                        self._register_scanpath("H", p)
            elif mod == "HE" and scan_dir.is_dir():
                for eye in _EYE_SIDES:
                    eye_dir = scan_dir / eye
                    if eye_dir.is_dir():
                        for p in sorted(eye_dir.iterdir()):
                            if p.suffix == ".csv":
                                self._register_scanpath("HE", p, eye=eye)

        # Sort by video id
        self._catalog = dict(
            sorted(self._catalog.items(), key=lambda kv: kv[1].video_id)
        )

    # ----- public query helpers ------------------------------------------

    @property
    def video_names(self) -> List[str]:
        """Sorted list of video identifiers."""
        return list(self._catalog.keys())

    @property
    def num_videos(self) -> int:
        return len(self._catalog)

    def meta(self, name: str) -> VideoMeta:
        """Return metadata for a video by name (e.g. ``'1_PortoRiverside'``)."""
        if name not in self._catalog:
            raise KeyError(
                f"Unknown video '{name}'. Available: {self.video_names}"
            )
        return self._catalog[name]

    def summary(self) -> str:
        """Pretty‑printed overview of the dataset catalogue."""
        lines = [
            f"Salient360 Dataset  –  {self.root}",
            f"{'Name':<30} {'W':>5} {'H':>5} {'Frames':>6}  "
            f"{'H_sal':>5} {'HE_sal':>6} {'H_sp':>5} {'HE_L':>5} {'HE_R':>5}",
            "-" * 100,
        ]
        for m in self._catalog.values():
            lines.append(
                f"{m.name:<30} {m.width:>5} {m.height:>5} {m.num_frames:>6}  "
                f"{'✓' if m.has_h_salmap else '✗':>5} "
                f"{'✓' if m.has_he_salmap else '✗':>6} "
                f"{'✓' if m.has_h_scanpath else '✗':>5} "
                f"{'✓' if m.has_he_scanpath_l else '✗':>5} "
                f"{'✓' if m.has_he_scanpath_r else '✗':>5}"
            )
        return "\n".join(lines)

    # ----- saliency map loading ------------------------------------------

    def saliency_reader(
        self, modality: Modality, name: str
    ) -> SaliencyMapReader:
        """Return a :class:`SaliencyMapReader` for lazy frame access.

        Parameters
        ----------
        modality : ``"H"`` | ``"HE"``
        name : str
            Video name, e.g. ``"1_PortoRiverside"``.
        """
        meta = self.meta(name)
        if modality == "H":
            if not meta.has_h_salmap:
                raise FileNotFoundError(
                    f"No H saliency map for '{name}'. "
                    f"(File may be missing or archive not extracted.)"
                )
            path = meta.h_salmap_path
        else:
            if not meta.has_he_salmap:
                raise FileNotFoundError(
                    f"No HE saliency map for '{name}'."
                )
            path = meta.he_salmap_path
        return SaliencyMapReader(
            path=path,
            width=meta.width,
            height=meta.height,
            num_frames=meta.num_frames,
            dtype_bits=meta.dtype_bits,
        )

    def load_saliency_map(
        self,
        modality: Modality,
        name: str,
        frame: Optional[int] = None,
        frame_range: Optional[Tuple[int, int]] = None,
        mean: bool = False,
    ) -> np.ndarray:
        """High‑level saliency map access.

        Parameters
        ----------
        modality : ``"H"`` | ``"HE"``
        name : str
        frame : int, optional
            Return a single frame ``(H, W)``.
        frame_range : (start, end), optional
            Return frames ``[start, end)`` → ``(T, H, W)``.
        mean : bool
            If *True*, return the temporal‑mean map ``(H, W)``.

        Returns
        -------
        np.ndarray
        """
        reader = self.saliency_reader(modality, name)
        if mean:
            start = frame_range[0] if frame_range else 0
            count = (
                (frame_range[1] - frame_range[0]) if frame_range else None
            )
            return reader.mean_saliency(start=start, count=count)
        if frame is not None:
            return reader.read_frame(frame)
        if frame_range is not None:
            s, e = frame_range
            return reader.read_frames(start=s, count=e - s)
        # Default: return the temporal‑mean saliency
        return reader.mean_saliency()

    def load_saliency_preview(
        self, modality: Modality, name: str
    ) -> Optional[np.ndarray]:
        """Load the aggregated saliency preview PNG (if available).

        Returns an RGB ``(H, W, 3)`` uint8 array or ``None``.
        """
        meta = self.meta(name)
        path = meta.h_preview_path if modality == "H" else meta.he_preview_path
        if path is None or not path.exists():
            return None
        try:
            from PIL import Image
            return np.asarray(Image.open(path).convert("RGB"))
        except ImportError:
            import matplotlib.pyplot as plt
            return plt.imread(str(path))  # fallback

    # ----- scanpath / fixation loading -----------------------------------

    def load_scanpaths(
        self,
        modality: Modality,
        name: str,
        eye: EyeSide = "L",
        split_observers: bool = True,
        as_dict: bool = False,
    ) -> Union[np.ndarray, List[np.ndarray], List[Dict[str, np.ndarray]]]:
        """Load scanpath fixations.

        Parameters
        ----------
        modality : ``"H"`` | ``"HE"``
        name : str
        eye : ``"L"`` | ``"R"``
            Only relevant when ``modality="HE"``.
        split_observers : bool
            If *True* (default), return a list with one array per observer.
        as_dict : bool
            If *True*, return each observer as a dict with named columns.

        Returns
        -------
        np.ndarray | list[np.ndarray] | list[dict]
        """
        meta = self.meta(name)
        if modality == "H":
            if not meta.has_h_scanpath:
                raise FileNotFoundError(
                    f"No H scanpath for '{name}'."
                )
            path = meta.h_scanpath_path
        else:
            if eye == "L":
                if not meta.has_he_scanpath_l:
                    raise FileNotFoundError(
                        f"No HE-L scanpath for '{name}'."
                    )
                path = meta.he_scanpath_l_path
            else:
                if not meta.has_he_scanpath_r:
                    raise FileNotFoundError(
                        f"No HE-R scanpath for '{name}'."
                    )
                path = meta.he_scanpath_r_path

        fixations = _parse_scanpath_csv(path)
        if not split_observers:
            return fixations

        observer_list = _split_observers(fixations)
        if not as_dict:
            return observer_list
        return [
            {col: obs[:, i] for i, col in enumerate(SCANPATH_COLUMNS)}
            for obs in observer_list
        ]

    def num_observers(self, modality: Modality, name: str, eye: EyeSide = "L") -> int:
        """Return the number of observers for a given video and modality."""
        fixations = self.load_scanpaths(
            modality, name, eye=eye, split_observers=False
        )
        return int(np.sum(fixations[:, _COL_IDX] == 0))

    # ----- fixation map generation ---------------------------------------

    def fixation_map(
        self,
        modality: Modality,
        name: str,
        eye: EyeSide = "L",
        frame_range: Optional[Tuple[int, int]] = None,
        resolution: Optional[Tuple[int, int]] = None,
        sigma_deg: float = 2.0,
        per_frame: bool = False,
    ) -> np.ndarray:
        """Generate a fixation‑density map from scanpath data.

        Projects normalised (lon, lat) fixations onto an equirectangular
        grid and applies a Gaussian kernel.

        Parameters
        ----------
        modality, name, eye : see :meth:`load_scanpaths`.
        frame_range : (start, end), optional
            Only use fixations within this frame range.
        resolution : (W, H), optional
            Output resolution. Defaults to ``self.resolution``.
        sigma_deg : float
            Gaussian sigma in degrees (viewport‑space).
        per_frame : bool
            If *True*, return a ``(T, H, W)`` stack with one map per frame
            in the given range; otherwise return an aggregate ``(H, W)`` map.

        Returns
        -------
        np.ndarray – float32 fixation‑density map(s), normalised to [0, 1].
        """
        W, H = resolution or self.resolution
        observers = self.load_scanpaths(
            modality, name, eye=eye, split_observers=True
        )

        # Collect fixation coordinates falling in the requested frame range
        all_fix: list[np.ndarray] = []
        for obs in observers:
            if frame_range is not None:
                mask = (obs[:, _COL_SFRAME] >= frame_range[0]) & (
                    obs[:, _COL_EFRAME] <= frame_range[1]
                )
                obs = obs[mask]
            all_fix.append(obs)
        fixations = np.concatenate(all_fix, axis=0)

        if per_frame and frame_range is not None:
            return self._per_frame_fixmap(
                fixations, frame_range, W, H, sigma_deg
            )

        return self._aggregate_fixmap(fixations, W, H, sigma_deg)

    @staticmethod
    def _aggregate_fixmap(
        fixations: np.ndarray, W: int, H: int, sigma_deg: float
    ) -> np.ndarray:
        """Build a single (H, W) fixation map from all supplied fixations."""
        from scipy.ndimage import gaussian_filter

        fmap = np.zeros((H, W), dtype=np.float64)
        if len(fixations) == 0:
            return fmap.astype(np.float32)

        # lon/lat are normalised [0,1] → pixel coordinates
        xs = np.clip((fixations[:, _COL_LON] * W).astype(int), 0, W - 1)
        ys = np.clip((fixations[:, _COL_LAT] * H).astype(int), 0, H - 1)
        np.add.at(fmap, (ys, xs), 1.0)

        # Convert sigma from degrees to pixels (360° mapped to W pixels)
        sigma_px = sigma_deg / 360.0 * W
        fmap = gaussian_filter(fmap, sigma=sigma_px)

        # Normalise to [0, 1]
        mx = fmap.max()
        if mx > 0:
            fmap /= mx
        return fmap.astype(np.float32)

    @staticmethod
    def _per_frame_fixmap(
        fixations: np.ndarray,
        frame_range: Tuple[int, int],
        W: int,
        H: int,
        sigma_deg: float,
    ) -> np.ndarray:
        """Build a (T, H, W) stack with one fixation map per frame."""
        from scipy.ndimage import gaussian_filter

        s, e = frame_range
        T = e - s
        maps = np.zeros((T, H, W), dtype=np.float32)
        sigma_px = sigma_deg / 360.0 * W

        for t in range(T):
            frame_idx = s + t
            # A fixation contributes to a frame if its frame range overlaps
            mask = (fixations[:, _COL_SFRAME] <= frame_idx) & (
                fixations[:, _COL_EFRAME] >= frame_idx
            )
            pts = fixations[mask]
            if len(pts) == 0:
                continue
            xs = np.clip((pts[:, _COL_LON] * W).astype(int), 0, W - 1)
            ys = np.clip((pts[:, _COL_LAT] * H).astype(int), 0, H - 1)
            fmap = np.zeros((H, W), dtype=np.float64)
            np.add.at(fmap, (ys, xs), 1.0)
            fmap = gaussian_filter(fmap, sigma=sigma_px)
            mx = fmap.max()
            if mx > 0:
                fmap /= mx
            maps[t] = fmap.astype(np.float32)
        return maps

    # ----- coordinate utilities ------------------------------------------

    @staticmethod
    def lonlat_to_pixel(
        lon: np.ndarray,
        lat: np.ndarray,
        width: int = 2048,
        height: int = 1024,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Convert normalised [0,1] lon/lat to pixel coordinates."""
        x = np.clip((lon * width).astype(int), 0, width - 1)
        y = np.clip((lat * height).astype(int), 0, height - 1)
        return x, y

    @staticmethod
    def lonlat_to_spherical(
        lon: np.ndarray, lat: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Convert normalised [0,1] lon/lat to radians (θ, φ).

        θ ∈ [0, 2π)  (azimuth / longitude)
        φ ∈ [-π/2, π/2]  (elevation / latitude, equator = 0)
        """
        theta = lon * 2.0 * np.pi
        phi = (lat - 0.5) * np.pi
        return theta, phi

    @staticmethod
    def lonlat_to_unit_vector(
        lon: np.ndarray, lat: np.ndarray
    ) -> np.ndarray:
        """Convert normalised [0,1] lon/lat to 3‑D unit vectors (N, 3)."""
        theta = lon * 2.0 * np.pi
        phi = (lat - 0.5) * np.pi
        x = np.cos(phi) * np.cos(theta)
        y = np.cos(phi) * np.sin(theta)
        z = np.sin(phi)
        return np.stack([x, y, z], axis=-1)

    # ----- PyTorch Dataset wrappers --------------------------------------

    def to_torch(
        self,
        modality: Modality = "H",
        output: Literal["saliency", "fixation", "both"] = "saliency",
        video_names: Optional[List[str]] = None,
        frames_per_sample: int = 1,
        stride: int = 1,
        eye: EyeSide = "L",
        sigma_deg: float = 2.0,
        transform: Optional[Callable] = None,
        target_transform: Optional[Callable] = None,
    ) -> "Salient360TorchDataset":
        """Create a PyTorch‑compatible :class:`torch.utils.data.Dataset`.

        Each sample is a dict with keys depending on *output*:

        * ``"saliency"`` → ``{"saliency": Tensor(T, H, W)}``
        * ``"fixation"`` → ``{"fixation_map": Tensor(T, H, W)}``
        * ``"both"``     → both keys present.

        All samples additionally contain ``{"name": str, "start_frame": int}``.

        Parameters
        ----------
        modality : ``"H"`` | ``"HE"``
        output : ``"saliency"`` | ``"fixation"`` | ``"both"``
        video_names : list[str], optional
            Subset of videos. Defaults to all available videos that have
            the required data files.
        frames_per_sample : int
            Temporal window length per sample.
        stride : int
            Step between consecutive samples.
        eye : ``"L"`` | ``"R"``
        sigma_deg : float
        transform : callable, optional
            Applied to the input (saliency) tensor.
        target_transform : callable, optional
            Applied to the target (fixation‑map) tensor.
        """
        try:
            import torch  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "PyTorch is required for to_torch(). "
                "Install it with:  pip install torch"
            ) from exc

        return Salient360TorchDataset(
            dataset=self,
            modality=modality,
            output=output,
            video_names=video_names,
            frames_per_sample=frames_per_sample,
            stride=stride,
            eye=eye,
            sigma_deg=sigma_deg,
            transform=transform,
            target_transform=target_transform,
        )

    # ----- dunder helpers ------------------------------------------------

    def __len__(self) -> int:
        return self.num_videos

    def __repr__(self) -> str:
        return f"Salient360Dataset({self.root}, {self.num_videos} videos)"

    def __getitem__(self, name: str) -> VideoMeta:
        return self.meta(name)

    def __contains__(self, name: str) -> bool:
        return name in self._catalog

    def __iter__(self):
        return iter(self._catalog.values())


# ---------------------------------------------------------------------------
# PyTorch Dataset wrapper
# ---------------------------------------------------------------------------


class Salient360TorchDataset:
    """PyTorch Dataset over saliency‑map frames and/or fixation‑density maps.

    Typically created via :meth:`Salient360Dataset.to_torch`.
    """

    def __init__(
        self,
        dataset: Salient360Dataset,
        modality: Modality = "H",
        output: Literal["saliency", "fixation", "both"] = "saliency",
        video_names: Optional[List[str]] = None,
        frames_per_sample: int = 1,
        stride: int = 1,
        eye: EyeSide = "L",
        sigma_deg: float = 2.0,
        transform: Optional[Callable] = None,
        target_transform: Optional[Callable] = None,
    ) -> None:
        import torch  # noqa: F401

        self.ds = dataset
        self.modality = modality
        self.output = output
        self.eye = eye
        self.sigma_deg = sigma_deg
        self.frames_per_sample = frames_per_sample
        self.stride = stride
        self.transform = transform
        self.target_transform = target_transform

        # Build an index of (video_name, start_frame) tuples
        self._index: List[Tuple[str, int]] = []
        names = video_names or dataset.video_names
        for vname in names:
            meta = dataset.meta(vname)
            # Check data availability
            has_sal = (
                meta.has_h_salmap if modality == "H" else meta.has_he_salmap
            )
            if output in ("saliency", "both") and not has_sal:
                logger.debug("Skipping %s (no saliency map).", vname)
                continue
            if output in ("fixation", "both"):
                has_sp = self._has_scanpath(meta)
                if not has_sp:
                    logger.debug("Skipping %s (no scanpath).", vname)
                    continue
            n_frames = meta.num_frames
            if n_frames == 0:
                continue
            for start in range(0, n_frames - frames_per_sample + 1, stride):
                self._index.append((vname, start))

        if not self._index:
            warnings.warn(
                "Salient360TorchDataset is empty – no valid samples found. "
                "Check modality, output type, and data availability."
            )

    def _has_scanpath(self, meta: VideoMeta) -> bool:
        if self.modality == "H":
            return meta.has_h_scanpath
        return (
            meta.has_he_scanpath_l
            if self.eye == "L"
            else meta.has_he_scanpath_r
        )

    def __len__(self) -> int:
        return len(self._index)

    def __getitem__(self, idx: int) -> Dict[str, Any]:
        import torch

        vname, start = self._index[idx]
        sample: Dict[str, Any] = {"name": vname, "start_frame": start}
        end = start + self.frames_per_sample

        if self.output in ("saliency", "both"):
            sal = self.ds.load_saliency_map(
                self.modality, vname, frame_range=(start, end)
            )
            sal_t = torch.from_numpy(sal)
            if self.transform is not None:
                sal_t = self.transform(sal_t)
            sample["saliency"] = sal_t

        if self.output in ("fixation", "both"):
            fmap = self.ds.fixation_map(
                self.modality,
                vname,
                eye=self.eye,
                frame_range=(start, end),
                sigma_deg=self.sigma_deg,
                per_frame=True,
            )
            fmap_t = torch.from_numpy(fmap)
            if self.target_transform is not None:
                fmap_t = self.target_transform(fmap_t)
            sample["fixation_map"] = fmap_t

        return sample

    def __repr__(self) -> str:
        return (
            f"Salient360TorchDataset(modality={self.modality!r}, "
            f"output={self.output!r}, samples={len(self)})"
        )


# ---------------------------------------------------------------------------
# CLI quick test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="Salient360 data loader test")
    parser.add_argument(
        "data_root",
        nargs="?",
        default="/home/teaching/Projects/NASCX/data/Salient360",
        help="Path to the Salient360 dataset root.",
    )
    args = parser.parse_args()

    ds = Salient360Dataset(args.data_root)
    print(ds.summary())

    # quick sanity checks
    first = ds.video_names[0]
    meta = ds.meta(first)
    print(f"\n--- Testing with '{first}' ---")
    print(f"  Metadata : {meta}")

    # Scanpath loading
    try:
        observers = ds.load_scanpaths("H", first)
        print(f"  H scanpath observers: {len(observers)}")
        print(f"  First observer fixations: {observers[0].shape}")
    except FileNotFoundError as e:
        print(f"  H scanpath: {e}")

    # Saliency loading
    try:
        reader = ds.saliency_reader("H", first)
        print(f"  H saliency reader: {reader}")
        frame0 = reader.read_frame(0)
        print(f"  Frame 0 shape={frame0.shape}, range=[{frame0.min():.4f}, {frame0.max():.4f}]")
    except FileNotFoundError as e:
        print(f"  H saliency: {e}")

    # Fixation map generation
    try:
        fmap = ds.fixation_map("H", first, frame_range=(0, 50))
        print(f"  Fixation map shape={fmap.shape}, range=[{fmap.min():.4f}, {fmap.max():.4f}]")
    except Exception as e:
        print(f"  Fixation map: {e}")

    print("\nDone.")
