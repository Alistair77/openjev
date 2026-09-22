"""Temperature scaling: improves NLL, bounded, grouped."""

from openjev.research.calibrate import fit_temperature, fit_temperature_by_group, mean_nll


def test_fit_temperature_reduces_nll_and_stays_bounded():
    logits = [[2.0, 0.5], [0.3, 1.8], [1.5, 1.4], [0.2, 2.2]]
    labels = [0, 1, 0, 1]
    before = mean_nll(logits, labels, 1.0)
    fitted = fit_temperature(logits, labels)
    assert 0.5 <= fitted <= 5.0
    assert mean_nll(logits, labels, fitted) <= before


def test_grouped_temperatures_and_singleton_fallback():
    logits = [[2.0, 0.5], [0.3, 1.8], [0.1, 0.2]]
    labels = [0, 1, 0]
    temperatures = fit_temperature_by_group(logits, labels, ["choice", "choice", "lonely"])
    assert 0.5 <= temperatures["choice"] <= 5.0
    assert temperatures["lonely"] == 1.0
