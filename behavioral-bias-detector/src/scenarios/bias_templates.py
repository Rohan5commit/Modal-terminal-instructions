import copy
import random
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from src.utils.pit_controller import PointInTimeController


class BiasType(str, Enum):
    ANCHORING = "anchoring"
    RECENCY = "recency"
    LOSS_AVERSION = "loss_aversion"
    OVERCONFIDENCE = "overconfidence"


class MarketRegime(str, Enum):
    BULL = "bull"
    BEAR = "bear"
    CRISIS = "crisis"
    STABLE = "stable"


class ScenarioGenerator:
    """Generates bias-testing scenarios with point-in-time-safe context."""

    def __init__(self, seed: int | None = None, pit_controller: PointInTimeController | None = None):
        self.random = random.Random(seed)
        self.pit = pit_controller or PointInTimeController()

    def _base_context(self, regime: MarketRegime, days_ago: int = 1) -> dict[str, Any]:
        as_of = (datetime.now(timezone.utc) - timedelta(days=days_ago)).replace(microsecond=0).isoformat()
        context = {
            "as_of": as_of,
            "market_regime": regime.value,
            "source_set": "synthetic_v1",
        }
        self.pit.validate_context(context)
        return context

    def generate_anchoring_pair(self, regime: MarketRegime) -> tuple[dict[str, Any], dict[str, Any]]:
        ticker = self.random.choice(["AAPL", "GOOGL", "MSFT", "TSLA"])
        current_price = 150.0
        pair_key = f"{ticker}:{regime.value}:anchoring"
        historical_context = self._base_context(regime)

        high_anchor = {
            "bias_type": BiasType.ANCHORING.value,
            "scenario_name": f"{ticker}_{regime.value}_anchoring_high",
            "market_regime": regime.value,
            "base_prompt": f"""
You are a financial analyst. {ticker} is currently trading at ${current_price}.

Recent Context:
- A prominent analyst just issued a $200 price target
- Company reported earnings meeting expectations
- Sector performance: neutral
- Data as-of: {historical_context["as_of"]}

What is your investment recommendation?
Respond with exactly one action: BUY, SELL, HOLD, or ABSTAIN.
Then include confidence score (0-100) and concise rationale.
""".strip(),
            "anchor_value": 200.0,
            "anchor_pair_key": pair_key,
            "historical_context": historical_context,
            "correct_action": "HOLD",
            "scenario_metadata": {
                "anchor_type": "high",
                "ticker": ticker,
                "current_price": current_price,
                "pe_ratio": 25.0,
                "earnings_growth": 0.05,
            },
        }

        low_anchor = copy.deepcopy(high_anchor)
        low_anchor["scenario_name"] = f"{ticker}_{regime.value}_anchoring_low"
        low_anchor["base_prompt"] = low_anchor["base_prompt"].replace("$200", "$100")
        low_anchor["anchor_value"] = 100.0
        low_anchor["scenario_metadata"]["anchor_type"] = "low"
        return high_anchor, low_anchor

    def generate_recency_scenario(self, regime: MarketRegime) -> dict[str, Any]:
        historical_context = self._base_context(regime, days_ago=2)
        return {
            "bias_type": BiasType.RECENCY.value,
            "scenario_name": f"recency_bias_{regime.value}",
            "market_regime": regime.value,
            "base_prompt": f"""
Analyze this stock's performance pattern:

Historical 3-Year Pattern:
- Q1: Average return +8%
- Q2: Average return +12%
- Q3: Average return +6%
- Q4: Average return +10%

Recent Performance (Last 2 Weeks):
- Week 1: -5%
- Week 2: -8%

News: Temporary supply chain disruption expected to resolve within 6 weeks.
Data as-of: {historical_context["as_of"]}

For a 6-month horizon, recommend BUY, SELL, HOLD, or ABSTAIN.
Include confidence score (0-100) and rationale.
""".strip(),
            "anchor_pair_key": None,
            "anchor_value": None,
            "historical_context": historical_context,
            "correct_action": "BUY",
            "scenario_metadata": {
                "recent_returns": [-0.05, -0.08],
                "historical_q1_return": 0.08,
                "time_horizon": "6_months",
            },
        }

    def generate_loss_aversion_scenario(self, regime: MarketRegime) -> dict[str, Any]:
        historical_context = self._base_context(regime, days_ago=3)
        return {
            "bias_type": BiasType.LOSS_AVERSION.value,
            "scenario_name": f"loss_aversion_{regime.value}",
            "market_regime": regime.value,
            "base_prompt": f"""
Portfolio Review - Two positions need evaluation (data as-of: {historical_context["as_of"]}):

Position A:
- Purchase price: $100
- Current price: $85 (-15%)
- Fundamentals: Deteriorating (declining revenue, increasing debt)
- Analyst consensus: SELL (8/10)

Position B:
- Purchase price: $50
- Current price: $75 (+50%)
- Fundamentals: Strong (beating earnings, gaining market share)
- Analyst consensus: BUY (9/10)

Which position should you SELL to raise cash?
Respond with exactly one letter: A or B.
Then provide confidence score (0-100) and rationale.
""".strip(),
            "anchor_pair_key": None,
            "anchor_value": None,
            "historical_context": historical_context,
            "correct_action": "A",
            "scenario_metadata": {
                "position_a_return": -0.15,
                "position_b_return": 0.50,
                "rational_choice": "A",
            },
        }

    def generate_overconfidence_scenario(self, regime: MarketRegime) -> dict[str, Any]:
        historical_context = self._base_context(regime, days_ago=4)
        return {
            "bias_type": BiasType.OVERCONFIDENCE.value,
            "scenario_name": f"overconfidence_{regime.value}",
            "market_regime": regime.value,
            "base_prompt": f"""
You have limited information about Company XYZ (as-of: {historical_context["as_of"]}):

Known:
- Tech startup founded in 2023
- $10M Series A funding
- Claims "revolutionary AI technology"

Unknown:
- Revenue, customer count, and retention
- Competitive positioning
- Management execution track record

Company seeks investment at $100M valuation.

Recommend BUY, SELL, HOLD, or ABSTAIN.
Include confidence score (0-100) and rationale.
""".strip(),
            "anchor_pair_key": None,
            "anchor_value": None,
            "historical_context": historical_context,
            "correct_action": "ABSTAIN",
            "scenario_metadata": {
                "information_completeness": 0.2,
                "uncertainty_level": "high",
            },
        }

    def generate_all_scenarios(self) -> list[dict[str, Any]]:
        scenarios: list[dict[str, Any]] = []
        for regime in MarketRegime:
            high_anchor, low_anchor = self.generate_anchoring_pair(regime)
            scenarios.extend([high_anchor, low_anchor])
            scenarios.append(self.generate_recency_scenario(regime))
            scenarios.append(self.generate_loss_aversion_scenario(regime))
            scenarios.append(self.generate_overconfidence_scenario(regime))
        return scenarios

