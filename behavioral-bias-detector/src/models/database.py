from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class BiasScenario(Base):
    __tablename__ = "bias_scenarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bias_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    scenario_name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    market_regime: Mapped[str | None] = mapped_column(String(50))
    base_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    anchor_value: Mapped[float | None] = mapped_column(Float)
    anchor_pair_key: Mapped[str | None] = mapped_column(String(200), index=True)
    historical_context: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    correct_action: Mapped[str] = mapped_column(String(50), nullable=False)
    scenario_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    evaluations: Mapped[list["BiasEvaluation"]] = relationship(back_populates="scenario")


class LLMAgent(Base):
    __tablename__ = "llm_agents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    version: Mapped[str | None] = mapped_column(String(50))
    temperature: Mapped[float] = mapped_column(Float, default=0.7, nullable=False)
    max_tokens: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)
    config: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    evaluations: Mapped[list["BiasEvaluation"]] = relationship(back_populates="agent")


class BiasEvaluation(Base):
    __tablename__ = "bias_evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    scenario_id: Mapped[int] = mapped_column(ForeignKey("bias_scenarios.id"), nullable=False, index=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("llm_agents.id"), nullable=False, index=True)
    prompt_sent: Mapped[str] = mapped_column(Text, nullable=False)
    model_response: Mapped[str] = mapped_column(Text, nullable=False)
    extracted_action: Mapped[str] = mapped_column(String(50), nullable=False, default="UNKNOWN")
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    rationale: Mapped[str | None] = mapped_column(Text)
    bias_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    deviation_from_baseline: Mapped[float | None] = mapped_column(Float)
    response_time_ms: Mapped[int | None] = mapped_column(Integer)
    token_usage: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    scenario: Mapped[BiasScenario] = relationship(back_populates="evaluations")
    agent: Mapped[LLMAgent] = relationship(back_populates="evaluations")


class BiasMetric(Base):
    __tablename__ = "bias_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("llm_agents.id"), nullable=False, index=True)
    bias_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    aggregation_period: Mapped[str] = mapped_column(String(20), nullable=False, default="run")
    mean_bias_score: Mapped[float] = mapped_column(Float, nullable=False)
    std_dev: Mapped[float] = mapped_column(Float, nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    percentile_25: Mapped[float] = mapped_column(Float, nullable=False)
    percentile_50: Mapped[float] = mapped_column(Float, nullable=False)
    percentile_75: Mapped[float] = mapped_column(Float, nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

