from __future__ import annotations

import html
import json
import re
from typing import Any

import requests
import streamlit as st

# FastAPI
API_BASE = "http://localhost:8000/api/v1"
ZENODO_PAGE_SIZE = 10


st.set_page_config(page_title="QEC Data Lake", layout="wide")


def api_get(path: str, params: dict | None = None):
    response = requests.get(f"{API_BASE}{path}", params=params, timeout=60)
    response.raise_for_status()
    return response.json()


def api_post(path: str, payload: dict | None = None):
    response = requests.post(f"{API_BASE}{path}", json=payload or {}, timeout=120)
    response.raise_for_status()
    return response.json()


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    text = re.sub(r"<[^>]+>", " ", value)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def safe_json_loads(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def get_latest_export(dataset_id: str) -> dict[str, Any] | None:
    try:
        return api_get(f"/registry/datasets/{dataset_id}/export")
    except Exception:
        return None


def build_metadata_overview(dataset: dict[str, Any], files: list[dict[str, Any]]) -> str:
    metadata = safe_json_loads(dataset.get("metadata_json"))
    parts = [
        f"{dataset.get('name') or dataset.get('dataset_id')} is a {dataset.get('source') or 'registered'} dataset.",
        f"It has {len(files)} registered file(s).",
    ]

    tags = metadata.get("tags") or metadata.get("keywords") or []
    if tags:
        parts.append(f"Tags include: {', '.join(str(tag) for tag in tags[:8])}.")

    formats = sorted({file.get("file_format") for file in files if file.get("file_format")})
    if formats:
        parts.append(f"File format(s): {', '.join(formats)}.")

    columns: set[str] = set()
    for file in files:
        schema = safe_json_loads(file.get("schema_json"))
        columns.update(schema.keys())
    if columns:
        shown_columns = ", ".join(sorted(columns)[:12])
        parts.append(f"Detected schema columns include: {shown_columns}.")

    return " ".join(parts)


def render_chip_row(values: list[str], limit: int = 10) -> None:
    if not values:
        st.caption("No tags available.")
        return

    shown = values[:limit]
    chips = " ".join(f"`{value}`" for value in shown if value)
    if chips:
        st.markdown(chips)

    remaining = len(values) - len(shown)
    if remaining > 0:
        st.caption(f"+ {remaining} more")


def render_page_nav() -> str:
    page_options = [
        "Browse Registry",
        "Register Internal Parquet",
        "Discover from Zenodo",
    ]

    if "page" not in st.session_state:
        st.session_state["page"] = page_options[0]

    st.markdown(
        """
        <style>
        h1 {
            font-size: 2.5rem !important;
        }

        h2 {
            font-size: 2rem !important;
        }

        h3 {
            font-size: 1.55rem !important;
        }

        /* Segmented control buttons */
        div[data-testid="stSegmentedControl"] button {
            font-size: 30px !important;
            padding: 0.9rem 1.5rem !important;
            min-height: 3.4rem !important;
        }

        /* Segmented control text */
        div[data-testid="stSegmentedControl"] button p {
            font-size: 30px !important;
            font-weight: 600 !important;
        }

        div[data-testid="stMarkdownContainer"] p,
        div[data-testid="stCaptionContainer"] p,
        div[data-testid="stDataFrame"] {
            font-size: 1rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("QEC Data Lake Registry")

    selected_page = st.segmented_control(
        "Navigation",
        page_options,
        default=st.session_state["page"],
        label_visibility="collapsed",
    )
    if selected_page and selected_page != st.session_state["page"]:
        st.session_state["page"] = selected_page
        st.rerun()

    st.divider()
    return st.session_state["page"]


def load_registry() -> list[dict[str, Any]]:
    try:
        return api_get("/registry/datasets")
    except Exception as exc:
        st.error(f"Failed to load registry: {exc}")
        return []


# AI chatbot query logic. Simple local keyword search for the sidebar dataset finder.
def match_datasets(query: str, datasets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # regular
    tokens = [token.lower() for token in re.findall(r"[A-Za-z0-9_+-]+", query)]
    if not tokens:
        return []

    scored = []
    for dataset in datasets:
        haystack = " ".join(
            str(dataset.get(field) or "")
            for field in ("dataset_id", "name", "source", "description", "summary", "metadata_json")
        ).lower()
        score = sum(1 for token in tokens if token in haystack)
        if score:
            scored.append((score, dataset))

    return [dataset for _, dataset in sorted(scored, key=lambda item: item[0], reverse=True)[:5]]



####################### Side bar ################################
def render_sidebar_chatbot() -> None:
    with st.sidebar:
        st.subheader("AI Dataset Finder")
        st.caption("Describe the QEC dataset you need. I will search the local registry first.")

        datasets = load_registry()

        if "chat_messages" not in st.session_state:
            st.session_state["chat_messages"] = [
                {
                    "role": "assistant",
                    "content": "Tell me about the dataset you need, for example surface code syndrome data or QEC decoder benchmarks.",
                }
            ]

        for message in st.session_state["chat_messages"]:
            with st.chat_message(message["role"]):
                st.write(message["content"])

        prompt = st.chat_input("What dataset are you looking for?")
        if prompt:
            st.session_state["chat_messages"].append({"role": "user", "content": prompt})
            matches = match_datasets(prompt, datasets)

            if matches:
                lines = ["I found these local registry matches:"]
                for dataset in matches:
                    lines.append(f"- {dataset.get('name')} (`{dataset.get('dataset_id')}`)")
                lines.append("Open Browse Registry and click the row to inspect details.")
                answer = "\n".join(lines)
            else:
                answer = (
                    "I did not find a strong local match yet. Try Discover from Zenodo with this search phrase, "
                    "then register the best matching record."
                )

            st.session_state["chat_messages"].append({"role": "assistant", "content": answer})
            st.rerun()


def render_dataset_actions(dataset_id: str) -> None:
    st.markdown("#### Dataset actions")
    export_record = get_latest_export(dataset_id)
    export_ready_key = f"export_ready_{dataset_id}"
    action_cols = st.columns([1, 1.25, 1.1, 4.5])

    with action_cols[0]:
        if st.button("Validate", key=f"validate_{dataset_id}", use_container_width=True):
            try:
                st.session_state["last_action_result"] = api_post(f"/registry/datasets/{dataset_id}/validate")
                st.success("Validation completed")
            except Exception as exc:
                st.error(f"Validation failed: {exc}")

    with action_cols[1]:
        if st.button("Prepare Package", key=f"export_{dataset_id}", use_container_width=True):
            try:
                st.session_state["last_action_result"] = api_post(f"/registry/datasets/{dataset_id}/export")
                st.session_state[export_ready_key] = True
                st.success("Package prepared")
            except Exception as exc:
                st.error(f"Package preparation failed: {exc}")

    with action_cols[2]:
        package_url = f"{API_BASE}/registry/datasets/{dataset_id}/package"
        st.link_button(
            "Download",
            package_url,
            use_container_width=True,
            disabled=export_record is None and not st.session_state.get(export_ready_key),
        )

    with st.expander("Advanced summary"):
        st.caption("Use this only when you want to refresh the saved lightweight summary.")
        if st.button("Regenerate Summary", key=f"summary_{dataset_id}"):
            try:
                st.session_state["last_action_result"] = api_post(f"/registry/datasets/{dataset_id}/summary")
                st.success("Summary regenerated")
                st.rerun()
            except Exception as exc:
                st.error(f"Summary generation failed: {exc}")


def render_dataset_detail(dataset_id: str) -> None:
    try:
        detail = api_get(f"/registry/datasets/{dataset_id}")
    except Exception as exc:
        st.error(f"Failed to load dataset detail: {exc}")
        return

    dataset = detail.get("dataset", {})
    files = detail.get("files", [])

    st.subheader(dataset.get("name") or dataset_id)
    st.caption(f"{dataset.get('dataset_id')} · {dataset.get('source')} · {dataset.get('storage_status')}")
    render_dataset_actions(dataset_id)
    st.divider()

    description = clean_text(dataset.get("description"))
    summary = clean_text(dataset.get("summary"))

    if description:
        st.markdown("#### Description")
        st.markdown(description)
        if summary and summary != description:
            with st.expander("Saved summary"):
                st.markdown(summary)
    elif summary:
        st.markdown("#### Summary")
        st.markdown(summary)
    else:
        st.markdown("#### Metadata overview")
        st.markdown(build_metadata_overview(dataset, files))

    info_cols = st.columns(4)
    info_cols[0].markdown(f"**Files**  \n{len(files)}")
    info_cols[1].markdown(f"**Source**  \n{dataset.get('source') or 'unknown'}")
    info_cols[2].markdown(f"**Storage**  \n{dataset.get('storage_status') or 'unknown'}")
    info_cols[3].markdown(f"**DOI**  \n{dataset.get('doi') or 'N/A'}")

    if dataset.get("source_url"):
        st.link_button("Open source record", dataset["source_url"])

    if files:
        st.markdown("#### Files")
        file_rows = [
            {
                "file_name": file.get("file_name"),
                "format": file.get("file_format"),
                "split": file.get("split"),
                "size_bytes": file.get("size_bytes"),
                "file_url": file.get("file_url"),
                "file_path": file.get("file_path"),
            }
            for file in files
        ]
        st.dataframe(file_rows, use_container_width=True, hide_index=True)

    result = st.session_state.get("last_action_result")
    if result:
        with st.expander("Latest action result"):
            st.json(result)


def render_browse_registry() -> None:
    st.header("Registered Datasets")
    datasets = load_registry()

    if not datasets:
        st.info("No datasets registered yet.")
        return

    if "selected_dataset_id" not in st.session_state and datasets:
        st.session_state["selected_dataset_id"] = datasets[0].get("dataset_id")

    # st.caption("Click a dataset name to inspect and operate on it.")
    header_cols = st.columns([3.2, 1.1, 1.4, 0.7, 2.2])
    header_cols[0].caption("Name")
    header_cols[1].caption("Source")
    header_cols[2].caption("Storage")
    header_cols[3].caption("Files")
    header_cols[4].caption("Dataset ID")

    for dataset in datasets:
        dataset_id = dataset.get("dataset_id")
        is_selected = dataset_id == st.session_state.get("selected_dataset_id")
        metadata = safe_json_loads(dataset.get("metadata_json"))

        with st.container(border=True):
            row_cols = st.columns([3.2, 1.1, 1.4, 0.7, 2.2])
            if row_cols[0].button(
                dataset.get("name") or dataset_id,
                key=f"select_dataset_{dataset_id}",
                type="primary" if is_selected else "secondary",
                use_container_width=True,
            ):
                st.session_state["selected_dataset_id"] = dataset_id
                st.session_state["last_action_result"] = None
                st.rerun()

            row_cols[1].markdown(dataset.get("source") or "unknown")
            row_cols[2].markdown(dataset.get("storage_status") or "unknown")
            row_cols[3].markdown(str(metadata.get("file_count", "")))
            row_cols[4].code(dataset_id or "")

    st.divider()
    selected_id = st.session_state.get("selected_dataset_id")
    if selected_id:
        render_dataset_detail(selected_id)
    else:
        st.info("Select a dataset row to view details.")


def render_register_internal_parquet() -> None:
    
    st.markdown(
        """
        <style>
        /* Labels inside the form */
        div[data-testid="stForm"] label {
            font-size: 20px !important;
            font-weight: 600 !important;
        }

        /* Text input content */
        div[data-testid="stForm"] input {
            font-size: 18px !important;
        }

        /* Text area content */
        div[data-testid="stForm"] textarea {
            font-size: 18px !important;
        }

        /* Form submit button */
        div[data-testid="stForm"] button {
            font-size: 18px !important;
            padding: 0.6rem 1rem !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.header("Register Internal Dataset")

    manual_tab, metadata_tab = st.tabs(["Manual Form", "Metadata File"])

    with manual_tab:
        with st.form("register_parquet_form"):
            dataset_id = st.text_input("Dataset ID")
            name = st.text_input("Dataset Name")
            path = st.text_input("Local Parquet Folder Path")
            description = st.text_area("Description")
            tags_raw = st.text_input("Tags(comma-separated)")

            submitted = st.form_submit_button("Register Parquet Dataset", type="primary")

        if submitted:
            payload = {
                "dataset_id": dataset_id.strip(),
                "name": name.strip(),
                "path": path.strip(),
                "description": description.strip() or None,
                "tags": [tag.strip() for tag in tags_raw.split(",") if tag.strip()],
            }

            if not payload["dataset_id"] or not payload["name"] or not payload["path"]:
                st.warning("Dataset ID, Dataset Name, and Local Parquet Folder Path are required.")
                return

            try:
                result = api_post("/registry/datasets/register/parquet", payload)
                st.success("Dataset registered")
                st.json(result)
            except Exception as exc:
                st.error(f"Registration failed: {exc}")

    with metadata_tab:
        st.caption("Use this when the ETL/data lake team provides a metadata.yaml or metadata.json file.")
        with st.form("register_metadata_file_form"):
            metadata_path = st.text_input(
                "Metadata File Path",
                placeholder="/path/to/metadata.yaml",
            )
            metadata_submitted = st.form_submit_button("Register from Metadata File", type="primary")

        if metadata_submitted:
            payload = {"metadata_path": metadata_path.strip()}

            if not payload["metadata_path"]:
                st.warning("Metadata File Path is required.")
                return

            try:
                result = api_post("/registry/datasets/register/metadata-file", payload)
                st.success("Dataset registered from metadata file")
                st.json(result)
            except Exception as exc:
                st.error(f"Metadata registration failed: {exc}")


def search_zenodo(query: str, size: int) -> list[dict[str, Any]]:
    result = api_get("/zenodo/search", params={"q": query, "size": size})
    return result.get("results", [])


def render_zenodo_card(record: dict[str, Any], idx: int) -> None:
    title = record.get("title") or f"Zenodo record {idx + 1}"
    files = record.get("files") or []
    keywords = [str(keyword) for keyword in record.get("keywords", []) if keyword]
    creators = record.get("creators") or []
    creator_names = ", ".join(
        creator.get("name", "")
        for creator in creators
        if isinstance(creator, dict) and creator.get("name")
    )

    with st.container(border=True):
        top_cols = st.columns([0.10, 0.70, 0.1])
        top_cols[0].markdown(f"### {idx + 1}")
        top_cols[1].markdown(f"### {title}")
        if top_cols[2].button("View", key=f"view_zenodo_{idx}", use_container_width=True,icon="👀"):
            st.session_state["selected_zenodo_record"] = record
            st.rerun()

        st.caption(
            " · ".join(
                value
                for value in [
                    record.get("publication_date"),
                    f" doi: {record.get('doi')}",
                    # record.get("doi"),
                    # f"{len(files)} file(s)",
                ]
                if value
            )
        )

        summary = clean_text(record.get("summary") or record.get("description"))
        if len(summary) > 360:
            summary = summary[:357].rstrip() + "..."
        st.write(summary or "No description is available.")

        if creator_names:
            st.caption(f"Authors: {creator_names}")

        render_chip_row(keywords, limit=8)


def render_zenodo_detail(record: dict[str, Any]) -> None:
    if st.button("Back to Zenodo results",type="primary"):
        st.session_state["selected_zenodo_record"] = None
        st.rerun()

    st.subheader(record.get("title") or "Zenodo Dataset")

    metadata_cols = st.columns(4)
    metadata_cols[0].metric("Files", len(record.get("files") or []))
    metadata_cols[1].metric("Date", record.get("publication_date") or "N/A")
    metadata_cols[2].metric("DOI", record.get("doi") or "N/A")
    license_value = record.get("license")
    if isinstance(license_value, dict):
        license_value = license_value.get("id")
    metadata_cols[3].metric("License", license_value or "N/A")

    if record.get("source_url"):
        st.link_button("Open Zenodo record", record["source_url"])

    st.markdown("#### Description")
    st.write(clean_text(record.get("description")) or record.get("summary") or "No description is available.")

    st.markdown("#### Keywords")
    render_chip_row([str(keyword) for keyword in record.get("keywords", []) if keyword], limit=20)

    files = record.get("files") or []
    if files:
        st.markdown("#### Files")
        st.dataframe(
            [
                {
                    "file_name": file.get("file_name"),
                    "size_bytes": file.get("size_bytes"),
                    "checksum": file.get("checksum"),
                    "file_url": file.get("file_url"),
                }
                for file in files
            ],
            use_container_width=True,
            hide_index=True,
        )

    if st.button("Register this Zenodo record", key="register_selected_zenodo"):
        try:
            result = api_post("/zenodo/register", {"record": record})
            st.success("Zenodo record registered")
            st.json(result)
        except Exception as exc:
            st.error(f"Registration failed: {exc}")


def render_discover_from_zenodo() -> None:
    st.header("Discover QEC-related Datasets from Zenodo")

    selected_record = st.session_state.get("selected_zenodo_record")
    if selected_record:
        render_zenodo_detail(selected_record)
        return

    # query = st.text_input("Search query 👇", 
    #                     value=st.session_state.get("zenodo_query", "quantum error correction dataset"),
    #                     label_visibility="visible",
    #                     disabled=False,
    #                     placeholder=st.session_state.placeholder,
    #                     )
    query = st.text_input(
        "Search query 👇",
        value="",
        placeholder="Try: quantum error correction dataset",
        # key="zenodo_query",
)
    
    

    if st.button("Search Zenodo", type="primary"):
        st.session_state["zenodo_query"] = query
        st.session_state["zenodo_size"] = ZENODO_PAGE_SIZE
        st.session_state["selected_zenodo_record"] = None
        try:
            st.session_state["zenodo_results"] = search_zenodo(query, ZENODO_PAGE_SIZE)
        except Exception as exc:
            st.error(f"Zenodo search failed: {exc}")

    results = st.session_state.get("zenodo_results", [])
    if not results:
        st.info("Search Zenodo to see dataset candidates.")
        return

    st.caption(f"Showing {len(results)} result(s). Search loads 20 records first; Load more adds 20 more.")
    for idx, record in enumerate(results):
        render_zenodo_card(record, idx)

    if st.button("Load more", use_container_width=True):
        next_size = st.session_state.get("zenodo_size", ZENODO_PAGE_SIZE) + ZENODO_PAGE_SIZE
        try:
            st.session_state["zenodo_results"] = search_zenodo(st.session_state.get("zenodo_query", query), next_size)
            st.session_state["zenodo_size"] = next_size
            st.rerun()
        except Exception as exc:
            st.error(f"Failed to load more Zenodo records: {exc}")


render_sidebar_chatbot()
page = render_page_nav()

if page == "Browse Registry":
    render_browse_registry()
elif page == "Register Internal Parquet":
    render_register_internal_parquet()
elif page == "Discover from Zenodo":
    render_discover_from_zenodo()
