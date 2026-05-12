from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from app.catalog.sqlite_catalog import SQLiteCatalog


class MetadataService:
    """
    Register an internal dataset from a metadata.yaml or metadata.json file.

    Expected minimal metadata:
        dataset_id: surface_code_v1
        name: Surface Code Syndrome Dataset
        local_path: /path/to/parquet/folder

    Optional fields such as description, tags, authors, license, domain, and
    provenance are preserved in datasets.metadata_json.
    
    
    ################# Assumes yaml format ########################
    dataset_id: surface_code_v1
    name: Surface Code Syndrome Dataset
    local_path: /path/to/parquet/folder
    description: Dataset for surface code decoding benchmarks.
    tags:
    - surface code
    - qec
    - syndrome
    authors:
    - Alice Zhang
    license: MIT
    domain:
    code_type: surface_code
    decoder: matching
    noise_model: depolarizing

    """

    REQUIRED_FIELDS = ("dataset_id", "name", "local_path")

    def __init__(self) -> None:
        self.catalog = SQLiteCatalog()

    def register_from_file(self, metadata_path: str) -> dict[str, Any]:
        path = Path(metadata_path).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"Metadata file does not exist: {metadata_path}")

        metadata = self._read_metadata_file(path)
        self._validate_metadata(metadata)

        dataset_path = Path(str(metadata["local_path"])).expanduser()
        parquet_files = self._find_parquet_files(dataset_path)

        dataset_id = str(metadata["dataset_id"])
        reserved_keys = {
            "dataset_id",
            "name",
            "description",
            "summary",
            "doi",
            "source_url",
            "local_path",
            "storage_status",
        }
        extra_metadata = {
            key: value
            for key, value in metadata.items()
            if key not in reserved_keys
        }
        extra_metadata["file_count"] = len(parquet_files)
        extra_metadata["metadata_file"] = str(path)

        record = {
            "dataset_id": dataset_id,
            "name": str(metadata["name"]),
            "source": str(metadata.get("source", "internal")),
            "description": metadata.get("description"),
            "summary": metadata.get("summary"),
            "doi": metadata.get("doi"),
            "source_url": metadata.get("source_url"),
            "local_path": str(dataset_path),
            "storage_status": str(metadata.get("storage_status", "registered_local")),
            "metadata": extra_metadata,
        }

        self.catalog.upsert_dataset(record)

        for file_path in parquet_files:
            self.catalog.add_file(dataset_id, {
                "file_name": file_path.name,
                "file_path": str(file_path),
                "file_format": "parquet",
                "size_bytes": file_path.stat().st_size,
                "split": self._infer_split(file_path),
                "schema": self._read_schema(file_path),
            })

        return {
            "dataset": record,
            "metadata_file": str(path),
            "files_registered": len(parquet_files),
        }

    def _read_metadata_file(self, path: Path) -> dict[str, Any]:
        suffix = path.suffix.lower()
        raw = path.read_text(encoding="utf-8")

        if suffix in {".yaml", ".yml"}:
            parsed = yaml.safe_load(raw)
        elif suffix == ".json":
            parsed = json.loads(raw)
        else:
            raise ValueError("Metadata file must be .yaml, .yml, or .json")

        if not isinstance(parsed, dict):
            raise ValueError("Metadata file must contain a top-level object")

        return parsed

    def _validate_metadata(self, metadata: dict[str, Any]) -> None:
        missing = [
            field
            for field in self.REQUIRED_FIELDS
            if not metadata.get(field)
        ]
        if missing:
            raise ValueError(f"Metadata file is missing required field(s): {', '.join(missing)}")

    def _find_parquet_files(self, dataset_path: Path) -> list[Path]:
        if not dataset_path.exists():
            raise FileNotFoundError(f"Dataset local_path does not exist: {dataset_path}")

        if dataset_path.is_file():
            if dataset_path.suffix.lower() != ".parquet":
                raise ValueError(f"Dataset local_path is not a parquet file: {dataset_path}")
            return [dataset_path]

        parquet_files = sorted(dataset_path.rglob("*.parquet"))
        if not parquet_files:
            raise ValueError(f"No parquet files found under: {dataset_path}")

        return parquet_files

    def _infer_split(self, file_path: Path) -> str | None:
        name = file_path.name.lower()

        if "train" in name:
            return "train"
        if "dev" in name or "valid" in name or "validation" in name:
            return "dev"
        if "test" in name:
            return "test"

        return None

    def _read_schema(self, file_path: Path) -> dict[str, str]:
        try:
            import pyarrow.parquet as pq

            schema = pq.read_schema(file_path)
            return {field.name: str(field.type) for field in schema}
        except ImportError:
            return {}
