from pathlib import Path
from typing import Any

from app.catalog.sqlite_catalog import SQLiteCatalog


class ValidationService:
    def __init__(self) -> None:
        self.catalog = SQLiteCatalog()

    def validate_dataset(self, dataset_id: str) -> dict[str, Any]:
        dataset = self.catalog.get_dataset(dataset_id)
        if dataset is None:
            raise ValueError(f"Dataset not found: {dataset_id}")

        files = self.catalog.list_files(dataset_id)

        errors: list[str] = []
        warnings: list[str] = []

        self._validate_dataset_record(dataset, errors, warnings)
        self._validate_file_records(dataset, files, errors, warnings)

        valid = len(errors) == 0

        report = self.catalog.save_validation_report(
            dataset_id=dataset_id,
            valid=valid,
            errors=errors,
            warnings=warnings,
        )

        return report

    def _validate_dataset_record(
        self,
        dataset: dict[str, Any],
        errors: list[str],
        warnings: list[str],
    ) -> None:
        if not dataset.get("dataset_id"):
            errors.append("Missing dataset_id.")

        if not dataset.get("name"):
            errors.append("Missing dataset name.")

        if not dataset.get("source"):
            errors.append("Missing dataset source.")

        if not dataset.get("storage_status"):
            errors.append("Missing storage_status.")

        if not dataset.get("summary"):
            warnings.append("Missing lightweight summary.")

        storage_status = dataset.get("storage_status")

        if storage_status in {"registered_local", "cached_locally", "processed"}:
            local_path = dataset.get("local_path")
            if not local_path:
                errors.append("Local dataset is missing local_path.")
            elif not Path(local_path).exists():
                errors.append(f"local_path does not exist: {local_path}")

    def _validate_file_records(
        self,
        dataset: dict[str, Any],
        files: list[dict[str, Any]],
        errors: list[str],
        warnings: list[str],
    ) -> None:
        if not files:
            warnings.append("No file records registered for this dataset.")
            return

        storage_status = dataset.get("storage_status")

        for f in files:
            file_name = f.get("file_name")

            if not file_name:
                errors.append("A file record is missing file_name.")

            if storage_status == "remote_only":
                if not f.get("file_url"):
                    warnings.append(f"Remote file `{file_name}` is missing file_url.")

            if storage_status in {"registered_local", "cached_locally", "processed"}:
                file_path = f.get("file_path")

                if not file_path:
                    errors.append(f"Local file `{file_name}` is missing file_path.")
                elif not Path(file_path).exists():
                    errors.append(f"Local file does not exist: {file_path}")

            if f.get("file_format") == "parquet" and not f.get("schema_json"):
                warnings.append(f"Parquet file `{file_name}` has no stored schema_json.")