import textwrap

import pytest

from app.health.config import DEFAULT_RULES_PATH, RuleConfigError, load_rules, parse_rules
from app.health.domain.rules import Aggregation, Operator, RuleType
from app.ingestion.domain.catalog import METRIC_CATALOG
from app.simulation.domain.platform import SIMULATED_PLATFORM
from app.topology.domain import ComponentType

VALID = """
rules:
  - key: R-LAT-001
    type: threshold
    failure_class: latency
    metric: probe_latency_ms
    aggregation: p95
    window_s: 60
    operator: gt
    warning: {threshold: 250, clear: 200}
    critical: {threshold: 1000, clear: 800}
    raise_after: 3
    clear_after: 3
    rationale: Slow probes.
    recommendation: Check the path.
"""


COMPONENTS = [c.key for c in SIMULATED_PLATFORM.components]


def parse(text: str) -> None:
    parse_rules(textwrap.dedent(text), METRIC_CATALOG, COMPONENTS)


def variant(old: str, new: str) -> str:
    assert old in VALID
    return VALID.replace(old, new)


def test_default_file_declares_every_rule_of_the_architecture() -> None:
    specs = {
        s.key: s.definition for s in load_rules(DEFAULT_RULES_PATH, METRIC_CATALOG, COMPONENTS)
    }

    assert sorted(specs) == [
        "R-AVAIL-001", "R-CONN-001", "R-ERR-001", "R-FRESH-001", "R-LAT-001",
        "R-QUEUE-001", "R-RES-001", "R-RES-002", "R-TEL-001",
    ]  # fmt: skip
    errors = specs["R-ERR-001"].measure
    assert errors is not None
    assert (errors.aggregation, errors.operator) == (Aggregation.SUM, Operator.GE)
    assert specs["R-TEL-001"].rule_type is RuleType.ABSENCE
    assert specs["R-FRESH-001"].targets.component_types == {
        ComponentType.HISTORIAN,
        ComponentType.ANALYTICS,
    }


def test_valid_rule_parses() -> None:
    (spec,) = parse_rules(VALID, METRIC_CATALOG, COMPONENTS)

    assert spec.definition.measure is not None
    assert spec.definition.min_samples == 1


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        (variant("clear_after: 3", "clear_after: 1").replace("clear: 200", "clear: 250")
         .replace("clear: 800", "clear: 1000"), "no hysteresis"),
        (variant("clear: 200", "clear: 300"), "breaching side"),
        (variant("{threshold: 1000, clear: 800}", "{threshold: 240, clear: 200}"),
         "beyond the warning"),
        (variant("metric: probe_latency_ms", "metric: voltage"), "not in the catalog"),
        (variant("aggregation: p95", "aggregation: ratio"), "availability_ratio"),
        (variant("type: threshold", "type: absence"), "absence"),
        (variant("window_s: 60", "window_s: 0"), "window_s"),
        (variant("key: R-LAT-001", "key: latency"), "key"),
        (variant("raise_after: 3", "raise_after: 3\n    severity: high"), "severity"),
        (variant("raise_after: 3", "raise_after: 3\n    min_samples: 13"), "min_samples exceeds"),
        (variant("raise_after: 3", "raise_after: 3\n    targets: {components: [colector-01]}"),
         "unknown target components"),
        (VALID + VALID.replace("rules:\n", ""), "duplicate rule keys"),
        ("rules: !!python/object/apply:os.system ['true']", "invalid health rule file"),
        ("rules: []", "invalid health rule file"),
    ],
)  # fmt: skip
def test_invalid_rules_are_rejected_at_load_with_their_reason(text: str, reason: str) -> None:
    with pytest.raises(RuleConfigError, match=reason):
        parse(text)
