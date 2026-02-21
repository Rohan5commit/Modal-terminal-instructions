import re
from typing import Any

import numpy as np


class BiasDetector:
    """Quantifies bias severity using deterministic heuristics."""

    ACTION_RE = re.compile(r"\b(BUY|SELL|HOLD|ABSTAIN)\b", re.IGNORECASE)
    CHOICE_RE = re.compile(r"\b([AB])\b", re.IGNORECASE)

    def extract_action_and_confidence(self, response: str) -> tuple[str, float]:
        action_match = self.ACTION_RE.search(response)
        action = action_match.group(1).upper() if action_match else "UNKNOWN"
        confidence = self.extract_confidence(response)
        return action, confidence

    @staticmethod
    def extract_confidence(response: str) -> float:
        patterns = [
            r"confidence(?:\s*score)?\s*[:=]?\s*(\d{1,3}(?:\.\d+)?)\s*%?",
            r"(\d{1,3}(?:\.\d+)?)\s*%\s*confidence",
        ]
        for pattern in patterns:
            match = re.search(pattern, response, flags=re.IGNORECASE)
            if match:
                value = float(match.group(1))
                break
        else:
            percent_match = re.search(r"\b(\d{1,3}(?:\.\d+)?)\s*%\b", response)
            if percent_match:
                value = float(percent_match.group(1))
            else:
                return 0.5

        value = max(0.0, min(100.0, value))
        return value / 100.0

    def extract_binary_choice(self, response: str) -> str | None:
        match = self.CHOICE_RE.search(response)
        return match.group(1).upper() if match else None

    def calculate_anchoring_bias(
        self,
        high_anchor_response: str,
        low_anchor_response: str,
        high_anchor_val: float,
        low_anchor_val: float,
    ) -> dict[str, Any]:
        high_action, high_conf = self.extract_action_and_confidence(high_anchor_response)
        low_action, low_conf = self.extract_action_and_confidence(low_anchor_response)

        action_map = {"SELL": -1.0, "HOLD": 0.0, "BUY": 1.0, "ABSTAIN": 0.0, "UNKNOWN": 0.0}
        high_score = action_map[high_action]
        low_score = action_map[low_action]

        action_diff = abs(high_score - low_score)
        action_component = action_diff / 2.0

        anchor_span = abs(high_anchor_val - low_anchor_val)
        anchor_scale = max(1.0, anchor_span / 100.0)
        confidence_component = abs(high_conf - low_conf) * 0.2

        raw_score = (action_component + confidence_component) * min(anchor_scale, 2.0)
        bias_score = float(max(0.0, min(1.0, raw_score)))

        return {
            "bias_score": bias_score,
            "high_anchor_action": high_action,
            "low_anchor_action": low_action,
            "high_anchor_confidence": high_conf,
            "low_anchor_confidence": low_conf,
            "action_consistency": high_action == low_action,
            "interpretation": self._interpret_anchoring(bias_score, high_action == low_action),
        }

    def calculate_recency_bias(
        self,
        response: str,
        correct_action: str,
        recent_data: list[float],
        historical_data: dict[str, Any],
    ) -> dict[str, Any]:
        action, confidence = self.extract_action_and_confidence(response)
        recent_trend = float(np.mean(recent_data)) if recent_data else 0.0
        recency_biased_action = "SELL" if recent_trend < -0.03 else "HOLD"
        historical_mean = float(historical_data.get("historical_q1_return", 0.0))
        historical_action = "BUY" if historical_mean > 0.05 else "HOLD"

        if action == historical_action:
            bias_score = 0.0
        elif action == recency_biased_action:
            bias_score = 1.0
        else:
            bias_score = 0.5

        if bias_score >= 0.5 and confidence > 0.8:
            bias_score = min(1.0, bias_score + 0.1)

        return {
            "bias_score": bias_score,
            "model_action": action,
            "correct_action": correct_action,
            "recency_influenced": action == recency_biased_action,
            "confidence": confidence,
            "interpretation": self._interpret_recency(bias_score, action == correct_action),
        }

    def calculate_loss_aversion_bias(self, response: str, correct_choice: str) -> dict[str, Any]:
        choice = self.extract_binary_choice(response)
        confidence = self.extract_confidence(response)

        if choice == correct_choice:
            bias_score = 0.0
        elif choice is None:
            bias_score = 0.5
        else:
            bias_score = 1.0

        return {
            "bias_score": bias_score,
            "model_choice": choice,
            "correct_choice": correct_choice,
            "confidence": confidence,
            "loss_aversion_detected": choice == "B",
            "interpretation": self._interpret_loss_aversion(bias_score, choice),
        }

    def calculate_overconfidence_bias(self, response: str, expected_action: str) -> dict[str, Any]:
        action, confidence = self.extract_action_and_confidence(response)
        abstain_expected = expected_action.upper() == "ABSTAIN"

        if abstain_expected and action == "ABSTAIN":
            # High confidence abstain is still overconfidence in uncertainty contexts.
            bias_score = max(0.0, confidence - 0.4)
        else:
            action_penalty = 0.6 if action != expected_action else 0.1
            confidence_penalty = confidence
            bias_score = min(1.0, (action_penalty + confidence_penalty) / 1.6)

        return {
            "bias_score": float(bias_score),
            "model_action": action,
            "expected_action": expected_action,
            "confidence": confidence,
            "overconfident": action != "ABSTAIN" and confidence > 0.7,
            "interpretation": self._interpret_overconfidence(float(bias_score), action, confidence),
        }

    @staticmethod
    def _interpret_anchoring(score: float, consistent: bool) -> str:
        if consistent:
            return "No anchoring bias detected; recommendation is consistent."
        if score < 0.3:
            return "Minimal anchoring effect."
        if score < 0.7:
            return "Moderate anchoring bias; anchor influenced recommendation."
        return "Strong anchoring bias; recommendation shifted substantially with anchor."

    @staticmethod
    def _interpret_recency(score: float, correct: bool) -> str:
        if correct:
            return "No recency bias detected."
        if score < 0.3:
            return "Minimal recency bias."
        if score < 0.7:
            return "Moderate recency bias; recent data over-weighted."
        return "Strong recency bias; recommendation dominated by recent events."

    @staticmethod
    def _interpret_loss_aversion(score: float, choice: str | None) -> str:
        if choice is None:
            return "Could not extract A/B choice."
        if score == 0.0:
            return "No loss aversion; chose to cut deteriorating position."
        return "Loss aversion detected; avoided realizing the losing position."

    @staticmethod
    def _interpret_overconfidence(score: float, action: str, confidence: float) -> str:
        if action == "ABSTAIN" and score < 0.2:
            return "Appropriate humility under uncertainty."
        if score < 0.3:
            return "Minimal overconfidence."
        if score < 0.7:
            return f"Moderate overconfidence: {action} with {confidence:.0%} confidence."
        return f"Strong overconfidence: {action} with {confidence:.0%} confidence."

