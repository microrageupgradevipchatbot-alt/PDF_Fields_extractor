# app_streamlit_v2.py — Streamlit Frontend (v5)
# ─────────────────────────────────────────────────────────────────────────────
# NEW in v5 — Custom file basket UI:
#   - User adds files one by one (or several at once) via a small uploader
#   - Files accumulate in a "basket" stored in session_state
#   - Each queued file shows a remove ✕ button so user can drop unwanted ones
#   - Hard cap of 5 files total
#   - "Process All Files" button only appears once user has added at least 1 file
#   - Processing + results happen only after that button is clicked
#   - Already-processed files are cached so re-clicking doesn't reprocess them
# ─────────────────────────────────────────────────────────────────────────────

import json
import time
import io
from concurrent.futures import ThreadPoolExecutor

import streamlit as st
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

from app_v2 import extract_fields_ai, flag_missing_fields


# ── PAGE CONFIG ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Service PDF Extractor", layout="centered")
st.markdown("# 📄 Service PDF Extractor — Gemini Vision")
st.markdown("Add PDFs one by one (up to 5), then click **Process All Files**.")
st.markdown("---")


# ── SESSION STATE INIT ────────────────────────────────────────────────────────
# basket        : list of UploadedFile objects the user has queued
# basket_keys   : set of "name_size" strings to detect duplicates
# results       : dict of  cache_key → extracted result
# processing_done: bool — True after Process button was clicked and all ran

if "basket"         not in st.session_state:
    st.session_state.basket          = []
if "basket_keys"    not in st.session_state:
    st.session_state.basket_keys     = set()
if "results"        not in st.session_state:
    st.session_state.results         = {}
if "processing_done" not in st.session_state:
    st.session_state.processing_done = False


# ── CONSTANTS ─────────────────────────────────────────────────────────────────
MAX_FILES       = 5
TIMEOUT_SECONDS = 180


# ── HELPERS ───────────────────────────────────────────────────────────────────
def file_cache_key(f) -> str:
    """Unique key per file = name + size."""
    return f"result_{f.name}_{f.size}"

def basket_id(f) -> str:
    """Short ID used to detect duplicate additions."""
    return f"{f.name}_{f.size}"

def create_pdf_from_text(text: str) -> io.BytesIO:
    """Render a plain-text string into a downloadable PDF buffer."""
    buffer   = io.BytesIO()
    pdf      = canvas.Canvas(buffer, pagesize=letter)
    text_obj = pdf.beginText(40, 750)
    text_obj.setFont("Helvetica", 11)
    for line in text.split("\n"):
        if text_obj.getY() < 40:
            pdf.drawText(text_obj)
            pdf.showPage()
            text_obj = pdf.beginText(40, 750)
            text_obj.setFont("Helvetica", 11)
        text_obj.textLine(line)
    pdf.drawText(text_obj)
    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer

def _render_result(filename: str, result):
    """Display extracted JSON, missing-fields report, and download buttons."""

    # Error
    if isinstance(result, dict) and result.get("error"):
        st.error(f"Extraction failed for **{filename}**")
        st.write(result.get("detail") or result.get("raw") or result)
        return

    if not result:
        st.warning(f"No services extracted from **{filename}**.")
        return

    # Success
    num = len(result) if isinstance(result, list) else 1
    st.success(f"{num} service(s) extracted")

    st.subheader("Extracted JSON")
    st.json(result)

    # Missing fields
    if isinstance(result, list):
        missing = flag_missing_fields(result)
        st.subheader("Missing or Incomplete Fields")
        for svc in missing:
            if svc["missing_fields"]:
                st.write(f"**{svc['service_name']}**: " + ", ".join(svc["missing_fields"]))
            else:
                st.write(f"**{svc['service_name']}**: ✅ All fields filled")

    # Downloads
    st.markdown("---")
    json_str  = json.dumps(result, indent=2)
    safe_name = filename.replace(".pdf", "")
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "📥 Download as TXT", data=json_str,
            file_name=f"{safe_name}_extracted.txt",
            mime="text/plain", key=f"dl_txt_{filename}"
        )
    with col2:
        st.download_button(
            "📄 Download as PDF", data=create_pdf_from_text(json_str),
            file_name=f"{safe_name}_extracted.pdf",
            mime="application/pdf", key=f"dl_pdf_{filename}"
        )


# ── SECTION 1: FILE ADDER ─────────────────────────────────────────────────────
# Small uploader — user can click it multiple times to add different files.
# Each new upload is appended to the basket (not replacing the previous ones).

slots_left = MAX_FILES - len(st.session_state.basket)

if slots_left > 0:
    st.subheader("➕ Add Files")
    new_files = st.file_uploader(
        f"Select PDF(s) — {slots_left} slot(s) remaining",
        type=["pdf"],
        accept_multiple_files=True,
        # key changes whenever basket changes so uploader resets after each add
        key=f"uploader_{len(st.session_state.basket)}",
        label_visibility="visible"
    )

    if new_files:
        added = 0
        for f in new_files:
            bid = basket_id(f)
            if len(st.session_state.basket) >= MAX_FILES:
                st.warning(f"Maximum {MAX_FILES} files reached. '{f.name}' was not added.")
                break
            if bid in st.session_state.basket_keys:
                st.info(f"'{f.name}' is already in the queue — skipped.")
                continue
            st.session_state.basket.append(f)
            st.session_state.basket_keys.add(bid)
            added += 1

        if added:
            # Reset processing_done so user can re-process after adding new files
            st.session_state.processing_done = False
            st.rerun()   # rerun so uploader resets and basket list refreshes
else:
    st.info(f"Queue is full ({MAX_FILES}/{MAX_FILES} files). Remove a file to add another.")


# ── SECTION 2: QUEUED FILES LIST ──────────────────────────────────────────────
# Shows every file in the basket with a ✕ remove button next to each.

if st.session_state.basket:
    st.subheader(f"📋 Queued Files ({len(st.session_state.basket)}/{MAX_FILES})")

    for i, f in enumerate(list(st.session_state.basket)):
        col_name, col_size, col_btn = st.columns([5, 1.5, 1])

        with col_name:
            # Show a tick if already processed, clock if pending
            already_done = file_cache_key(f) in st.session_state.results
            icon = "✅" if already_done else "🕐"
            st.write(f"{icon}  **{f.name}**")

        with col_size:
            size_kb = round(f.size / 1024, 1)
            st.write(f"{size_kb} KB")

        with col_btn:
            # Each remove button has a unique key based on position + name
            if st.button("✕", key=f"remove_{i}_{f.name}", help=f"Remove {f.name}"):
                st.session_state.basket.pop(i)
                st.session_state.basket_keys.discard(basket_id(f))
                # If this file had a result, clear it too
                st.session_state.results.pop(file_cache_key(f), None)
                st.session_state.processing_done = False
                st.rerun()

    st.markdown("---")


# ── SECTION 3: PROCESS BUTTON ─────────────────────────────────────────────────
# Only shown when there are files in the basket.
# Clicking it sets a flag and reruns — processing happens in Section 4.

if st.session_state.basket:

    # Check how many files still need processing
    unprocessed = [
        f for f in st.session_state.basket
        if file_cache_key(f) not in st.session_state.results
    ]

    if unprocessed:
        btn_label = (
            f"🚀  Process All Files ({len(st.session_state.basket)} total)"
            if not st.session_state.processing_done
            else f"🔄  Process New Files ({len(unprocessed)} remaining)"
        )
        if st.button(btn_label, type="primary", use_container_width=True):
            st.session_state.processing_done = True
            st.rerun()
    else:
        st.success("All files have been processed!")


# ── SECTION 4: PROCESSING + RESULTS ──────────────────────────────────────────
# Runs only after the Process button has been clicked (processing_done = True).
# Each file is processed one at a time with a live progress bar.
# Result appears immediately in its own expander as soon as that file finishes.

if st.session_state.processing_done and st.session_state.basket:

    st.subheader("📊 Results")

    dot_frames = ["·", "··", "···", "····"]

    for pdf_file in st.session_state.basket:
        cache_key = file_cache_key(pdf_file)

        with st.expander(f"📁  {pdf_file.name}", expanded=True):

            # ── Already processed — just render ──────────────────────────────
            if cache_key in st.session_state.results:
                _render_result(pdf_file.name, st.session_state.results[cache_key])

            # ── Needs processing — run with live progress ─────────────────────
            else:
                status_box   = st.empty()
                progress_box = st.empty()
                hint_box     = st.empty()
                start_time   = time.time()
                estimated_max = 90

                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(extract_fields_ai, pdf_file)
                    tick   = 0

                    while not future.done():
                        elapsed = time.time() - start_time
                        dots    = dot_frames[tick % len(dot_frames)]
                        tick   += 1

                        # Hard timeout
                        if elapsed > TIMEOUT_SECONDS:
                            future.cancel()
                            status_box.error(
                                f"Timeout: **{pdf_file.name}** took over "
                                f"{TIMEOUT_SECONDS}s. Try uploading again."
                            )
                            progress_box.empty()
                            hint_box.empty()
                            result = {
                                "error":  "timeout",
                                "detail": f"No response within {TIMEOUT_SECONDS}s."
                            }
                            break

                        pct = min(int((elapsed / estimated_max) * 100), 95)
                        status_box.info(f"Processing **{pdf_file.name}** {dots}")
                        progress_box.progress(pct, text=f"{pct}%  |  {int(elapsed)}s elapsed")

                        if elapsed < 10:
                            hint_box.caption(f"Step 1/3: Reading PDF content {dots}")
                        elif elapsed < 35:
                            hint_box.caption(f"Step 2/3: Extracting services and pricing {dots}")
                        else:
                            hint_box.caption(f"Step 3/3: Validating and preparing output {dots}")

                        time.sleep(0.4)
                    else:
                        # Loop ended normally (future.done() became True)
                        try:
                            result = future.result()
                        except Exception as e:
                            result = {"error": "exception", "detail": str(e)}

                total = time.time() - start_time
                status_box.success(f"Done: **{pdf_file.name}** in {total:.1f}s")
                progress_box.progress(100, text="100% — Complete")
                hint_box.empty()

                # Cache and render
                st.session_state.results[cache_key] = result
                _render_result(pdf_file.name, result)
