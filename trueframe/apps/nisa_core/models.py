"""
Pydantic request / response şemaları.
"""

from __future__ import annotations
from typing import Any
from pydantic import BaseModel


# ── Requests ─────────────────────────────────────────────────
class AnalyzeRequest(BaseModel):
    source: str                          # base64 data-URI veya URL
    metrics: list[str] | None = None    # None → tüm metrikler
    profile: str = "none"               # yayın profili ID'si
    name: str = "image"


class BatchRequest(BaseModel):
    images: list[AnalyzeRequest]


class ExportRequest(BaseModel):
    results: list[dict[str, Any]]
    format: str = "json"                 # "json" | "csv"


# ── Sub-responses ────────────────────────────────────────────
class TechnicalInfo(BaseModel):
    width: int
    height: int
    megapixels: float
    format: str
    color_mode: str
    dpi_x: int | None = None
    dpi_y: int | None = None


class FastMetrics(BaseModel):
    sharpness_lap: float
    noise_est: float
    colour_richness: float
    brightness: float
    contrast_rms: float


class HistogramData(BaseModel):
    hist_r: list[int]
    hist_g: list[int]
    hist_b: list[int]
    highlight_clip_pct: float
    shadow_clip_pct: float
    mean_brightness: float
    dynamic_range_score: float
    exposure_label: str


class ColorData(BaseModel):
    temperature_k: int
    temperature_label: str
    cast: str
    cast_strength: float
    dominant_colors: list[str]
    saturation: float
    grey_world_deviation: float
    channel_means: dict[str, float]


class SharpnessMap(BaseModel):
    grid: list[list[float]]
    rows: int
    cols: int
    sharpest_cell: list[int]
    softest_cell: list[int]
    global_score: float


class ProfileCheck(BaseModel):
    name: str
    key: str
    passed: bool | None
    value: str
    threshold: str
    description: str


class ProfileResult(BaseModel):
    profile_id: str
    profile_label: str
    checks: list[ProfileCheck]
    total: int
    passed: int
    failed: int
    overall_passed: bool
    score_pct: int


# ── Full analysis response ───────────────────────────────────
class AnalysisResult(BaseModel):
    name: str
    profile: str
    overall: float | None
    verdict: str
    profile_result: ProfileResult
    technical: TechnicalInfo
    exif: dict[str, Any]
    fast: FastMetrics
    histogram: HistogramData
    color: ColorData
    sharpness_map: SharpnessMap
    iqa_metrics: dict[str, Any]
    metric_meta: dict[str, Any]
    device: str
    status: str = "ok"
