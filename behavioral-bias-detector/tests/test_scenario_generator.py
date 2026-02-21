from src.scenarios.bias_templates import MarketRegime, ScenarioGenerator
from src.utils.pit_controller import PointInTimeController


def test_anchoring_pair_has_distinct_metadata():
    generator = ScenarioGenerator(seed=7, pit_controller=PointInTimeController())
    high, low = generator.generate_anchoring_pair(MarketRegime.BULL)

    assert high["scenario_metadata"]["anchor_type"] == "high"
    assert low["scenario_metadata"]["anchor_type"] == "low"
    assert high["anchor_pair_key"] == low["anchor_pair_key"]
    assert high["anchor_value"] != low["anchor_value"]


def test_generate_all_scenarios_count():
    generator = ScenarioGenerator(seed=7, pit_controller=PointInTimeController())
    scenarios = generator.generate_all_scenarios()
    # 4 regimes x (2 anchoring + 3 single scenarios)
    assert len(scenarios) == 20

