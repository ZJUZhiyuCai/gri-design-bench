"""Check the design intervention, physiological outcomes, and paired contrasts."""

from collections.abc import Mapping
import itertools
import json
import math
from pathlib import Path
import stat

import numpy as np
import pytest


ARMS = ("responsive", "daily_flat", "daily_shift_12h")
METRICS = ("tir", "tbr70", "tbr54", "minimum")
METRIC_TOLERANCE = {"tir": 0.11, "tbr70": 0.11, "tbr54": 0.11, "minimum": 0.02}
FIELDS = {"patient", "seed", "variant", "arm", "rate_u_min", "daily_dose_u", *METRICS}
OUTPUT = Path("/app/output/results.json")


def unique_keys(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError(f"Duplicate key: {key}")
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError(f"Nonfinite JSON value: {value}")


def finite_number(value):
    return type(value) in (int, float) and abs(value) <= 1e12 and math.isfinite(value)


def finite_list(values, size):
    return isinstance(values, list) and len(values) == size and all(finite_number(value) for value in values)


def scenario_key(row):
    return row["patient"], row["seed"], row["variant"], row["arm"]


@pytest.fixture(scope="session")
def expected():
    path = Path(__file__).with_name("reference.json")
    try:
        value = json.loads(path.read_text(), object_pairs_hook=unique_keys, parse_constant=reject_constant)
        panel = value["panel"]
        required = set(itertools.product(panel["instance"]["patients"], panel["seeds"], panel["instance"]["variants"], ARMS))
        rows = {scenario_key(row): row for row in value["rows"]}
        if set(rows) != required or len(rows) != len(value["rows"]):
            raise ValueError("Reference coverage differs from the case definition")
        if any(not finite_list(row["rate_u_min"], 1440) or not finite_list(row["daily_dose_u"], 3)
               or not all(finite_number(row[m]) for m in METRICS) for row in rows.values()):
            raise ValueError("Invalid numeric reference")
    except (OSError, TypeError, ValueError, KeyError) as exc:
        pytest.exit(f"Verifier reference error: {exc}", returncode=3)
    return rows


@pytest.fixture(scope="session")
def submission(expected):
    try:
        info = OUTPUT.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > 16 * 1024 * 1024:
            raise ValueError("results.json must be a regular file of at most 16 MiB")
        value = json.loads(OUTPUT.read_text(), object_pairs_hook=unique_keys, parse_constant=reject_constant)
    except (OSError, ValueError, RecursionError) as exc:
        pytest.fail(f"Missing or invalid results.json: {exc}", pytrace=False)

    assert isinstance(value, Mapping) and set(value) == {"rows", "mean_responsive_minus_control"}
    assert isinstance(value["rows"], list) and len(value["rows"]) == len(expected)
    rows = {}
    for row in value["rows"]:
        assert isinstance(row, Mapping) and set(row) == FIELDS, "Row fields differ from the schema"
        assert all(isinstance(row[k], str) for k in ("patient", "variant", "arm")) and type(row["seed"]) is int
        key = scenario_key(row)
        assert key in expected and key not in rows, f"Unexpected or duplicate scenario: {key}"
        assert finite_list(row["rate_u_min"], 1440) and min(row["rate_u_min"]) >= 0, key
        assert finite_list(row["daily_dose_u"], 3) and min(row["daily_dose_u"]) >= 0, key
        assert all(finite_number(row[m]) for m in METRICS), key
        assert all(0 <= row[m] <= 100 for m in ("tir", "tbr70", "tbr54")), key
        rows[key] = row

    effects = value["mean_responsive_minus_control"]
    assert isinstance(effects, Mapping) and set(effects) == set(ARMS[1:])
    for metrics in effects.values():
        assert isinstance(metrics, Mapping) and set(metrics) == set(METRICS)
        assert all(finite_number(value) for value in metrics.values())
    return rows, effects


def test_complete_scenario_matrix(submission, expected):
    """Every prescribed arm appears once for every patient and meal scenario."""
    rows, _ = submission
    assert set(rows) == set(expected)


def test_responsive_schedule(submission, expected):
    """Responsive rates follow the fixed formulation on each meal scenario."""
    rows, _ = submission
    for key in rows:
        if key[-1] == "responsive":
            np.testing.assert_allclose(rows[key]["rate_u_min"], expected[key]["rate_u_min"], rtol=0, atol=2e-6, err_msg=str(key))


def test_daily_dose_and_timing(submission):
    """Controls retain the common warmup and preserve dose on each later day."""
    rows, _ = submission
    for key, row in rows.items():
        rates = np.asarray(row["rate_u_min"]).reshape(3, 480)
        original = np.asarray(rows[(*key[:3], "responsive")]["rate_u_min"]).reshape(3, 480)
        np.testing.assert_allclose(row["daily_dose_u"], 3 * rates.sum(axis=1), rtol=0, atol=2e-5, err_msg=str(key))
        np.testing.assert_allclose(rates.sum(axis=1) * 3, original.sum(axis=1) * 3, rtol=0, atol=2e-5, err_msg=str(key))
        np.testing.assert_allclose(rates[0], original[0], rtol=0, atol=2e-7, err_msg=str(key))
        if key[-1] == "daily_flat":
            uniform = np.broadcast_to(original[1:].mean(axis=1, keepdims=True), (2, 480))
            np.testing.assert_allclose(rates[1:], uniform, rtol=0, atol=2e-7, err_msg=str(key))
        elif key[-1] == "daily_shift_12h":
            np.testing.assert_allclose(rates[1:], np.roll(original[1:], 240, axis=1), rtol=0, atol=2e-7, err_msg=str(key))


def test_replayed_glucose_outcomes(submission, expected):
    """The matched replays yield the required time fractions and sampled minima."""
    rows, _ = submission
    for key, row in rows.items():
        for metric in METRICS:
            assert row[metric] == pytest.approx(expected[key][metric], rel=0, abs=METRIC_TOLERANCE[metric]), (key, metric)


def test_paired_effects(submission):
    """Report the signed effects with the prescribed equal scenario weighting."""
    rows, effects = submission
    for arm in ARMS[1:]:
        for metric in METRICS:
            values = [row[metric] - rows[(*key[:3], arm)][metric] for key, row in rows.items() if key[-1] == "responsive"]
            estimate = sum(values) / len(values)
            assert effects[arm][metric] == pytest.approx(estimate, rel=0, abs=2e-5), (arm, metric)
