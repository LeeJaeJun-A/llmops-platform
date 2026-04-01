"""LLM-as-judge scorer — uses the gateway to evaluate output quality."""

import re
from typing import Any

from llmops.core.scoring.base import Scorer, ScoreResult

DEFAULT_RUBRIC = """\
You are an expert evaluator. Rate the following AI response on a scale of 0.0 to 1.0.

## Input
{input_text}

## AI Response
{output_text}

## Reference (if provided)
{reference}

## Evaluation Criteria
{rubric}

Respond with ONLY a JSON object in this format:
{{"score": 0.0-1.0, "reason": "brief explanation"}}
"""


class LLMJudgeScorer(Scorer):
    """Scores output using another LLM call as a judge.

    Config options:
    - model: str (default: first available model)
    - rubric: str (evaluation criteria)
    - template: str (full prompt template, overrides default)
    """

    @property
    def name(self) -> str:
        return "llm_judge"

    async def score(
        self,
        *,
        input_text: str,
        output_text: str,
        reference: str | None = None,
        context: dict[str, Any] | None = None,
        config: dict[str, Any] | None = None,
    ) -> ScoreResult:
        config = config or {}
        model = config.get("model", "gemini-2.0-flash")
        rubric = config.get("rubric", "Rate the overall quality, accuracy, and helpfulness.")
        template = config.get("template", DEFAULT_RUBRIC)

        prompt = template.format(
            input_text=input_text,
            output_text=output_text,
            reference=reference or "N/A",
            rubric=rubric,
        )

        # Import here to avoid circular dependency
        from llmops.core.gateway.registry import get_registry
        from llmops.core.gateway.schemas import ChatRequest, Message, Role

        registry = get_registry()
        provider = registry.resolve(model)

        request = ChatRequest(
            model=model,
            messages=[Message(role=Role.USER, content=prompt)],
            temperature=0.0,
            max_tokens=256,
        )

        response = await provider.chat(request)
        judge_output = response.content

        score_value, reason = self._parse_judge_response(judge_output)

        return ScoreResult(
            name=self.name,
            value=score_value,
            comment=reason,
            metadata={
                "judge_model": model,
                "judge_raw_output": judge_output,
                "rubric": rubric,
            },
        )

    def _parse_judge_response(self, text: str) -> tuple[float, str]:
        """Extract score and reason from judge response."""
        import json

        # Try parsing as JSON first
        try:
            # Find JSON object in the response
            match = re.search(r"\{[^}]+\}", text)
            if match:
                data = json.loads(match.group())
                score = float(data.get("score", 0.5))
                reason = str(data.get("reason", ""))
                return max(0.0, min(1.0, score)), reason
        except (json.JSONDecodeError, ValueError):
            pass

        # Fallback: try to find a number
        numbers = re.findall(r"(\d+\.?\d*)", text)
        if numbers:
            score = float(numbers[0])
            if score > 1.0:
                score = score / 10.0 if score <= 10.0 else score / 100.0
            return max(0.0, min(1.0, score)), text[:200]

        return 0.5, f"Could not parse judge output: {text[:200]}"
