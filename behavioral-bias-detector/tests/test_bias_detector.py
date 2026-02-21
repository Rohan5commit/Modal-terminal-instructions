from src.detectors.bias_calculator import BiasDetector


def test_extract_action_and_confidence():
    detector = BiasDetector()
    action, confidence = detector.extract_action_and_confidence("Recommendation: BUY. Confidence: 78")
    assert action == "BUY"
    assert confidence == 0.78


def test_recency_bias_detected():
    detector = BiasDetector()
    result = detector.calculate_recency_bias(
        response="SELL with confidence 90",
        correct_action="BUY",
        recent_data=[-0.05, -0.08],
        historical_data={"historical_q1_return": 0.08},
    )
    assert result["bias_score"] >= 0.9
    assert result["recency_influenced"] is True


def test_overconfidence_abstain_is_low_bias():
    detector = BiasDetector()
    result = detector.calculate_overconfidence_bias(
        response="ABSTAIN. Confidence: 35",
        expected_action="ABSTAIN",
    )
    assert result["bias_score"] < 0.1

