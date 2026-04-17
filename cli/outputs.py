"""CLI-facing output dataclasses.

These wrap service/repository results that don't already have a typed shape,
giving the `OutputWriter` a stable, typed surface for text (and later JSON)
rendering.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class IngestResultOutput:
    parsed: int
    inserted: int
    skipped: int
    categorized: int
    data_import_id: int
    archive_path: Optional[str] = None


@dataclass
class MigrationStatusRow:
    migration_file: str
    status: str  # "APPLIED" | "PENDING"


@dataclass
class MigrationStatusOutput:
    migrations: list[MigrationStatusRow]
    total: int
    applied: int
    pending: int


@dataclass
class BackupResultOutput:
    output_path: str


@dataclass
class UpdateFromCsvOutput:
    total_updated: int
    category_updated: int
    category_auto_accepted: int
    merchant_updated: int
    merchant_auto_accepted: int
    amortization_updated: int
    skipped: int


@dataclass
class ExportResultOutput:
    total_exported: int
    output_path: str


@dataclass
class SeedResultOutput:
    created: int
    skipped: int
    total: int
