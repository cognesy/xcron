"""Validate command shell."""

from __future__ import annotations

import argparse

from apps.cli.commands._common import print_validation_messages, resolve_project_path
from libs.actions import validate_project


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("validate", help="Validate one schedule manifest under resources/schedules/.")
    parser.set_defaults(handler=handle)


def handle(args: argparse.Namespace) -> int:
    result = validate_project(
        resolve_project_path(getattr(args, "project", None)),
        schedule_name=getattr(args, "schedule", None),
    )
    print(f"project: {result.project_root}")
    if result.manifest_path:
        print(f"manifest: {result.manifest_path}")
    if result.errors:
        print_validation_messages(result.errors)
    if result.warnings:
        print_validation_messages(result.warnings)
    if result.valid and result.hashes is not None and result.normalized_manifest is not None:
        print(f"jobs: {len(result.normalized_manifest.jobs)}")
        print(f"manifest_hash: {result.hashes.manifest_hash}")
        return 0
    return 2
