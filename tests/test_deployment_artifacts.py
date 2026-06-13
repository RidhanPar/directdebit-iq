"""Checks for deployable automation and cloud configuration artifacts."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_n8n_workflow_contains_approval_and_execution_steps():
    workflow = json.loads(
        (ROOT / "automation" / "n8n_retry_approval_workflow.json").read_text(
            encoding="utf-8"
        )
    )
    names = {node["name"] for node in workflow["nodes"]}
    assert {
        "Create Prediction and Approval",
        "Record Reviewer Decision",
        "Execute Approved Retry",
    }.issubset(names)


def test_render_blueprint_deploys_api_and_managed_database():
    blueprint = yaml.safe_load((ROOT / "render.yaml").read_text(encoding="utf-8"))
    assert blueprint["databases"][0]["plan"] == "free"
    service = blueprint["services"][0]
    assert service["healthCheckPath"] == "/health"
    assert service["dockerfilePath"] == "./Dockerfile.api"
