"""Jinja2-based prompt renderer with variable injection."""

from jinja2 import BaseLoader, Environment, TemplateSyntaxError, UndefinedError

_jinja_env = Environment(
    loader=BaseLoader(),
    autoescape=False,
    undefined=__import__("jinja2").StrictUndefined,
    keep_trailing_newline=True,
)


class PromptRenderer:
    """Renders prompt templates with Jinja2."""

    @staticmethod
    def render(template: str, variables: dict[str, str] | None = None) -> str:
        """Render a template string with the given variables.

        Supports both Jinja2 syntax ({{ var }}) and simple {var} placeholders.
        """
        variables = variables or {}

        try:
            tmpl = _jinja_env.from_string(template)
            return tmpl.render(**variables)
        except (TemplateSyntaxError, UndefinedError) as e:
            raise ValueError(f"Template rendering failed: {e}") from e

    @staticmethod
    def extract_variables(template: str) -> list[str]:
        """Extract variable names from a Jinja2 template."""
        from jinja2 import meta

        try:
            ast = _jinja_env.parse(template)
            return sorted(meta.find_undeclared_variables(ast))
        except TemplateSyntaxError:
            return []
