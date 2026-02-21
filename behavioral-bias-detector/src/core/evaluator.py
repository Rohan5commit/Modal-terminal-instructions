import asyncio
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from loguru import logger
from sqlalchemy.orm import Session

from src.agents.llm_client import UnifiedLLMClient
from src.detectors.bias_calculator import BiasDetector
from src.models.database import BiasEvaluation, BiasScenario, LLMAgent


@dataclass(slots=True)
class PendingEvaluation:
    scenario_id: int
    agent_id: int
    prompt_sent: str
    model_response: str
    extracted_action: str
    confidence_score: float
    bias_score: float
    response_time_ms: int
    token_usage: dict[str, int]
    error: str | None = None


class BiasEvaluationOrchestrator:
    """Runs model evaluations and writes results to DB."""

    def __init__(self, db: Session, llm_client: UnifiedLLMClient, bias_detector: BiasDetector, concurrency: int = 8):
        self.db = db
        self.llm_client = llm_client
        self.bias_detector = bias_detector
        self.concurrency = max(1, concurrency)

    async def run_full_benchmark(self, agent_ids: list[int], scenario_ids: list[int]) -> tuple[str, list[BiasEvaluation]]:
        agents = self.db.query(LLMAgent).filter(LLMAgent.id.in_(agent_ids)).all()
        scenarios = self.db.query(BiasScenario).filter(BiasScenario.id.in_(scenario_ids)).all()
        run_id = str(uuid4())

        if not agents:
            raise ValueError("No agents matched requested IDs")
        if not scenarios:
            raise ValueError("No scenarios matched requested IDs")

        logger.info(
            "Starting benchmark run {} with {} agents and {} scenarios",
            run_id,
            len(agents),
            len(scenarios),
        )

        semaphore = asyncio.Semaphore(self.concurrency)
        tasks = [
            self._safe_evaluate(semaphore=semaphore, agent=agent, scenario=scenario)
            for agent in agents
            for scenario in scenarios
        ]

        pending_results = await asyncio.gather(*tasks)
        evaluations = self._persist_pending(run_id=run_id, pending=pending_results)
        self._apply_anchoring_pair_scores(evaluations)
        self.db.commit()

        logger.info("Completed benchmark run {} with {} evaluations", run_id, len(evaluations))
        return run_id, evaluations

    async def _safe_evaluate(
        self,
        semaphore: asyncio.Semaphore,
        agent: LLMAgent,
        scenario: BiasScenario,
    ) -> PendingEvaluation:
        async with semaphore:
            try:
                response = await self.llm_client.call_model(
                    provider=agent.provider,
                    prompt=scenario.base_prompt,
                    model=agent.model_name,
                    temperature=agent.temperature,
                    max_tokens=agent.max_tokens,
                )
                action, confidence = self.bias_detector.extract_action_and_confidence(response.content)
                bias_result = self._calculate_bias_for_scenario(scenario, response.content)
                bias_score = float(bias_result.get("bias_score", 0.0))
                return PendingEvaluation(
                    scenario_id=scenario.id,
                    agent_id=agent.id,
                    prompt_sent=scenario.base_prompt,
                    model_response=response.content,
                    extracted_action=action,
                    confidence_score=confidence,
                    bias_score=bias_score,
                    response_time_ms=response.response_time_ms,
                    token_usage=response.tokens_used,
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "Evaluation failure for model={} provider={} scenario={}",
                    agent.model_name,
                    agent.provider,
                    scenario.scenario_name,
                )
                return PendingEvaluation(
                    scenario_id=scenario.id,
                    agent_id=agent.id,
                    prompt_sent=scenario.base_prompt,
                    model_response="",
                    extracted_action="UNKNOWN",
                    confidence_score=0.0,
                    bias_score=0.0,
                    response_time_ms=0,
                    token_usage={},
                    error=str(exc),
                )

    def _persist_pending(self, run_id: str, pending: list[PendingEvaluation]) -> list[BiasEvaluation]:
        evaluations: list[BiasEvaluation] = []
        for item in pending:
            evaluation = BiasEvaluation(
                run_id=run_id,
                scenario_id=item.scenario_id,
                agent_id=item.agent_id,
                prompt_sent=item.prompt_sent,
                model_response=item.model_response,
                extracted_action=item.extracted_action,
                confidence_score=item.confidence_score,
                rationale=item.model_response,
                bias_score=item.bias_score,
                response_time_ms=item.response_time_ms,
                token_usage=item.token_usage,
                error=item.error,
            )
            self.db.add(evaluation)
            evaluations.append(evaluation)

        self.db.flush()
        for evaluation in evaluations:
            _ = evaluation.scenario
            _ = evaluation.agent
        return evaluations

    def _apply_anchoring_pair_scores(self, evaluations: list[BiasEvaluation]) -> None:
        grouped: dict[tuple[int, str], list[BiasEvaluation]] = {}
        for evaluation in evaluations:
            scenario = evaluation.scenario
            if not scenario or scenario.bias_type != "anchoring" or not scenario.anchor_pair_key:
                continue
            key = (evaluation.agent_id, scenario.anchor_pair_key)
            grouped.setdefault(key, []).append(evaluation)

        for (_, _), pair in grouped.items():
            if len(pair) < 2:
                continue

            high_eval = None
            low_eval = None
            for evaluation in pair:
                metadata = evaluation.scenario.scenario_metadata or {}
                anchor_type = metadata.get("anchor_type")
                if anchor_type == "high":
                    high_eval = evaluation
                elif anchor_type == "low":
                    low_eval = evaluation

            if not high_eval or not low_eval:
                continue

            high_val = float(high_eval.scenario.anchor_value or 0.0)
            low_val = float(low_eval.scenario.anchor_value or 0.0)
            result = self.bias_detector.calculate_anchoring_bias(
                high_anchor_response=high_eval.model_response,
                low_anchor_response=low_eval.model_response,
                high_anchor_val=high_val,
                low_anchor_val=low_val,
            )
            score = float(result["bias_score"])
            high_eval.bias_score = score
            low_eval.bias_score = score

    def _calculate_bias_for_scenario(self, scenario: BiasScenario, response: str) -> dict[str, Any]:
        metadata = scenario.scenario_metadata or {}

        if scenario.bias_type == "anchoring":
            # Pairwise score is computed after all evaluations are complete.
            return {"bias_score": 0.0}

        if scenario.bias_type == "recency":
            return self.bias_detector.calculate_recency_bias(
                response=response,
                correct_action=scenario.correct_action,
                recent_data=list(metadata.get("recent_returns", [])),
                historical_data=metadata,
            )

        if scenario.bias_type == "loss_aversion":
            return self.bias_detector.calculate_loss_aversion_bias(
                response=response,
                correct_choice=str(metadata.get("rational_choice", scenario.correct_action)),
            )

        if scenario.bias_type == "overconfidence":
            return self.bias_detector.calculate_overconfidence_bias(
                response=response,
                expected_action=scenario.correct_action,
            )

        return {"bias_score": 0.0}

