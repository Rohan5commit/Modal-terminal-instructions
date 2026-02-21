from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from src.agents.llm_client import UnifiedLLMClient
from src.api.schemas import (
    AgentResponse,
    BenchmarkResultItem,
    BenchmarkRunResponse,
    BiasScoreResponse,
    CreateAgentRequest,
    GenerateScenarioResponse,
    RunBenchmarkRequest,
    RunSummaryResponse,
    ScenarioResponse,
)
from src.config.settings import get_settings
from src.core.evaluator import BiasEvaluationOrchestrator
from src.core.reporting import build_metrics_for_run
from src.db.session import get_db
from src.detectors.bias_calculator import BiasDetector
from src.models.database import BiasEvaluation, BiasScenario, LLMAgent
from src.scenarios.bias_templates import ScenarioGenerator
from src.utils.pit_controller import PointInTimeController

router = APIRouter(prefix="/api/v1")


@router.post("/scenarios/generate", response_model=GenerateScenarioResponse)
def generate_scenarios(db: Session = Depends(get_db)) -> GenerateScenarioResponse:
    generator = ScenarioGenerator(pit_controller=PointInTimeController())
    generated = generator.generate_all_scenarios()
    inserted = 0

    existing_names = {row[0] for row in db.query(BiasScenario.scenario_name).all()}
    for scenario_data in generated:
        if scenario_data["scenario_name"] in existing_names:
            continue
        db.add(BiasScenario(**scenario_data))
        inserted += 1

    db.commit()
    return GenerateScenarioResponse(inserted=inserted, total_generated=len(generated))


@router.get("/scenarios", response_model=list[ScenarioResponse])
def list_scenarios(db: Session = Depends(get_db)) -> list[ScenarioResponse]:
    rows = db.query(BiasScenario).order_by(BiasScenario.id.asc()).all()
    return [
        ScenarioResponse(
            id=row.id,
            bias_type=row.bias_type,
            scenario_name=row.scenario_name,
            market_regime=row.market_regime,
            correct_action=row.correct_action,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.post("/agents", response_model=AgentResponse)
def create_agent(request: CreateAgentRequest, db: Session = Depends(get_db)) -> AgentResponse:
    agent = LLMAgent(
        model_name=request.model_name,
        provider=request.provider.lower(),
        version=request.version,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        config=request.config,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return AgentResponse(
        id=agent.id,
        model_name=agent.model_name,
        provider=agent.provider,
        version=agent.version,
        temperature=agent.temperature,
        max_tokens=agent.max_tokens,
    )


@router.get("/agents", response_model=list[AgentResponse])
def list_agents(db: Session = Depends(get_db)) -> list[AgentResponse]:
    rows = db.query(LLMAgent).order_by(LLMAgent.id.asc()).all()
    return [
        AgentResponse(
            id=row.id,
            model_name=row.model_name,
            provider=row.provider,
            version=row.version,
            temperature=row.temperature,
            max_tokens=row.max_tokens,
        )
        for row in rows
    ]


@router.post("/benchmark/run", response_model=BenchmarkRunResponse)
async def run_benchmark(request: RunBenchmarkRequest, db: Session = Depends(get_db)) -> BenchmarkRunResponse:
    settings = get_settings()
    llm_client = UnifiedLLMClient(
        {
            "OPENAI_API_KEY": settings.openai_api_key,
            "ANTHROPIC_API_KEY": settings.anthropic_api_key,
            "GOOGLE_API_KEY": settings.google_api_key,
            "GROQ_API_KEY": settings.groq_api_key,
            "TOGETHER_API_KEY": settings.together_api_key,
        }
    )
    orchestrator = BiasEvaluationOrchestrator(
        db=db,
        llm_client=llm_client,
        bias_detector=BiasDetector(),
        concurrency=settings.benchmark_concurrency,
    )

    try:
        run_id, evaluations = await orchestrator.run_full_benchmark(request.agent_ids, request.scenario_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    metrics = build_metrics_for_run(run_id=run_id, evaluations=evaluations)
    for metric in metrics:
        db.add(metric)
    db.commit()

    response_items = [
        BenchmarkResultItem(
            scenario_id=row.scenario_id,
            agent_id=row.agent_id,
            bias_score=float(row.bias_score),
            extracted_action=row.extracted_action,
            error=row.error,
        )
        for row in evaluations
    ]

    return BenchmarkRunResponse(
        run_id=run_id,
        status="completed",
        evaluations_run=len(response_items),
        results=response_items,
    )


@router.get("/results/by-model", response_model=list[BiasScoreResponse])
def get_results_by_model(run_id: str | None = None, db: Session = Depends(get_db)) -> list[BiasScoreResponse]:
    query = (
        db.query(
            LLMAgent.id.label("agent_id"),
            LLMAgent.model_name.label("model_name"),
            BiasScenario.bias_type.label("bias_type"),
            func.avg(BiasEvaluation.bias_score).label("mean_bias_score"),
            func.count(BiasEvaluation.id).label("sample_count"),
        )
        .join(BiasEvaluation, LLMAgent.id == BiasEvaluation.agent_id)
        .join(BiasScenario, BiasScenario.id == BiasEvaluation.scenario_id)
    )
    if run_id:
        query = query.filter(BiasEvaluation.run_id == run_id)

    rows = (
        query.group_by(LLMAgent.id, LLMAgent.model_name, BiasScenario.bias_type)
        .order_by(LLMAgent.id.asc(), BiasScenario.bias_type.asc())
        .all()
    )

    return [
        BiasScoreResponse(
            agent_id=int(row.agent_id),
            model_name=str(row.model_name),
            bias_type=str(row.bias_type),
            mean_bias_score=round(float(row.mean_bias_score or 0.0), 4),
            sample_count=int(row.sample_count),
        )
        for row in rows
    ]


@router.get("/runs", response_model=list[RunSummaryResponse])
def list_runs(db: Session = Depends(get_db)) -> list[RunSummaryResponse]:
    rows = (
        db.query(
            BiasEvaluation.run_id.label("run_id"),
            func.max(BiasEvaluation.evaluated_at).label("evaluated_at"),
            func.count(BiasEvaluation.id).label("evaluations"),
            func.sum(case((BiasEvaluation.error.is_(None), 0), else_=1)).label("failed"),
        )
        .group_by(BiasEvaluation.run_id)
        .order_by(func.max(BiasEvaluation.evaluated_at).desc())
        .all()
    )

    return [
        RunSummaryResponse(
            run_id=str(row.run_id),
            evaluated_at=row.evaluated_at,
            evaluations=int(row.evaluations),
            failed=int(row.failed or 0),
        )
        for row in rows
    ]
