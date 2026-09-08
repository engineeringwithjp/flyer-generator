"""The GitHub Actions workflow files, checked as data.

A workflow file that GitHub cannot parse does not fail loudly. It is accepted
into the repository, shows up in the Actions list under its *filename* instead
of its name, and every trigger it declares - including `schedule:` - is
silently discarded. The daily flyer run was in that state for two days and the
only visible symptom was an absence: no flyers, no failed run, no notification.

These tests are cheap and they run in CI, which is the point.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

try:
    import yaml
except ImportError:  # pragma: no cover - pyyaml is a dev dependency
    yaml = None  # type: ignore[assignment]

WORKFLOWS = sorted((Path(__file__).resolve().parent.parent / ".github" / "workflows").glob("*.yml"))

#: A `${{ }}` expression accepts single-quoted string literals only. A
#: double-quoted one is what broke generate-flyers.yml.
EXPRESSION = re.compile(r"\$\{\{(.+?)\}\}", re.DOTALL)


def test_there_are_workflows_to_check():
    assert WORKFLOWS, "no workflow files found - has the path changed?"


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_workflow_is_valid_yaml(path):
    if yaml is None:
        pytest.skip("pyyaml not installed")
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(document, dict), f"{path.name} did not parse to a mapping"
    assert "jobs" in document, f"{path.name} declares no jobs"
    # `on:` is YAML 1.1's boolean true once parsed, which is why it reads oddly.
    assert True in document or "on" in document, f"{path.name} declares no triggers"


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_no_double_quoted_strings_inside_expressions(path):
    """GitHub rejects the whole file, and takes the schedule down with it."""
    for match in EXPRESSION.finditer(path.read_text(encoding="utf-8")):
        body = match.group(1)
        assert '"' not in body, (
            f"{path.name}: expression {{{{{body}}}}} uses a double-quoted string. "
            "Actions expressions accept single quotes only; a double quote makes "
            "the entire workflow file unparseable and drops its triggers."
        )


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_local_actions_referenced_actually_exist(path):
    """`uses: ./...` is resolved from the repository, so a typo is a hard fail."""
    root = path.resolve().parent.parent.parent
    for reference in re.findall(r"uses:\s*(\./\S+)", path.read_text(encoding="utf-8")):
        action = root / reference.removeprefix("./")
        assert (action / "action.yml").exists() or (action / "action.yaml").exists(), (
            f"{path.name} uses {reference}, which has no action.yml"
        )


def test_the_daily_run_is_actually_scheduled():
    """The whole point of the project is that it runs without being asked."""
    if yaml is None:
        pytest.skip("pyyaml not installed")
    path = next(p for p in WORKFLOWS if p.name == "generate-flyers.yml")
    triggers = yaml.safe_load(path.read_text(encoding="utf-8"))[True]
    assert "schedule" in triggers, "generate-flyers.yml has no schedule"
    assert triggers["schedule"], "generate-flyers.yml schedule is empty"
