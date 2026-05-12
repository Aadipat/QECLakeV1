from pathlib import Path
import sqlite3


"""
Create and connect to the project SQLite database.    # This database stores metadata only. 
It does not store raw datasets,parquet files, Zenodo archives, or other large data file
"""

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "qec_registry.sqlite3" # Stores metadata only

def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    conn = get_connection()
    cur = conn.cursor()
    
    # Create the datasets table. Each row is a dataset

    cur.execute("""
    CREATE TABLE IF NOT EXISTS datasets (
        dataset_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        source TEXT NOT NULL,
        description TEXT,
        summary TEXT,
        doi TEXT,
        source_url TEXT,
        local_path TEXT,
        storage_status TEXT NOT NULL DEFAULT 'remote_only',
        metadata_json TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """)
    
    # Create the dataset file table --> the files each dataset has
    cur.execute("""
        CREATE TABLE IF NOT EXISTS dataset_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dataset_id TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_path TEXT,
            file_url TEXT,
            file_format TEXT,
            size_bytes INTEGER,
            split TEXT,
            schema_json TEXT,
            FOREIGN KEY(dataset_id) REFERENCES datasets(dataset_id)
        )
        """)
    
    # Validation reports
    cur.execute("""
        CREATE TABLE IF NOT EXISTS validation_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dataset_id TEXT NOT NULL,
            valid INTEGER NOT NULL,
            errors_json TEXT,
            warnings_json TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(dataset_id) REFERENCES datasets(dataset_id)
        )
        """)

    # Store export package paths and manifests.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS export_packages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dataset_id TEXT NOT NULL,
            package_path TEXT NOT NULL,
            package_format TEXT NOT NULL DEFAULT 'zip',
            manifest_json TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(dataset_id) REFERENCES datasets(dataset_id)
        )
        """)
    conn.commit()
    conn.close()
