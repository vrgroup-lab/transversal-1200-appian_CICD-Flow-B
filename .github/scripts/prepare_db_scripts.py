#!/usr/bin/env python3
"""Compute database script promotion metadata for Appian workflows."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect optional database scripts and metadata for promotion.",
    )
    parser.add_argument(
        "--scripts-dir",
        default="",
        help="Directory where database scripts were downloaded (optional).",
    )
    parser.add_argument(
        "--meta-dir",
        default="",
        help="Directory containing export metadata artifacts (optional).",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="File path where GitHub Actions outputs will be written.",
    )
    return parser.parse_args()


def detect_scripts_dir(raw: str) -> str:
    if not raw:
        return ""
    path = Path(raw)
    if not path.is_dir():
        return ""

    sql_like = {".sql", ".ddl"}
    for candidate in path.rglob("*"):
        if candidate.is_file() and candidate.suffix.lower() in sql_like:
            return str(path.resolve())
    return ""


def load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None


def extract_data_source(meta_dir: Path) -> str:
    response = meta_dir / "export-response.json"
    data = load_json(response)
    if isinstance(data, dict):
        value = data.get("dataSource")
        if isinstance(value, str):
            return value
    return ""


def extract_manifest(meta_dir: Path) -> str:
    manifest_path = meta_dir / "export-manifest.json"
    data = load_json(manifest_path)
    if not isinstance(data, dict):
        return ""

    scripts = data.get("databaseScripts")
    if not isinstance(scripts, list):
        return ""

    simplified: List[Dict[str, Any]] = []
    for item in scripts:
        if not isinstance(item, dict):
            continue
        entry: Dict[str, Any] = {}
        for key in ("storedName", "fileName", "orderId"):
            if key in item:
                entry[key] = item.get(key)
        if entry:
            simplified.append(entry)

    if not simplified:
        return ""

    return json.dumps(simplified, ensure_ascii=False)


def main() -> int:
    args = parse_args()
    outputs = {
        "db_scripts_path": "",
        "data_source": "",
        "db_scripts_manifest": "",
    }

    scripts_path = detect_scripts_dir(args.scripts_dir)
    if scripts_path:
        outputs["db_scripts_path"] = scripts_path

    meta_dir = Path(args.meta_dir) if args.meta_dir else None
    if meta_dir and meta_dir.is_dir():
        data_source = extract_data_source(meta_dir)
        if data_source:
            outputs["data_source"] = data_source

        manifest = extract_manifest(meta_dir)
        if manifest:
            outputs["db_scripts_manifest"] = manifest

    try:
        output_file = Path(args.output)
        with output_file.open("a", encoding="utf-8") as handle:
            for key, value in outputs.items():
                handle.write(f"{key}={value}\n")
    except OSError as exc:
        print(f"::error::No se pudieron escribir los outputs: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
