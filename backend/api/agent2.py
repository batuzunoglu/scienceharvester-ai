# backend/api/agent2.py
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
import os
import shutil
import json
import asyncio
from typing import List, Dict, Any # Added Dict, Any for better type hinting
import aiofiles # For asynchronous file operations
import traceback # For more detailed error logging

from agent2_module import process_single_pdf_async, sanitize_doi_for_filename
from .projects import get_project_data_paths 

router = APIRouter()

# --- Determine effective paths based on environment ---
IS_ON_VERCEL_AGENT2 = os.getenv("VERCEL_ENV") in ["production", "preview", "development"]

if IS_ON_VERCEL_AGENT2:
    print("INFO (api/agent2.py): Running on Vercel, configuring AGENT2_TEMP_INPUT_PDFS_DIR for /tmp.")
    AGENT2_TEMP_INPUT_PDFS_DIR = "/tmp/agent2_temp_input_pdfs"
else:
    print("INFO (api/agent2.py): Running locally, configuring AGENT2_TEMP_INPUT_PDFS_DIR locally.")
    # Assuming this file (agent2.py) is in backend/api/
    # So, __file__ gives .../backend/api/agent2.py
    # os.path.dirname(__file__) gives .../backend/api/
    # os.path.dirname(os.path.dirname(__file__)) gives .../backend/
    BACKEND_ROOT_DIR_A2 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))       
    AGENT2_TEMP_INPUT_PDFS_DIR = os.path.join(BACKEND_ROOT_DIR_A2, "agent2_temp_input_pdfs")

# Ensure the temporary directory exists
try:
    os.makedirs(AGENT2_TEMP_INPUT_PDFS_DIR, exist_ok=True)
    print(f"INFO (api/agent2.py): AGENT2_TEMP_INPUT_PDFS_DIR ensured at: {AGENT2_TEMP_INPUT_PDFS_DIR}")
except OSError as e:
    # This could be a startup failure if the directory can't be created.
    print(f"CRITICAL ERROR (api/agent2.py): Could not create AGENT2_TEMP_INPUT_PDFS_DIR at {AGENT2_TEMP_INPUT_PDFS_DIR}: {e}")
    # Depending on how critical this is at startup, you might raise an exception.
    # For Vercel, /tmp should always be writable. For local, permissions could be an issue.

async def save_upload_file(upload_file: UploadFile, destination: str) -> None:
    try:
        # Ensure parent directory of the destination file exists (important for nested temp structures if any)
        os.makedirs(os.path.dirname(destination), exist_ok=True) 
        async with aiofiles.open(destination, "wb") as buffer: # Use aiofiles for async write
            content = await upload_file.read() # Read content first
            await buffer.write(content)        # Then write
    except Exception as e:
        print(f"    [Agent2 SaveFile] Error saving {upload_file.filename} to {destination}: {e}")
        raise # Re-raise to be caught by the endpoint
    finally:
        await upload_file.close() # Ensure file is closed


@router.post("/extract")
async def extract_pdfs_concurrently(
    project_id: str = Form(...), 
    pdfs: List[UploadFile] = File(...),
):
    print(f"[Agent2 API] Received /extract for project_id: {project_id}, {len(pdfs)} PDF(s).")
    print(f"    [Agent2 API] Using temp PDF input directory: {AGENT2_TEMP_INPUT_PDFS_DIR}")
    
    agent1_metadata_path = ""
    agent2_output_dir_for_project = ""

    try:
        project_specific_paths = get_project_data_paths(project_id)
        agent1_metadata_path = project_specific_paths["agent1_metadata_file"]
        agent2_output_dir_for_project = project_specific_paths["agent2_extractions_dir"]
        await asyncio.to_thread(os.makedirs, agent2_output_dir_for_project, exist_ok=True)
        # print(f"    [Agent2 API] Agent1 metadata for project {project_id}: {agent1_metadata_path}")
        # print(f"    [Agent2 API] Agent2 output dir for project {project_id}: {agent2_output_dir_for_project}")
    except ValueError as e: # From get_project_data_paths
        raise HTTPException(status_code=404, detail=f"Project configuration error: {str(e)}")
    except Exception as e:
        print(f"    [Agent2 API] Error setting up paths for {project_id}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Internal server error during path setup.")

    agent1_full_metadata: Optional[Dict[str, Any]] = None
    if await asyncio.to_thread(os.path.exists, agent1_metadata_path):
        try:
            async with aiofiles.open(agent1_metadata_path, "r", encoding="utf-8") as f:
                agent1_full_metadata = json.loads(await f.read())
            # print(f"    [Agent2 API] Agent1 metadata loaded successfully for project {project_id}.")
        except Exception as e:
            print(f"    [Agent2 API] Warning: Error loading Agent1 metadata from {agent1_metadata_path}: {e}.")
    # else:
        # print(f"    [Agent2 API] Warning: Agent1 metadata file not found: {agent1_metadata_path}")

    temp_pdf_info_list: List[Dict[str, str]] = [] 
    tasks_for_pdf_processing: List[asyncio.Task] = []
    results_for_failed_saves: List[Dict[str, Any]] = []

    for pdf_upload_file in pdfs:
        if not pdf_upload_file.filename:
            print(f"    [Agent2 API] Skipping a file without a filename.")
            continue
        
        # Create a unique temporary filename, e.g., by prepending project_id or a UUID
        # This helps if AGENT2_TEMP_INPUT_PDFS_DIR is shared or for easier cleanup logging.
        unique_temp_filename = f"{project_id}_{os.urandom(4).hex()}_{pdf_upload_file.filename}"
        temp_pdf_path = os.path.join(AGENT2_TEMP_INPUT_PDFS_DIR, unique_temp_filename)
        
        try:
            await save_upload_file(pdf_upload_file, temp_pdf_path)
            temp_pdf_info_list.append({"path": temp_pdf_path, "original_filename": pdf_upload_file.filename})
        except Exception as e:
            print(f"    [Agent2 API] Failed to save '{pdf_upload_file.filename}' to '{temp_pdf_path}': {e}")
            results_for_failed_saves.append({
                "filename": pdf_upload_file.filename, 
                "error": f"Failed to save uploaded file: {str(e)}",
                "technical_features": [], "qualitative_insights": {} # Ensure full structure
            })

    for pdf_info in temp_pdf_info_list: # Only iterate over successfully saved PDFs
        pdf_path = pdf_info["path"]
        original_filename = pdf_info["original_filename"]
        current_paper_agent1_meta: Optional[Dict[str, Any]] = None

        if agent1_full_metadata and "papers" in agent1_full_metadata:
            for paper_meta in agent1_full_metadata.get("papers", []):
                sf = paper_meta.get("suggested_filename","").lower()
                orig_fn_lower = original_filename.lower()
                # Prioritize suggested_filename match (often DOI based)
                if sf and sf == orig_fn_lower:
                    current_paper_agent1_meta = paper_meta
                    break
                # Fallback to title match (less reliable)
                title_meta = paper_meta.get("title","").strip().lower()
                orig_fn_no_ext_lower = orig_fn_lower.replace(".pdf","")
                if title_meta and title_meta in orig_fn_no_ext_lower:
                     if not current_paper_agent1_meta: # Only if no better match yet
                        current_paper_agent1_meta = paper_meta
            
            # if current_paper_agent1_meta:
            #      print(f"    [Agent2 API] Matched Agent1 metadata for '{original_filename}'")

        task = process_single_pdf_async(
            pdf_path=pdf_path, # This is the path in the temp directory
            agent1_paper_metadata=current_paper_agent1_meta
        )
        tasks_for_pdf_processing.append(task)
    
    processed_results_or_exceptions: List[Any] = []
    if tasks_for_pdf_processing:
        # print(f"    [Agent2 API] Starting concurrent processing of {len(tasks_for_pdf_processing)} PDFs.")
        processed_results_or_exceptions = await asyncio.gather(*tasks_for_pdf_processing, return_exceptions=True)
    
    final_extractions: List[Dict[str, Any]] = list(results_for_failed_saves) 

    # Correlate results with original filenames from temp_pdf_info_list
    for i, result_item in enumerate(processed_results_or_exceptions):
        # `i` here corresponds to the index in `temp_pdf_info_list` because `tasks_for_pdf_processing`
        # was built by iterating over `temp_pdf_info_list`.
        original_fn_for_this_result = temp_pdf_info_list[i]["original_filename"]
            
        current_extraction_output: Dict[str, Any]
        if isinstance(result_item, Exception):
            print(f"    [Agent2 API] Exception during processing task for '{original_fn_for_this_result}': {result_item}")
            current_extraction_output = {
                "filename": original_fn_for_this_result, "error": f"Unexpected processing error: {str(result_item)}",
                "technical_features": [], "qualitative_insights": {}
            }
        elif isinstance(result_item, dict) and "filename" in result_item: # Expected output from process_single_pdf_async
            current_extraction_output = result_item
            # Ensure the top-level filename in the output is the original one provided by the user
            current_extraction_output["filename"] = original_fn_for_this_result 
        else: 
            print(f"    [Agent2 API] Malformed result for '{original_fn_for_this_result}': {result_item}")
            current_extraction_output = {
                "filename": original_fn_for_this_result, "error": "Malformed result from processing task.",
                "technical_features": [], "qualitative_insights": {}
            }
        
        final_extractions.append(current_extraction_output)

        # Save individual extraction JSON if no error in this specific extraction
        if not current_extraction_output.get("error"):
            output_basename_for_json = original_fn_for_this_result.lower().replace(".pdf", "") # Default
            
            # Re-check for Agent1 metadata for naming (could pass this info along with task if preferred)
            # This relies on current_paper_agent1_meta being from the *outer loop* over temp_pdf_info_list
            # which is fragile if indices don't align perfectly.
            # It's safer to re-find it or pass necessary info (like DOI) along with the PDF info.
            # For now, let's assume we can retrieve the meta used for this pdf_info item:
            # The current_paper_agent1_meta used when creating the task for temp_pdf_info_list[i]
            # is the one we need. This is complex to track back perfectly from asyncio.gather.
            # Simpler: use original filename for saving if DOI not easily available here.

            # Let's find the agent1_paper_metadata that was used for this specific pdf_info_list[i]
            # This logic is repeated, consider optimizing if it becomes a bottleneck.
            meta_for_naming: Optional[Dict[str, Any]] = None
            if agent1_full_metadata and "papers" in agent1_full_metadata:
                for paper_m_naming in agent1_full_metadata.get("papers",[]):
                    if paper_m_naming.get("suggested_filename","").lower() == original_fn_for_this_result.lower():
                        meta_for_naming = paper_m_naming
                        break
                    if paper_m_naming.get("title","").strip().lower() in original_fn_for_this_result.lower().replace(".pdf",""):
                        if not meta_for_naming: meta_for_naming = paper_m_naming

            if meta_for_naming and meta_for_naming.get("doi"):
                output_basename_for_json = sanitize_doi_for_filename(meta_for_naming.get("doi"))
            else: 
                output_basename_for_json = sanitize_doi_for_filename(output_basename_for_json) 

            output_json_path = os.path.join(agent2_output_dir_for_project, f"{output_basename_for_json}_extraction.json")
            try:
                # print(f"    [Agent2 API] Saving extraction for '{original_fn_for_this_result}' to '{output_json_path}'")
                async with aiofiles.open(output_json_path, "w", encoding="utf-8") as f_out:
                    await f_out.write(json.dumps(current_extraction_output, indent=2, ensure_ascii=False))
            except Exception as e_save:
                print(f"    [Agent2 API] Warning: could not write extraction JSON for '{original_fn_for_this_result}' to '{output_json_path}': {e_save}")
                current_extraction_output["warning_saving_extraction"] = str(e_save) # Add warning to response

    # print(f"    [Agent2 API] Cleaning up temporary PDF files...")
    for pdf_info_to_clean in temp_pdf_info_list: 
        try:
            temp_file_to_remove = pdf_info_to_clean["path"]
            if await asyncio.to_thread(os.path.exists, temp_file_to_remove):
                await asyncio.to_thread(os.remove, temp_file_to_remove)
                # print(f"    [Agent2 API] Removed temp file: {temp_file_to_remove}")
        except Exception as e_clean:
            print(f"    [Agent2 API] Error removing temp file {pdf_info_to_clean.get('path', 'N/A')}: {e_clean}")

    # print(f"[Agent2 API] Sending response with {len(final_extractions)} extraction results.")
    return JSONResponse(content={"extractions": final_extractions})