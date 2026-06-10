"""
Highlight lokalizasyon haritası — blown piksel yüzdesini grid hücrelerine böler.

Motivasyon: Global highlight_clip_pct hangi bölgenin blown olduğunu söylemez.
Blown gökyüzü genellikle kabul edilebilir; blown yüz hiçbir zaman kabul edilemez.
Bu modül her grid hücresi için ayrı kırpılma yüzdesi hesaplar.
"""

from __future__ import annotations

import numpy as np
from PIL import Image

from core.config import SHARP_GRID_COLS, SHARP_GRID_ROWS

# Piksel değeri bu eşik üzerindeyse "blown" sayılır
_BLOWN_THRESHOLD = 248


def compute_highlight_map(pil_img: Image.Image) -> dict:
    """
    Returns:
        grid            — rows × cols, her hücre blown piksel yüzdesi (0-100)
        rows / cols     — grid boyutu
        worst_cell      — [row, col] en çok blown olan hücre
        worst_pct       — worst_cell blown yüzdesi
        has_critical    — herhangi bir hücre > %30 blown ise True
        global_pct      — toplam blown yüzde (histogram'dan zaten var ama burada tutarlı)
    """
    arr  = np.array(pil_img.convert("RGB"), dtype=np.uint8)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    blown = (r >= _BLOWN_THRESHOLD) | (g >= _BLOWN_THRESHOLD) | (b >= _BLOWN_THRESHOLD)

    H, W   = blown.shape
    rows   = SHARP_GRID_ROWS
    cols   = SHARP_GRID_COLS
    cell_h = H // rows
    cell_w = W // cols

    if cell_h < 1 or cell_w < 1:
        empty = [[0.0] * cols for _ in range(rows)]
        return {
            "grid": empty, "rows": rows, "cols": cols,
            "worst_cell": [0, 0], "worst_pct": 0.0,
            "has_critical": False, "global_pct": 0.0,
        }

    grid: list[list[float]] = []
    for ri in range(rows):
        row = []
        for ci in range(cols):
            cell  = blown[ri*cell_h:(ri+1)*cell_h, ci*cell_w:(ci+1)*cell_w]
            pct   = float(cell.sum() / max(cell.size, 1) * 100)
            row.append(round(pct, 1))
        grid.append(row)

    flat    = [(r, c, grid[r][c]) for r in range(rows) for c in range(cols)]
    worst   = max(flat, key=lambda x: x[2])
    global_pct = round(float(blown.sum() / max(blown.size, 1) * 100), 2)

    return {
        "grid":         grid,
        "rows":         rows,
        "cols":         cols,
        "worst_cell":   [worst[0], worst[1]],
        "worst_pct":    worst[2],
        "has_critical": any(v > 30 for _, _, v in flat),
        "global_pct":   global_pct,
    }
