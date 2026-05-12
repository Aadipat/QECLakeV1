import json
import zipfile
from pathlib import Path
from typing import Any

from app.catalog.sqlite_catalog import SQLiteCatalog
from app.services.validation_service import ValidationService


class ExportService:
    def __init__(self, export_root: str = "exports") -> None:
        self.catalog = SQLiteCatalog()
        self.export_root = Path(export_root)
        self.export_root.mkdir(parents=True, exist_ok=True)

    def export_dataset_package(self, dataset_id: str) -> dict[str, Any]:
        dataset = self.catalog.get_dataset(dataset_id)
        if dataset is None:
            raise ValueError(f"Dataset not found: {dataset_id}")

        files = self.catalog.list_files(dataset_id)
        validation_report = ValidationService().validate_dataset(dataset_id)

        package_dir = self.export_root / dataset_id
        package_dir.mkdir(parents=True, exist_ok=True)

        metadata_path = package_dir / "metadata.json"
        summary_path = package_dir / "summary.md"
        manifest_path = package_dir / "manifest.json"
        validation_path = package_dir / "validation_report.json"

        manifest = {
            "dataset_id": dataset_id,
            "name": dataset.get("name"),
            "source": dataset.get("source"),
            "storage_status": dataset.get("storage_status"),
            "files": files,
        }

        metadata_path.write_text(
            json.dumps(dataset, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        summary_path.write_text(
            dataset.get("summary") or "",
            encoding="utf-8",
        )

        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        validation_path.write_text(
            json.dumps(validation_report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        zip_path = package_dir / f"{dataset_id}_package.zip"

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(metadata_path, arcname="metadata.json")
            zipf.write(summary_path, arcname="summary.md")
            zipf.write(manifest_path, arcname="manifest.json")
            zipf.write(validation_path, arcname="validation_report.json")

            if dataset.get("storage_status") != "remote_only":
                self._add_local_files(zipf, files)

        saved = self.catalog.save_export_package(
            dataset_id=dataset_id,
            package_path=str(zip_path),
            package_format="zip",
            manifest=manifest,
        )

        return {
            "dataset_id": dataset_id,
            "package_path": str(zip_path),
            "export_record": saved,
        }

    def _add_local_files(
        self,
        zipf: zipfile.ZipFile,
        files: list[dict[str, Any]],
    ) -> None:
        for f in files:
            file_path = f.get("file_path")
            if not file_path:
                continue

            path = Path(file_path)
            if not path.exists():
                continue

            zipf.write(path, arcname=f"files/{path.name}")