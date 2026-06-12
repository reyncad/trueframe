"""
Bölgesel keskinlik haritası — Laplacian varyansını grid hücrelerine böler.
"""

from __future__ import annotations

import numpy as np
from PIL import Image
from scipy.signal import convolve2d

from core.config import SHARP_GRID_ROWS, SHARP_GRID_COLS

_LAP = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float32)


def compute_sharpness_map(pil_img: Image.Image) -> dict:
    """
    Görseli SHARP_GRID_ROWS × SHARP_GRID_COLS hücreye böler,
    her hücrenin Laplacian varyansını hesaplar.

    Returns:
        grid            — rows × cols, değerler 0-100 normalize
        rows / cols     — grid boyutu
        sharpest_cell   — [row, col] en keskin hücre
        softest_cell    — [row, col] en yumuşak hücre
        global_score    — ham ortalama Laplacian varyansı
    """
    gray = np.array(pil_img.convert("L"), dtype=np.float32)
    lap  = convolve2d(gray, _LAP, mode="valid")

    rows, cols = SHARP_GRID_ROWS, SHARP_GRID_COLS
    cell_h = lap.shape[0] // rows
    cell_w = lap.shape[1] // cols

    if cell_h < 1 or cell_w < 1:
        # Görsel çok küçük
        empty = [[0.0] * cols for _ in range(rows)]
        return {
            "grid": empty, "rows": rows, "cols": cols,
            "sharpest_cell": [0, 0], "softest_cell": [0, 0],
            "global_score": 0.0,
        }

    raw_grid: list[list[float]] = []
    for r in range(rows):
        row_vals = []
        for c in range(cols):
            cell = lap[r * cell_h:(r + 1) * cell_h, c * cell_w:(c + 1) * cell_w]
            row_vals.append(float(cell.var()))
        raw_grid.append(row_vals)

    flat = [v for row in raw_grid for v in row]
    global_score = round(float(np.mean(flat)), 2)
    max_val = max(flat) if flat else 1.0
    if max_val == 0:
        max_val = 1.0

    grid_norm = [
        [round(v / max_val * 100, 1) for v in row]
        for row in raw_grid
    ]

    # En keskin / en yumuşak hücre
    indexed = [
        (r, c, grid_norm[r][c])
        for r in range(rows)
        for c in range(cols)
    ]
    sharpest = max(indexed, key=lambda x: x[2])
    softest  = min(indexed, key=lambda x: x[2])

    return {
        "grid":          grid_norm,
        "rows":          rows,
        "cols":          cols,
        "sharpest_cell": [sharpest[0], sharpest[1]],
        "softest_cell":  [softest[0],  softest[1]],
        "global_score":  global_score,
    }
