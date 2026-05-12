from __future__ import annotations

import json
from typing import Any

from app.catalog.sqlite_catalog import SQLiteCatalog


class SummaryService:
    def __init__(self) -> None:
        self.catalog = SQLiteCatalog()

    def generate_summary(self, dataset_id: str) -> dict[str, Any]:
        dataset = self.catalog.get_dataset(dataset_id)
        if dataset is None:
            raise ValueError(f"Dataset not found: {dataset_id}")

        files = self.catalog.list_files(dataset_id)

        source = dataset.get("source")
        name = dataset.get("name")
        description = dataset.get("description")
        storage_status = dataset.get("storage_status")

        file_count = len(files)
        formats = sorted({
            f.get("file_format")
            for f in files
            if f.get("file_format")
        })
        splits = sorted({
            f.get("split")
            for f in files
            if f.get("split")
        })
        columns = self._collect_columns(files)

        parts = []

        article = "an" if source == "internal" else "a"
        parts.append(f"{name} is {article} {source} dataset registered in the QEC data lake.")

        if description:
            parts.append(f"Description: {description}")

        parts.append(f"It currently has storage status `{storage_status}`.")

        if file_count:
            parts.append(f"It contains {file_count} registered file(s).")

        if formats:
            parts.append(f"Detected file format(s): {', '.join(formats)}.")

        if splits:
            parts.append(f"Detected split(s): {', '.join(splits)}.")

        if columns:
            shown_columns = ", ".join(columns[:12])
            parts.append(f"Detected schema columns include: {shown_columns}.")

        if source == "zenodo":
            doi = dataset.get("doi")
            source_url = dataset.get("source_url")
            if doi:
                parts.append(f"DOI: {doi}.")
            if source_url:
                parts.append(f"The original record is available remotely.")

        summary = " ".join(parts)

        updated_record = dict(dataset)
        updated_record["summary"] = summary
        updated_record["metadata"] = self._safe_json_loads(dataset.get("metadata_json"))

        self.catalog.upsert_dataset(updated_record)

        return {
            "dataset_id": dataset_id,
            "summary": summary,
        }

    def _collect_columns(self, files: list[dict[str, Any]]) -> list[str]:
        columns: set[str] = set()

        for f in files:
            schema_json = f.get("schema_json")
            if not schema_json:
                continue

            try:
                schema = json.loads(schema_json)
            except json.JSONDecodeError:
                continue

            if isinstance(schema, dict):
                columns.update(schema.keys())

        return sorted(columns)

    def _safe_json_loads(self, raw: str | None) -> dict[str, Any]:
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
