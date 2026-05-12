from __future__ import annotations

# Store an existed parquet dataset into SQLite registry。--> upload metadata to sqlite
from pathlib import Path
from typing import Any

import pandas as pd

from app.catalog.sqlite_catalog import SQLiteCatalog


class ParquetService:
    def __init__(self) -> None:
        self.catalog = SQLiteCatalog()

    def register_dataset(
        self,
        dataset_id: str,
        name: str,
        path: str,
        description: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        dataset_path = Path(path)

        if not dataset_path.exists():
            raise FileNotFoundError(f"Path does not exist: {path}")

        parquet_files = list(dataset_path.rglob("*.parquet"))

        if not parquet_files:
            raise ValueError(f"No parquet files found under: {path}")

        record = {
            "dataset_id": dataset_id,
            "name": name,
            "source": "internal",
            "description": description,
            "local_path": str(dataset_path),
            "storage_status": "registered_local",
            "metadata": {
                "tags": tags or [],
                "file_count": len(parquet_files),
            },
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
            "files_registered": len(parquet_files),
        }

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
        df = pd.read_parquet(file_path)
        return {column: str(dtype) for column, dtype in df.dtypes.items()}
