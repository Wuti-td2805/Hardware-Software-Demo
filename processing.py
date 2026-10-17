import numpy as np
import uuid
from datetime import datetime, timezone

def fit_model(rows, adc_max, stock):
    a = np.asarray(rows, dtype=float)
    if a.ndim != 2 or a.shape[1] != 2 or len(a) < 3:
        raise ValueError("Enter at least three standards, including 0% blank.")
    if not np.isfinite(a).all():
        raise ValueError("Every standard needs a finite percentage and ADC value.")
    x, y = a[:, 0], a[:, 1]
    if (x < 0).any() or (x > 100).any() or (y < 0).any() or (y > adc_max).any():
        raise ValueError("Percentages must be 0–100 and ADC values within the selected range.")
    if len(np.unique(x)) < 3 or 0 not in x:
        raise ValueError("Use at least three distinct dilution levels, including 0% blank.")
    if (y == adc_max).any():
        raise ValueError("A standard is at the ADC ceiling. Reduce exposure or gain and recalibrate.")
    levels = np.unique(x)
    means = np.array([y[x == v].mean() for v in levels])
    delta = np.diff(means)
    warnings = []
    if not ((delta > 0).all() or (delta < 0).all()):
        warnings.append("Some readings reverse direction. The line summarizes the overall trend; repeat measurements to check variability.")
    slope, intercept = np.polyfit(x, y, 1)
    if abs(slope) < 1e-9:
        raise ValueError("Response is too flat to estimate concentration.")
    predicted = slope*x + intercept
    r2 = 1 - float(np.sum((y-predicted)**2) / np.sum((y-y.mean())**2))
    if r2 < 0.95:
        warnings.append(f"R² = {r2:.3f}: readings scatter around the line. Estimates are exploratory; check independent standards before interpreting accuracy.")
    endpoints = sorted([float(slope*levels[0]+intercept), float(slope*levels[-1]+intercept)])
    low, high = max(float(means.min()), endpoints[0]), min(float(means.max()), endpoints[1])
    if low >= high:
        raise ValueError("No usable interpolation range.")
    return dict(id=uuid.uuid4().hex, created=datetime.now(timezone.utc).isoformat(), stock=stock,
                adc_max=int(adc_max), slope=float(slope), intercept=float(intercept), r2=r2,
                signal_min=low, signal_max=high, percent_min=float(x.min()), percent_max=float(x.max()),
                standards=a.tolist(), warnings=warnings, method="ordinary_least_squares", validated=False)

def estimate(model, adc):
    if model is None:
        return None, "No calibration"
    if not np.isfinite(adc) or adc < 0 or adc > model['adc_max']:
        raise ValueError("ADC reading is outside the configured range.")
    if not model['signal_min'] <= adc <= model['signal_max']:
        return None, "Outside calibration range — no estimate"
    result = (adc-model['intercept'])/model['slope']
    if not model['percent_min']-1e-8 <= result <= model['percent_max']+1e-8:
        return None, "Outside calibration range — no estimate"
    return float(result), "Within calibration range — exploratory estimate"
