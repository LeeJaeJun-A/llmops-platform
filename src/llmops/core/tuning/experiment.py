"""Experiment runner — manages experiment lifecycle."""

import statistics
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from llmops.core.tuning.ab_test import ABTestAllocator
from llmops.core.tuning.base import (
    AllocationStrategy,
    ExperimentConfig,
    ExperimentStatus,
    ParameterSet,
    VariantResult,
)
from llmops.core.tuning.parameter_space import generate_grid_variants, generate_random_variants
from llmops.db.models.experiment import ExperimentModel, ExperimentTrialModel


def _model_to_dict(m: ExperimentModel) -> dict[str, Any]:
    return {
        "id": str(m.id),
        "name": m.name,
        "description": m.description,
        "status": m.status,
        "allocation_strategy": m.allocation_strategy,
        "parameter_space": m.parameter_space,
        "variants": m.variants,
        "scoring_pipeline_id": m.scoring_pipeline_id,
        "traffic_percentage": m.traffic_percentage,
        "winner_variant_id": m.winner_variant_id,
        "concluded_at": m.concluded_at.isoformat() if m.concluded_at else None,
        "created_at": m.created_at.isoformat(),
    }


class ExperimentRunner:
    """Manages experiment lifecycle: create, start, allocate, record, conclude."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, config: ExperimentConfig) -> dict[str, Any]:
        """Create a new experiment with auto-generated variants if not provided."""
        variants = config.variants

        if not variants:
            if config.allocation_strategy == AllocationStrategy.GRID:
                variants = generate_grid_variants(config.parameter_space)
            else:
                variants = generate_random_variants(config.parameter_space, count=4)

        experiment = ExperimentModel(
            name=config.name,
            description=config.description,
            status=ExperimentStatus.DRAFT.value,
            allocation_strategy=config.allocation_strategy.value,
            parameter_space=config.parameter_space.model_dump(),
            variants=[v.model_dump() for v in variants],
            scoring_pipeline_id=config.scoring_pipeline_id,
            traffic_percentage=config.traffic_percentage,
        )
        self._session.add(experiment)
        await self._session.commit()
        await self._session.refresh(experiment)

        return _model_to_dict(experiment)

    async def start(self, experiment_id: str) -> dict[str, Any]:
        """Move experiment from DRAFT to RUNNING."""
        exp = await self._get_experiment(experiment_id)
        if exp.status != ExperimentStatus.DRAFT.value:
            raise ValueError(f"Cannot start experiment in '{exp.status}' status")

        exp.status = ExperimentStatus.RUNNING.value
        await self._session.commit()
        await self._session.refresh(exp)
        return _model_to_dict(exp)

    async def allocate_variant(
        self, experiment_id: str, key: str
    ) -> ParameterSet | None:
        """Allocate a variant for a request within a running experiment."""
        exp = await self._get_experiment(experiment_id)
        if exp.status != ExperimentStatus.RUNNING.value:
            return None

        variants = [ParameterSet(**v) for v in exp.variants]
        allocator = ABTestAllocator(variants, exp.traffic_percentage)
        return allocator.allocate(key)

    async def record_trial(
        self,
        experiment_id: str,
        *,
        variant_id: str,
        trace_id: str,
        parameters: dict[str, Any],
        input_text: str,
        output_text: str,
        score: float | None = None,
    ) -> dict[str, Any]:
        """Record a trial (request + response) for an experiment."""
        trial = ExperimentTrialModel(
            experiment_id=experiment_id,
            variant_id=variant_id,
            trace_id=trace_id,
            parameters=parameters,
            input_text=input_text,
            output_text=output_text,
            score=score,
        )
        self._session.add(trial)
        await self._session.commit()
        await self._session.refresh(trial)

        return {
            "id": str(trial.id),
            "experiment_id": str(trial.experiment_id),
            "variant_id": trial.variant_id,
            "trace_id": trial.trace_id,
            "score": trial.score,
        }

    async def get_results(self, experiment_id: str) -> dict[str, Any]:
        """Aggregate trial results per variant."""
        exp = await self._get_experiment(experiment_id)

        result = await self._session.execute(
            select(ExperimentTrialModel).where(
                ExperimentTrialModel.experiment_id == experiment_id,
                ExperimentTrialModel.score.isnot(None),
            )
        )
        trials = result.scalars().all()

        # Group by variant
        variant_trials: dict[str, list[float]] = {}
        variant_params: dict[str, dict[str, Any]] = {}
        for trial in trials:
            if trial.variant_id not in variant_trials:
                variant_trials[trial.variant_id] = []
                variant_params[trial.variant_id] = trial.parameters
            variant_trials[trial.variant_id].append(trial.score)

        variant_results = []
        for vid, scores in variant_trials.items():
            variant_results.append(
                VariantResult(
                    variant_id=vid,
                    parameters=variant_params[vid],
                    sample_count=len(scores),
                    avg_score=round(statistics.mean(scores), 4) if scores else 0.0,
                    min_score=min(scores) if scores else 0.0,
                    max_score=max(scores) if scores else 0.0,
                    scores=scores,
                ).model_dump()
            )

        # Sort by avg_score descending
        variant_results.sort(key=lambda x: x["avg_score"], reverse=True)

        return {
            **_model_to_dict(exp),
            "results": variant_results,
            "total_trials": len(trials),
        }

    async def conclude(
        self, experiment_id: str, *, winner_variant_id: str | None = None
    ) -> dict[str, Any]:
        """Conclude an experiment, optionally specifying the winner."""
        exp = await self._get_experiment(experiment_id)
        if exp.status != ExperimentStatus.RUNNING.value:
            raise ValueError(f"Cannot conclude experiment in '{exp.status}' status")

        # Auto-detect winner if not specified
        if not winner_variant_id:
            results = await self.get_results(experiment_id)
            if results["results"]:
                winner_variant_id = results["results"][0]["variant_id"]

        exp.status = ExperimentStatus.COMPLETED.value
        exp.winner_variant_id = winner_variant_id
        exp.concluded_at = func.now()
        await self._session.commit()
        await self._session.refresh(exp)

        return _model_to_dict(exp)

    async def cancel(self, experiment_id: str) -> dict[str, Any]:
        """Cancel an experiment."""
        exp = await self._get_experiment(experiment_id)
        exp.status = ExperimentStatus.CANCELLED.value
        await self._session.commit()
        await self._session.refresh(exp)
        return _model_to_dict(exp)

    async def get(self, experiment_id: str) -> dict[str, Any]:
        exp = await self._get_experiment(experiment_id)
        return _model_to_dict(exp)

    async def list_experiments(self) -> list[dict[str, Any]]:
        result = await self._session.execute(
            select(ExperimentModel).order_by(ExperimentModel.created_at.desc())
        )
        return [_model_to_dict(e) for e in result.scalars().all()]

    async def _get_experiment(self, experiment_id: str) -> ExperimentModel:
        result = await self._session.execute(
            select(ExperimentModel).where(ExperimentModel.id == experiment_id)
        )
        exp = result.scalar_one_or_none()
        if not exp:
            raise ValueError(f"Experiment '{experiment_id}' not found")
        return exp
