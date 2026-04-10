"""Validate command shell."""

from __future__ import annotations

import argparse

from apps.cli.commands._common import add_fields_argument, emit_error, emit_payload, resolve_project_path, selected_fields, validation_details
from apps.cli.parser import set_help_key
from libs.actions import validate_project


VALIDATE_FIELDS = (
    "project",
    "manifest",
    "valid",
    "jobs",
    "manifest_hash",
    "errors",
    "warnings",
    "warning_messages",
)


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = set_help_key(
        subparsers.add_parser("validate", help="Validate one schedule manifest under resources/schedules/."),
        "validate",
    )
    add_fields_argument(parser)
    parser.set_defaults(handler=handle)


def handle(args: argparse.Namespace) -> int:
    result = validate_project(
        resolve_project_path(getattr(args, "project", None)),
        schedule_name=getattr(args, "schedule", None),
    )
    if not result.valid or result.hashes is None or result.normalized_manifest is None:
        return emit_error(
            "project validation failed",
            details=validation_details(result.errors + result.warnings),
            help_items=("Run `xcron validate --help` to review command usage",),
        )

    payload: dict[str, object] = {
        "project": result.project_root,
        "manifest": result.manifest_path,
        "valid": True,
        "jobs": len(result.normalized_manifest.jobs),
        "manifest_hash": result.hashes.manifest_hash,
        "errors": len(result.errors),
        "warnings": len(result.warnings),
    }
    if result.warnings:
        payload["warning_messages"] = [f"{message.path}: {message.message}" for message in result.warnings]
    return emit_payload(
        payload,
        allowed_fields=VALIDATE_FIELDS,
        requested_fields=selected_fields(getattr(args, "fields", None)),
    )
