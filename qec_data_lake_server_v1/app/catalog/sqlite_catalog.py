from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.core.sqlite_database import get_connection

"""
Read and write dataset records from SQLite, including dataset metadata, 
file records, validation reports, and export package records.
"""


class SQLiteCatalog:
    
    def list_datasets(self) -> list[dict[str, Any]]:
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM datasets ORDER BY updated_at DESC"
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_dataset(self, dataset_id: str) -> dict[str, Any] | None:
        conn = get_connection()
        row = conn.execute(
            "SELECT * FROM datasets WHERE dataset_id = ?",
            (dataset_id,),
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def list_files(self, dataset_id: str) -> list[dict[str, Any]]:
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM dataset_files WHERE dataset_id = ?",
            (dataset_id,),
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def save_validation_report(
        self,
        dataset_id: str,
        valid: bool,
        errors: list[str] | None = None,
        warnings: list[str] | None = None,
    ) -> dict[str, Any]:
        

        now = datetime.now(timezone.utc).isoformat()

        report = {
            "dataset_id": dataset_id,
            "valid": valid,
            "errors": errors or [],
            "warnings": warnings or [],
            "created_at": now,
        }

        conn = get_connection()
        
        
        conn.execute("""
        INSERT INTO validation_reports (
            dataset_id, valid, errors_json, warnings_json, created_at
        )
        VALUES (?, ?, ?, ?, ?)
        """, (
            dataset_id,
            1 if valid else 0,
            json.dumps(errors or []),
            json.dumps(warnings or []),
            now,
        ))
        conn.commit()
        conn.close()

        return report

    def get_latest_validation_report(
        self,
        dataset_id: str,
    ) -> dict[str, Any] | None:
        
        conn = get_connection()
        row = conn.execute("""
        SELECT * FROM validation_reports
        WHERE dataset_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """, (dataset_id,)).fetchone()
        conn.close()

        
        if row is None:
            return None

        result = dict(row)
        result["valid"] = bool(result["valid"])

        if result.get("errors_json"):
            result["errors"] = json.loads(result["errors_json"])
        else:
            result["errors"] = []

        if result.get("warnings_json"):
            result["warnings"] = json.loads(result["warnings_json"])
        else:
            result["warnings"] = []

        return result

    def upsert_dataset(self, record: dict[str, Any]) -> dict[str, Any]:
        now = datetime.utcnow().isoformat()

        conn = get_connection()
        conn.execute("""
        INSERT INTO datasets (
            dataset_id, name, source, description, summary, doi,
            source_url, local_path, storage_status, metadata_json,
            created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(dataset_id) DO UPDATE SET
            name=excluded.name,
            source=excluded.source,
            description=excluded.description,
            summary=excluded.summary,
            doi=excluded.doi,
            source_url=excluded.source_url,
            local_path=excluded.local_path,
            storage_status=excluded.storage_status,
            metadata_json=excluded.metadata_json,
            updated_at=excluded.updated_at
        """, (
            record["dataset_id"],
            record["name"],
            record["source"],
            record.get("description"),
            record.get("summary"),
            record.get("doi"),
            record.get("source_url"),
            record.get("local_path"),
            record.get("storage_status", "remote_only"),
            json.dumps(record.get("metadata", {})),
            now,
            now,
        ))
        conn.commit()
        conn.close()
        return record

    def add_file(self, dataset_id: str, file_record: dict[str, Any]) -> None:
        conn = get_connection()
        conn.execute("""
        INSERT INTO dataset_files (
            dataset_id, file_name, file_path, file_url,
            file_format, size_bytes, split, schema_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            dataset_id,
            file_record["file_name"],
            file_record.get("file_path"),
            file_record.get("file_url"),
            file_record.get("file_format"),
            file_record.get("size_bytes"),
            file_record.get("split"),
            json.dumps(file_record.get("schema", {})),
        ))
        
        
        
        
        
        
        
        conn.commit()
        conn.close()

    def save_export_package(
        self,
        dataset_id: str,
        package_path: str,
        package_format: str = "zip",
        manifest: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()

        record = {
            "dataset_id": dataset_id,
            "package_path": package_path,
            "package_format": package_format,
            "manifest": manifest or {},
            "created_at": now,
        }

        conn = get_connection()
        conn.execute("""
        INSERT INTO export_packages (
            dataset_id, package_path, package_format, manifest_json, created_at
        )
        VALUES (?, ?, ?, ?, ?)
        """, (
            dataset_id,
            package_path,
            package_format,
            json.dumps(manifest or {}),
            now,
        ))
        conn.commit()
        conn.close()

        return record

    def get_latest_export_package(
        self,
        dataset_id: str,
    ) -> dict[str, Any] | None:
        conn = get_connection()
        row = conn.execute("""
        SELECT * FROM export_packages
        WHERE dataset_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """, (dataset_id,)).fetchone()
        conn.close()

        if row is None:
            return None

        result = dict(row)

        if result.get("manifest_json"):
            result["manifest"] = json.loads(result["manifest_json"])
        else:
            result["manifest"] = {}

        return result
