from __future__ import annotations

from typing import Any

import requests

from app.catalog.sqlite_catalog import SQLiteCatalog


class ZenodoService:
    BASE_URL = "https://zenodo.org/api/records"

    def __init__(self) -> None:
        self.catalog = SQLiteCatalog()

    def search_records(self, query: str, size: int = 10) -> list[dict[str, Any]]:
        params = {
            "q": query,
            "size": size,
            "sort": "bestmatch",
        }

        response = requests.get(self.BASE_URL, params=params, timeout=60)
        response.raise_for_status()

        payload = response.json()
        hits = payload.get("hits", {}).get("hits", [])

        return [self._normalize_record(hit) for hit in hits]

    def register_record(self, record: dict[str, Any]) -> dict[str, Any]:
        dataset_id = f"zenodo_{record['record_id']}"

        dataset_record = {
            "dataset_id": dataset_id,
            "name": record["title"],
            "source": "zenodo",
            "description": record.get("description"),
            "summary": record.get("summary"),
            "doi": record.get("doi"),
            "source_url": record.get("source_url"),
            "local_path": None,
            "storage_status": "remote_only",
            "metadata": {
                "keywords": record.get("keywords", []),
                "creators": record.get("creators", []),
                "publication_date": record.get("publication_date"),
                "license": record.get("license"),
                "zenodo_record_id": record["record_id"],
            },
        }

        self.catalog.upsert_dataset(dataset_record)

        for file_record in record.get("files", []):
            self.catalog.add_file(dataset_id, {
                "file_name": file_record.get("file_name"),
                "file_url": file_record.get("file_url"),
                "file_format": self._guess_file_format(file_record.get("file_name")),
                "size_bytes": file_record.get("size_bytes"),
                "split": None,
                "schema": {},
            })

        return {
            "dataset": dataset_record,
            "files_registered": len(record.get("files", [])),
        }

    def _normalize_record(self, raw: dict[str, Any]) -> dict[str, Any]:
        metadata = raw.get("metadata", {})
        links = raw.get("links", {})
        files = raw.get("files", [])

        normalized_files = []
        for f in files:
            file_links = f.get("links", {})
            normalized_files.append({
                "file_name": f.get("key"),
                "file_url": file_links.get("self"),
                "size_bytes": f.get("size"),
                "checksum": f.get("checksum"),
            })

        title = metadata.get("title") or f"Zenodo record {raw.get('id')}"
        description = metadata.get("description") or ""

        return {
            "record_id": str(raw.get("id")),
            "title": title,
            "description": description,
            "doi": metadata.get("doi"),
            "source_url": links.get("html"),
            "keywords": metadata.get("keywords", []),
            "creators": metadata.get("creators", []),
            "publication_date": metadata.get("publication_date"),
            "license": metadata.get("license"),
            "files": normalized_files,
            "summary": self._make_lightweight_summary(title, metadata, normalized_files),
        }

    def _make_lightweight_summary(
        self,
        title: str,
        metadata: dict[str, Any],
        files: list[dict[str, Any]],
    ) -> str:
        keywords = metadata.get("keywords", [])
        file_count = len(files)

        summary = f"{title} is a Zenodo record with {file_count} file(s)."

        if keywords:
            summary += f" Keywords include: {', '.join(keywords[:8])}."

        return summary

    def _guess_file_format(self, file_name: str | None) -> str | None:
        if not file_name or "." not in file_name:
            return None
        return file_name.rsplit(".", 1)[-1].lower()
