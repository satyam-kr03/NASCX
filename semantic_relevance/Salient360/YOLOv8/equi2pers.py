"""
Equirectangular ↔ Tangent-plane (gnomonic) projection utilities.

Provides:
  - equirect_to_patches(): extract perspective patches from an equirectangular image
  - patch_bbox_to_equirect(): convert a bounding box in patch pixel coords back to
    equirectangular pixel coords
"""

import math
import numpy as np
import cv2
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class PatchInfo:
    """Metadata for a single tangent-plane patch."""
    index: int                        # patch ID
    theta_center: float               # azimuth of patch centre (radians)
    phi_center: float                 # elevation of patch centre (radians)
    fov_h: float                      # horizontal FoV (radians)
    fov_v: float                      # vertical FoV (radians)
    image: np.ndarray = None          # the extracted patch (H, W, 3)


def build_patch_centres(nrows: int,
                        num_cols: List[int],
                        phi_centers_deg: List[float]) -> List[Tuple[float, float]]:
    """
    Compute patch centre directions (theta, phi) in radians.

    Returns a list of (theta_rad, phi_rad) for every patch.
    """
    centres = []
    for i, n_cols in enumerate(num_cols):
        theta_interval = 360.0 / n_cols
        phi_rad = math.radians(phi_centers_deg[i])
        for j in range(n_cols):
            theta_deg = j * theta_interval + theta_interval / 2.0
            theta_rad = math.radians(theta_deg)
            centres.append((theta_rad, phi_rad))
    return centres


def _gnomonic_grid(patch_w: int, patch_h: int,
                   theta0: float, phi0: float,
                   fov_h: float, fov_v: float) -> Tuple[np.ndarray, np.ndarray]:
    """
    Build the inverse gnomonic projection sampling grid.

    For every pixel (u, v) in the output patch, compute the corresponding
    (lon, lat) on the sphere.  Returns two arrays of shape (patch_h, patch_w)
    with longitude and latitude in radians.
    """
    # Tangent plane coordinates [-1, 1] scaled by half-FoV
    u = np.linspace(-1, 1, patch_w, dtype=np.float64) * math.tan(fov_h / 2)
    v = np.linspace(-1, 1, patch_h, dtype=np.float64) * math.tan(fov_v / 2)
    uu, vv = np.meshgrid(u, v)   # (patch_h, patch_w)

    # Distance from optical axis on the tangent plane
    rho = np.sqrt(uu ** 2 + vv ** 2)
    c = np.arctan(rho)

    sin_c = np.sin(c)
    cos_c = np.cos(c)
    sin_phi0 = math.sin(phi0)
    cos_phi0 = math.cos(phi0)

    # Inverse gnomonic: tangent plane → spherical
    lat = np.arcsin(cos_c * sin_phi0 + (vv * sin_c * cos_phi0) / np.where(rho == 0, 1, rho))
    lon = theta0 + np.arctan2(
        uu * sin_c,
        rho * cos_phi0 * cos_c - vv * sin_phi0 * sin_c
    )

    # Handle the singular point at rho == 0
    lat = np.where(rho == 0, phi0, lat)
    lon = np.where(rho == 0, theta0, lon)

    return lon, lat


def _lonlat_to_equirect_pixel(lon: np.ndarray, lat: np.ndarray,
                               erp_w: int, erp_h: int) -> Tuple[np.ndarray, np.ndarray]:
    """Convert (lon, lat) in radians to equirectangular pixel coordinates."""
    # lon ∈ [0, 2π) → x ∈ [0, erp_w)
    x = (lon / (2 * math.pi)) * erp_w
    x = x % erp_w  # wrap around

    # lat ∈ [-π/2, π/2] → y ∈ [0, erp_h), with y=0 at the top (north pole)
    y = (0.5 - lat / math.pi) * erp_h
    y = np.clip(y, 0, erp_h - 1)

    return x.astype(np.float32), y.astype(np.float32)


def equirect_to_patches(equirect: np.ndarray,
                        nrows: int,
                        num_cols: List[int],
                        phi_centers_deg: List[float],
                        fov_deg: float,
                        patch_size: Tuple[int, int]) -> List[PatchInfo]:
    """
    Extract perspective (tangent-plane) patches from an equirectangular image.

    Parameters
    ----------
    equirect : np.ndarray
        Input equirectangular image of shape (H, W, 3), uint8 BGR or RGB.
    nrows, num_cols, phi_centers_deg :
        Patch layout — see config.PatchConfig.
    fov_deg : float
        Field of view in degrees (same for horizontal and vertical).
    patch_size : (width, height)
        Output resolution per patch.

    Returns
    -------
    List[PatchInfo]
        One entry per patch, with .image populated.
    """
    erp_h, erp_w = equirect.shape[:2]
    patch_w, patch_h = patch_size
    fov_rad = math.radians(fov_deg)

    centres = build_patch_centres(nrows, num_cols, phi_centers_deg)
    patches: List[PatchInfo] = []

    for idx, (theta0, phi0) in enumerate(centres):
        # Build the sampling grid: for every output pixel, find the source pixel
        lon, lat = _gnomonic_grid(patch_w, patch_h, theta0, phi0, fov_rad, fov_rad)
        src_x, src_y = _lonlat_to_equirect_pixel(lon, lat, erp_w, erp_h)

        # Use cv2.remap for bilinear sampling
        patch_img = cv2.remap(
            equirect,
            src_x, src_y,
            interpolation=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_WRAP,
        )

        patches.append(PatchInfo(
            index=idx,
            theta_center=theta0,
            phi_center=phi0,
            fov_h=fov_rad,
            fov_v=fov_rad,
            image=patch_img,
        ))

    return patches


def patch_pixel_to_equirect(px: float, py: float,
                            patch_info: PatchInfo,
                            patch_size: Tuple[int, int],
                            erp_w: int, erp_h: int) -> Tuple[float, float]:
    """
    Convert a single pixel coordinate in a tangent patch to equirectangular coords.

    Parameters
    ----------
    px, py : float
        Pixel coordinate in the patch (0-indexed,  x = col, y = row).
    patch_info : PatchInfo
        Metadata of the patch (centre direction, FoV).
    patch_size : (width, height)
    erp_w, erp_h : int
        Equirectangular image dimensions.

    Returns
    -------
    (ex, ey) : float
        Pixel coordinates in the equirectangular image.
    """
    patch_w, patch_h = patch_size

    # Normalise to [-1, 1] and scale by tan(half-FoV)
    u = ((px / (patch_w - 1)) * 2 - 1) * math.tan(patch_info.fov_h / 2)
    v = ((py / (patch_h - 1)) * 2 - 1) * math.tan(patch_info.fov_v / 2)

    theta0 = patch_info.theta_center
    phi0 = patch_info.phi_center

    rho = math.sqrt(u ** 2 + v ** 2)
    if rho < 1e-10:
        lon, lat = theta0, phi0
    else:
        c = math.atan(rho)
        sin_c = math.sin(c)
        cos_c = math.cos(c)
        lat = math.asin(cos_c * math.sin(phi0) + (v * sin_c * math.cos(phi0)) / rho)
        lon = theta0 + math.atan2(
            u * sin_c,
            rho * math.cos(phi0) * cos_c - v * math.sin(phi0) * sin_c,
        )

    # lon → x
    ex = (lon / (2 * math.pi)) * erp_w
    ex = ex % erp_w

    # lat → y (y=0 at north pole)
    ey = (0.5 - lat / math.pi) * erp_h
    ey = max(0, min(erp_h - 1, ey))

    return ex, ey


def patch_bbox_to_equirect(x1: float, y1: float, x2: float, y2: float,
                           patch_info: PatchInfo,
                           patch_size: Tuple[int, int],
                           erp_w: int, erp_h: int,
                           n_samples: int = 16) -> Tuple[float, float, float, float]:
    """
    Convert a bounding box from patch pixel coordinates to equirectangular coordinates.

    Because the gnomonic mapping is non-linear, we sample points along all four
    edges of the box, project each to equirectangular space, and take the
    bounding rectangle.

    Parameters
    ----------
    x1, y1, x2, y2 :
        Top-left and bottom-right corners in patch pixel coords.
    n_samples :
        Number of sample points per edge for an accurate bounding box.

    Returns
    -------
    (ex1, ey1, ex2, ey2) in equirectangular pixel coordinates.
    If the box wraps around the 360° boundary, ex2 may be > erp_w
    (the caller should handle wrap-around).
    """
    # Sample points along the four edges
    edge_pts = []
    for t in np.linspace(0, 1, n_samples):
        # top edge
        edge_pts.append((x1 + t * (x2 - x1), y1))
        # bottom edge
        edge_pts.append((x1 + t * (x2 - x1), y2))
        # left edge
        edge_pts.append((x1, y1 + t * (y2 - y1)))
        # right edge
        edge_pts.append((x2, y1 + t * (y2 - y1)))

    equirect_pts = [
        patch_pixel_to_equirect(px, py, patch_info, patch_size, erp_w, erp_h)
        for px, py in edge_pts
    ]
    ex_arr = np.array([p[0] for p in equirect_pts])
    ey_arr = np.array([p[1] for p in equirect_pts])

    # Handle potential 360° wrap-around:
    # If the range of longitudes spans more than half the image, the box likely
    # wraps around the seam.
    x_range = ex_arr.max() - ex_arr.min()
    if x_range > erp_w / 2:
        # Shift coordinates so the seam is not in the middle of the box
        ex_arr_shifted = (ex_arr + erp_w / 2) % erp_w
        ex1_out = ex_arr_shifted.min() - erp_w / 2
        ex2_out = ex_arr_shifted.max() - erp_w / 2
        # Normalise back
        ex1_out = ex1_out % erp_w
        ex2_out = ex2_out % erp_w
        if ex2_out < ex1_out:
            ex2_out += erp_w  # signal wrap-around
    else:
        ex1_out = ex_arr.min()
        ex2_out = ex_arr.max()

    ey1_out = ey_arr.min()
    ey2_out = ey_arr.max()

    return float(ex1_out), float(ey1_out), float(ex2_out), float(ey2_out)
