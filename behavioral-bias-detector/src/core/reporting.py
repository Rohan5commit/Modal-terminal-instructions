from collections import defaultdict
from statistics import mean, pstdev

from src.models.database import BiasEvaluation, BiasMetric


def build_metrics_for_run(run_id: str, evaluations: list[BiasEvaluation]) -> list[BiasMetric]:
    grouped: dict[tuple[int, str], list[float]] = defaultdict(list)

    for evaluation in evaluations:
        scenario = evaluation.scenario
        if not scenario:
            continue
        grouped[(evaluation.agent_id, scenario.bias_type)].append(float(evaluation.bias_score))

    metrics: list[BiasMetric] = []
    for (agent_id, bias_type), scores in grouped.items():
        ordered = sorted(scores)
        n = len(ordered)
        p25 = ordered[max(0, int(0.25 * (n - 1)))]
        p50 = ordered[max(0, int(0.50 * (n - 1)))]
        p75 = ordered[max(0, int(0.75 * (n - 1)))]
        metrics.append(
            BiasMetric(
                run_id=run_id,
                agent_id=agent_id,
                bias_type=bias_type,
                aggregation_period="run",
                mean_bias_score=mean(ordered),
                std_dev=pstdev(ordered) if n > 1 else 0.0,
                sample_count=n,
                percentile_25=p25,
                percentile_50=p50,
                percentile_75=p75,
            )
        )

    return metrics
