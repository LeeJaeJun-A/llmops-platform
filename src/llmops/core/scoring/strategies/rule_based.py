"""Rule-based scorer — regex, length, JSON validity, keyword checks."""

import json
import re
from typing import Any

from llmops.core.scoring.base import Scorer, ScoreResult


class RuleBasedScorer(Scorer):
    """Scores output based on configurable rules.

    Supported rules:
    - min_length: {"type": "min_length", "min": 50}
    - max_length: {"type": "max_length", "max": 500}
    - contains: {"type": "contains", "keywords": ["hello", "world"]}
    - not_contains: {"type": "not_contains", "keywords": ["error", "fail"]}
    - regex_match: {"type": "regex_match", "pattern": "\\d{4}-\\d{2}-\\d{2}"}
    - json_valid: {"type": "json_valid"}
    """

    @property
    def name(self) -> str:
        return "rule_based"

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
        rules: list[dict[str, Any]] = config.get("rules", [])

        if not rules:
            return ScoreResult(
                name=self.name,
                value=1.0,
                comment="No rules configured, default pass",
            )

        passed = 0
        total = len(rules)
        failed_rules: list[str] = []

        for rule in rules:
            rule_type = rule.get("type", "")
            if self._evaluate_rule(rule_type, rule, output_text):
                passed += 1
            else:
                failed_rules.append(rule_type)

        score = passed / total if total > 0 else 1.0

        return ScoreResult(
            name=self.name,
            value=round(score, 4),
            comment=f"Passed {passed}/{total} rules"
            + (f". Failed: {failed_rules}" if failed_rules else ""),
            metadata={"passed": passed, "total": total, "failed_rules": failed_rules},
        )

    def _evaluate_rule(self, rule_type: str, rule: dict[str, Any], text: str) -> bool:
        match rule_type:
            case "min_length":
                return len(text) >= rule.get("min", 0)
            case "max_length":
                return len(text) <= rule.get("max", float("inf"))
            case "contains":
                keywords = rule.get("keywords", [])
                return all(kw.lower() in text.lower() for kw in keywords)
            case "not_contains":
                keywords = rule.get("keywords", [])
                return all(kw.lower() not in text.lower() for kw in keywords)
            case "regex_match":
                pattern = rule.get("pattern", "")
                return bool(re.search(pattern, text))
            case "json_valid":
                try:
                    json.loads(text)
                    return True
                except (json.JSONDecodeError, TypeError):
                    return False
            case _:
                return True
