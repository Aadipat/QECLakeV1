# QEC Data Lake UI / Registry Intro

This document summarizes what I have implemented so far and what the current limitations are.

## Project Goal

It does not store large raw datasets directly inside SQLite. Instead, SQLite stores dataset metadata, local file paths, remote file URLs, validation reports, summaries, and export package records.

The main workflow is:

1. Register internal/local datasets.
2. Search and register Zenodo datasets.
3. Browse registered datasets in the Streamlit UI.
4. Validate dataset records.
5. Prepare export packages and download them.

## System Structure

The project has two main parts:

### FastAPI Backend

The backend starts from:

```bash
uvicorn app.main:app --reload
```

Important backend files:

- `app/main.py`: creates the FastAPI app and includes the API router.
- `app/api/v1/router.py`: combines API endpoint modules.
- `app/api/v1/endpoints/dataset.py`: dataset registry APIs.
- `app/api/v1/endpoints/zenodo.py`: Zenodo search and registration APIs.
- `app/services/*.py`: business logic.
- `app/catalog/sqlite_catalog.py`: reads/writes registry data in SQLite.
- `app/core/sqlite_database.py`: initializes the SQLite database schema. (**)

### Streamlit UI

The UI starts from:

```bash
streamlit run app/ui/streamlit_app.py
```

The UI calls the FastAPI backend at:

```text
http://localhost:8000/api/v1
```

So the FastAPI backend must be running before the Streamlit UI can fully work.

## What I Implemented

### 1. Browse Registry Page

This page shows all registered datasets from SQLite.

For each dataset, the user can inspect:

- dataset name
- source
- storage status
- file count
- dataset ID
- description or summary
- file records

The dataset detail view now prefers showing `description` first. If no description exists, it falls back to `summary`. If neither exists, it builds a basic metadata overview from the registered metadata and files.

### 2. Register Internal Dataset

This page now has two registration options.

#### Manual Form

This is the original internal registration flow.

The user enters:

- dataset ID
- dataset name
- local parquet folder path
- description
- tags

The backend scans parquet files under the local folder and registers file paths, file sizes, split names, and schema metadata if available.

#### Metadata File

I added a metadata-file registration flow for the ETL/data lake team.
🔴 **You can merge ur metadata format here**

The user can provide a `metadata.yaml`, `metadata.yml`, or `metadata.json` file. The backend reads the metadata file, finds the `local_path`, scans parquet files, and writes everything into the SQLite registry.

Minimal metadata file example:

```yaml
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
domain: quantum error correction
code_type: surface_code
decoder: matching
noise_model: depolarizing
```

Required fields:

- `dataset_id`
- `name`
- `local_path`

The `local_path` can point to either:

- a parquet folder
- a single `.parquet` file

Extra fields such as `authors`, `license`, `domain`, `decoder`, `noise_model`, and `use_case` are preserved in `metadata_json`.

### 3. Zenodo Search and Registration

The Zenodo search page lets the user search public Zenodo records.

The UI calls:

```text
GET /api/v1/zenodo/search?q=...&size=...
```

The backend then calls the Zenodo API:

```text
https://zenodo.org/api/records
```

Current Zenodo search parameters:

```python
params = {
    "q": query,
    "size": size,
    "sort": "bestmatch",
}
```

After search, the user can inspect a Zenodo record and register it into the local SQLite registry. For Zenodo datasets, the system stores metadata and remote file URLs. It does not automatically download the real files.

### 4. Dataset Actions

In the Browse Registry page, each selected dataset has actions:

- `Validate`: checks whether required metadata and file records exist.
- `Prepare Package`: creates a zip export package.
- `Download`: downloads the latest prepared package.
- `Regenerate Summary`: hidden under Advanced Summary, because summary generation is currently lightweight and rule-based.

`Prepare Package` and `Download` are different:

- `Prepare Package` creates the export zip.
- `Download` downloads the latest existing zip.

## Current AI Chat / Query Logic

The sidebar has an `AI Dataset Finder`, but it is important to clarify that it is not currently a real LLM-based chatbot.

At the moment, the logic is only basic local **keyword matching**. (Stupid method 😞)

The implementation is in:

```text
app/ui/streamlit_app.py
```

Function:

```python
def match_datasets(query, datasets):
    ...
```

How it works:

1. It splits the user query into simple tokens using a regular expression.
2. It creates a searchable text field from each dataset's:
   - `dataset_id`
   - `name`. (‼️ we can remove this feature if u want, since we barely search author's name to look for a dataset)
   - `source`
   - `description`
   - `summary`
   - `metadata_json`
3. It counts how many query tokens appear in that searchable text.
4. It returns the top 5 matching datasets.

So if the user asks:

```text
surface code syndrome data
```

The system searches for words like:

```text
surface, code, syndrome, data
```

inside the local registry metadata.

This means the current AI chat is only a lightweight keyword search UI. It does not yet:

- call an LLM
- understand semantic similarity
- generate natural language reasoning
- rank results with embeddings
- search inside raw parquet data
- search external sources automatically

## Current Search Query Logic

There are two different search/query mechanisms:

### Local Registry Search

Used by the sidebar AI Dataset Finder.

Current method:

```text
basic keyword match against local registered metadata
```

This is simple and fast, but not semantically intelligent.

### Zenodo Search

Used by the Discover from Zenodo page.

Current method:

```text
send query string to Zenodo API
```

The project does not implement its own Zenodo ranking model. It relies on Zenodo's `bestmatch` search result ordering.

## Current Limitations

- The AI Dataset Finder is not a real LLM agent yet.
- Local search is only keyword-based.
- There is no embedding/vector search yet.
- There is no semantic search over dataset contents.
🔴 **👆These are mainly about the query thing**
- SQLite stores metadata only, not large raw datasets.
- Zenodo registration stores remote URLs but does not download files.
- Schema extraction depends on parquet support. If `pyarrow` is not installed, the dataset can still be registered, but schema fields may be empty.
- The metadata schema is still flexible and not fully standardized.(**🔴 u decide it**)


## How to Run

Start the backend:

```bash
cd qec_data_lake_server_v1
uvicorn app.main:app --reload
```

Start the UI in another terminal:

```bash
cd qec_data_lake_server_v1
streamlit run app/ui/streamlit_app.py
```
