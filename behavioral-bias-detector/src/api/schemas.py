from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CreateAgentRequest(BaseModel):
    model_name: str
    provider: str
    version: str | None = None
    temperature: float = 0.7
    max_tokens: int = 1000
    config: dict[str, Any] | None = None


class AgentResponse(BaseModel):
    id: int
    model_name: str
    provider: str
    version: str | None = None
    temperature: float
    max_tokens: int


class RunBenchmarkRequest(BaseModel):
    agent_ids: list[int] = Field(min_length=1)
    scenario_ids: list[int] = Field(min_length=1)


class BenchmarkResultItem(BaseModel):
    scenario_id: int
    agent_id: int
    bias_score: float
    extracted_action: str
    error: str | None = None


class BenchmarkRunResponse(BaseModel):
    run_id: str
    status: str
    evaluations_run: int
    results: list[BenchmarkResultItem]


class BiasScoreResponse(BaseModel):
    agent_id: int
    model_name: str
    bias_type: str
    mean_bias_score: float
    sample_count: int


class ScenarioResponse(BaseModel):
    id: int
    bias_type: str
    scenario_name: str
    market_regime: str | None
    correct_action: str
    created_at: datetime


class GenerateScenarioResponse(BaseModel):
    inserted: int
    total_generated: int


class RunSummaryResponse(BaseModel):
    run_id: str
    evaluated_at: datetime
    evaluations: int
    failed: int

