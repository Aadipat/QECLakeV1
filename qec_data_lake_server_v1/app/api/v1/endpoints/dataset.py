"""
Dataset Registry API: FastAPI
  
"""


from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from pathlib import Path
from typing import Optional

from fastapi.responses import FileResponse
from app.catalog.sqlite_catalog import SQLiteCatalog
from app.services.metadata_service import MetadataService
from app.services.parquet_service import ParquetService
from app.services.summary_service import SummaryService
from app.services.validation_service import ValidationService
from app.services.export_service import ExportService

router = APIRouter(prefix="/registry/datasets", tags=["Dataset Registry"])

class RegisterParquetPayload(BaseModel):
    dataset_id: str
    name: str
    path: str
    description: Optional[str] = None
    tags: list[str] = Field(default_factory=list)


class RegisterMetadataFilePayload(BaseModel):
    metadata_path: str


@router.get("")
def list_registered_datasets():
    catalog = SQLiteCatalog()
    return catalog.list_datasets()


@router.get("/{dataset_id}")
def get_registered_dataset(dataset_id: str):
    catalog = SQLiteCatalog()
    dataset = catalog.get_dataset(dataset_id)

    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found")

    return {
        "dataset": dataset,
        "files": catalog.list_files(dataset_id),
    }


@router.post("/register/parquet")
def register_parquet_dataset(payload: RegisterParquetPayload):
    
    service = ParquetService()

    try:
        return service.register_dataset(
            dataset_id=payload.dataset_id,
            name=payload.name,
            path=payload.path,
            description=payload.description,
            tags=payload.tags,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/register/metadata-file")
def register_dataset_from_metadata_file(payload: RegisterMetadataFilePayload):
    service = MetadataService()

    try:
        return service.register_from_file(payload.metadata_path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@router.post("/{dataset_id}/summary")
def generate_dataset_summary(dataset_id: str):
    service = SummaryService()

    try:
        return service.generate_summary(dataset_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/{dataset_id}/validate")
def validate_dataset(dataset_id: str):
    service = ValidationService()

    try:
        return service.validate_dataset(dataset_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{dataset_id}/validation")
def get_latest_validation_report(dataset_id: str):
    catalog = SQLiteCatalog()
    report = catalog.get_latest_validation_report(dataset_id)

    if report is None:
        raise HTTPException(status_code=404, detail="No validation report found")

    return report

@router.post("/{dataset_id}/export")
def export_dataset(dataset_id: str):
    service = ExportService()

    try:
        return service.export_dataset_package(dataset_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{dataset_id}/export")
def get_latest_export(dataset_id: str):
    catalog = SQLiteCatalog()
    record = catalog.get_latest_export_package(dataset_id)

    if record is None:
        raise HTTPException(status_code=404, detail="No export package found")

    return record


@router.get("/{dataset_id}/package")
def download_dataset_package(dataset_id: str):
    catalog = SQLiteCatalog()
    record = catalog.get_latest_export_package(dataset_id)

    if record is None:
        raise HTTPException(status_code=404, detail="No export package found")

    package_path = Path(record["package_path"])

    if not package_path.exists():
        raise HTTPException(status_code=404, detail="Export package file does not exist")

    return FileResponse(
        path=package_path,
        filename=package_path.name,
        media_type="application/zip",
    )
