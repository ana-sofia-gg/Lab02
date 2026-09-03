from __future__ import annotations

import numpy as np
import pytest

from ecg_af_dashboard.rr import summarize_rr


def test_constant_rr_has_zero_successive_irregularity() -> None:
    result = summarize_rr(np.array([1.0, 1.0, 1.0, 1.0]))

    assert result["count"] == 4
    assert result["median_rr_s"] == pytest.approx(1.0)
    assert result["cv_rr"] == pytest.approx(0.0)
    assert result["rmssd_s"] == pytest.approx(0.0)


def test_rr_with_insufficient_data() -> None:
    """Verifica que se rechacen menos de tres intervalos RR."""
    with pytest.raises(ValueError):
        summarize_rr(np.array([1.0, 1.2]))


def test_rr_with_invalid_values() -> None:
    """Verifica el manejo de valores no finitos (NaN, Inf)

    o negativos en la serie RR.
    """
    # Las series con NaNs o valores negativos deben ser
    # filtradas o lanzar un error controlado
    with pytest.raises((ValueError, TypeError)):
        summarize_rr(np.array([1.0, np.nan, 1.2, 1.1]))

    with pytest.raises((ValueError, TypeError)):
        summarize_rr(np.array([1.0, -0.5, 1.2, 1.1]))
