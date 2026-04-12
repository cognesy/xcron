from __future__ import annotations

from libs.actions.validate_project import validate_project
from libs.domain import DeployedJobState, ProjectState, build_project_plan
from libs.services.hash_service import WRAPPER_RENDERER_VERSION


def test_wrapper_renderer_version_participates_in_definition_hash(tmp_path) -> None:
    project = tmp_path / "project"
    schedule_dir = project / "resources" / "schedules"
    schedule_dir.mkdir(parents=True)
    (schedule_dir / "default.yaml").write_text(
        """
version: 1
project:
  id: hash-demo
jobs:
  - id: tick
    schedule:
      every: 60s
    command: echo tick
""",
        encoding="utf-8",
    )

    validation = validate_project(project)
    assert validation.valid
    assert validation.normalized_manifest is not None
    assert validation.hashes is not None
    job = validation.normalized_manifest.jobs[0]
    desired_definition_hash = validation.hashes.job_definition_hashes[job.qualified_id]

    stale_state = ProjectState(
        project_id="hash-demo",
        backend="launchd",
        manifest_hash="old",
        jobs=(
            DeployedJobState(
                qualified_id=job.qualified_id,
                job_id=job.job_id,
                artifact_id=job.artifact_id,
                backend="launchd",
                enabled=True,
                desired_hash=validation.hashes.job_hashes[job.qualified_id],
                definition_hash=f"pre-wrapper-v{WRAPPER_RENDERER_VERSION}",
            ),
        ),
    )

    plan = build_project_plan(
        validation.normalized_manifest,
        "launchd",
        validation.hashes.manifest_hash,
        validation.hashes.job_hashes,
        validation.hashes.job_definition_hashes,
        stale_state,
    )

    assert desired_definition_hash != f"pre-wrapper-v{WRAPPER_RENDERER_VERSION}"
    assert plan.changes[0].kind.value == "update"
    assert plan.changes[0].reason == "normalized job definition hash changed"
