import json
import streamlit as st
from app_v2 import extract_fields_ai

st.set_page_config(page_title="PDF Extractor + Verification", layout="centered")

st.title("📄 PDF Extractor with Verification")

# ─────────────────────────────────────────────
# Session Init
# ─────────────────────────────────────────────

if "results" not in st.session_state:
    st.session_state.results = {}

if "processed_files" not in st.session_state:
    st.session_state.processed_files = set()

if "staged_files" not in st.session_state:
    st.session_state.staged_files = []   # list of uploaded file objects

if "processing_started" not in st.session_state:
    st.session_state.processing_started = False


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def normalize_result(result):
    if isinstance(result, dict):
        return [result]
    return result


def keyify(path):
    return path.replace(".", "_").replace("[", "_").replace("]", "")


def pretty_label(path):
    label = path.split(".")[-1]
    return label.replace("_", " ").title()


def safe_name(name):
    return name.replace(".", "_").replace(" ", "_")


# ─────────────────────────────────────────────
# UI Components
# ─────────────────────────────────────────────

def render_leaf(path, value):
    key_base = keyify(path)
    label = pretty_label(path)

    col1, col2, col3 = st.columns([2, 4, 1])

    with col1:
        st.markdown(f"**{label}**")

    with col2:
        st.text_input(
            label,
            value if value is not None else "",
            label_visibility="collapsed",
            key=f"value_{key_base}"
        )

    with col3:
        st.checkbox("Verified", key=f"verify_{key_base}", label_visibility="hidden")


def render_pricing(path, pricing_dict):
    st.markdown("### 💰 Pricing")

    for pax, data in pricing_dict.items():
        col1, col2, col3, col4 = st.columns([2, 3, 3, 1])

        with col1:
            st.markdown(f"**{pax.replace('_',' ').title()}**")

        with col2:
            st.text_input(
                "Adults",
                data.get("adults") or "",
                label_visibility="collapsed",
                key=f"value_{path}_{pax}_adults"
            )

        with col3:
            st.text_input(
                "Children",
                data.get("children") or "",
                label_visibility="collapsed",
                key=f"value_{path}_{pax}_children"
            )

        with col4:
            st.checkbox("Verified", key=f"verify_{path}_{pax}", label_visibility="hidden")


# ─────────────────────────────────────────────
# Recursive Renderer
# ─────────────────────────────────────────────

def render_field(path, value):

    if path.endswith("pricing") and isinstance(value, dict):
        render_pricing(path, value)
        return

    if isinstance(value, dict):
        st.markdown(f"### {pretty_label(path)}")
        for k, v in value.items():
            render_field(f"{path}.{k}", v)

    elif isinstance(value, list):
        for i, item in enumerate(value):
            render_field(f"{path}[{i}]", item)

    else:
        render_leaf(path, value)


# ─────────────────────────────────────────────
# Verification
# ─────────────────────────────────────────────

def is_file_verified(file_key):
    keys = [k for k in st.session_state if k.startswith(f"verify_{file_key}")]
    return keys and all(st.session_state[k] for k in keys)


# ─────────────────────────────────────────────
# Rebuild JSON
# ─────────────────────────────────────────────

def rebuild_json(original, path):

    if isinstance(original, dict):
        new_obj = {}

        for k, v in original.items():

            if k == "pricing" and isinstance(v, dict):
                pricing_new = {}

                for pax, data in v.items():
                    pricing_new[pax] = {
                        "adults": st.session_state.get(
                            f"value_{path}.{k}_{pax}_adults",
                            data.get("adults")
                        ),
                        "children": st.session_state.get(
                            f"value_{path}.{k}_{pax}_children",
                            data.get("children")
                        ),
                    }

                new_obj[k] = pricing_new

            else:
                new_obj[k] = rebuild_json(v, f"{path}.{k}")

        return new_obj

    elif isinstance(original, list):
        return [
            rebuild_json(item, f"{path}[{i}]")
            for i, item in enumerate(original)
        ]

    else:
        key_base = keyify(path)
        return st.session_state.get(f"value_{key_base}", original)


# ─────────────────────────────────────────────
# STAGE 1 — File picker with queue management
# ─────────────────────────────────────────────

if not st.session_state.processing_started:

    # File uploader (does NOT auto-process)
    new_files = st.file_uploader(
        "Select PDFs to upload (up to 5)",
        type=["pdf"],
        accept_multiple_files=True,
        key="file_picker"
    )

    # Merge newly picked files into the staged queue (avoid duplicates by name)
    if new_files:
        existing_names = {f.name for f in st.session_state.staged_files}
        for f in new_files:
            if f.name not in existing_names:
                if len(st.session_state.staged_files) >= 5:
                    st.warning("Maximum 5 files allowed. Some files were not added.")
                    break
                st.session_state.staged_files.append(f)
                existing_names.add(f.name)

    # Show the staged queue with remove buttons
    if st.session_state.staged_files:
        st.markdown("### 📋 Files queued for processing")

        to_remove = None
        for idx, f in enumerate(st.session_state.staged_files):
            col_name, col_size, col_btn = st.columns([5, 2, 1])
            with col_name:
                st.markdown(f"📄 **{f.name}**")
            with col_size:
                size_kb = len(f.getvalue()) / 1024
                st.caption(f"{size_kb:.1f} KB")
                f.seek(0)          # reset pointer after getvalue()
            with col_btn:
                if st.button("✕", key=f"remove_{idx}", help=f"Remove {f.name}"):
                    to_remove = idx

        if to_remove is not None:
            st.session_state.staged_files.pop(to_remove)
            st.rerun()

        st.markdown("---")

        col_proceed, col_clear = st.columns([3, 1])
        with col_proceed:
            if st.button(
                f"▶ Proceed — extract {len(st.session_state.staged_files)} file(s)",
                type="primary",
                use_container_width=True
            ):
                st.session_state.processing_started = True
                st.rerun()
        with col_clear:
            if st.button("🗑 Clear all", use_container_width=True):
                st.session_state.staged_files = []
                st.rerun()

    else:
        st.info("Select one or more PDF files above, then click **Proceed** to start extraction.")


# ─────────────────────────────────────────────
# STAGE 2 — Sequential processing (one file per rerun)
# ─────────────────────────────────────────────

if st.session_state.processing_started and st.session_state.staged_files:

    pending = [
        f for f in st.session_state.staged_files
        if safe_name(f.name) not in st.session_state.processed_files
    ]

    if pending:
        total = len(st.session_state.staged_files)
        done  = total - len(pending)
        next_file = pending[0]
        st.info(f"⏳ Processing file {done + 1} of {total}: **{next_file.name}**")

        with st.spinner(f"Extracting data from {next_file.name}…"):
            result = extract_fields_ai(next_file)
            fname  = safe_name(next_file.name)
            st.session_state.results[fname] = {
                "original_name": next_file.name,
                "data": result
            }
            st.session_state.processed_files.add(fname)

        st.rerun()


# ─────────────────────────────────────────────
# STAGE 3 — Display results
# ─────────────────────────────────────────────

for fname, payload in st.session_state.results.items():

    file_display = payload["original_name"]
    result       = payload["data"]

    st.markdown(f"# 📁 {file_display}")

    if isinstance(result, dict) and result.get("error"):
        st.error("Extraction failed")
        st.write(result)
        continue

    services = normalize_result(result)

    # ── Raw extraction download (always available) ──────────────────────────
    raw_json_str = json.dumps(services, indent=2)
    st.download_button(
        label="📥 Download raw extracted JSON",
        data=raw_json_str,
        file_name=f"{fname}_raw.json",
        mime="application/json",
        key=f"download_raw_{fname}"
    )

    # ── Per-service editable fields ─────────────────────────────────────────
    for i, svc in enumerate(services):
        idx = i + 1
        with st.expander(f"Service {idx}", expanded=False):
            render_field(f"{fname}_service_{idx}", svc)

    st.markdown("---")

    # ── Verified download ───────────────────────────────────────────────────
    if not is_file_verified(fname):
        st.warning(f"⚠️ Please verify all fields for {file_display}")
    else:
        st.success(f"✅ {file_display} verified!")

        final_json = [
            rebuild_json(svc, f"{fname}_service_{i+1}")
            for i, svc in enumerate(services)
        ]

        st.json(final_json)

        st.download_button(
            f"📥 Download verified JSON — {file_display}",
            data=json.dumps(final_json, indent=2),
            file_name=f"{fname}_verified.json",
            mime="application/json",
            key=f"download_verified_{fname}"
        )

    st.markdown("-----")


# ─────────────────────────────────────────────
# Reset button (once processing is done or started)
# ─────────────────────────────────────────────

if st.session_state.processing_started:
    st.markdown("---")
    if st.button("🔄 Start over with new files"):
        for key in ["results", "processed_files", "staged_files", "processing_started"]:
            del st.session_state[key]
        st.rerun()
