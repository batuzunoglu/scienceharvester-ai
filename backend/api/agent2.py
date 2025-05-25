# backend/api/agent2.py
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
import os
import shutil
import json
import asyncio
from typing import List

from agent2_module import process_single_pdf_async, sanitize_doi_for_filename
# MODIFIED: Import get_project_data_paths
from .projects import get_project_data_paths # Assuming projects.py is in the same 'api' directory

router = APIRouter()

# MODIFIED: Global temporary directory for uploads
AGENT2_TEMP_INPUT_PDFS_DIR = "agent2_temp_input_pdfs"
os.makedirs(AGENT2_TEMP_INPUT_PDFS_DIR, exist_ok=True)

# AGENT2_OUTPUT_DIR is no longer needed here, will be project-specific
# AGENT1_METADATA_FILE is no longer needed here, will be project-specific

async def save_upload_file(upload_file: UploadFile, destination: str) -> None:
    try:
        os.makedirs(os.path.dirname(destination), exist_ok=True) # Ensure parent dir exists
        with open(destination, "wb") as buffer:
            await asyncio.to_thread(shutil.copyfileobj, upload_file.file, buffer)
    finally:
        await upload_file.close()


@router.post("/extract")
async def extract_pdfs_concurrently(
    project_id: str = Form(...), # Changed from projectId to project_id for consistency
    pdfs: List[UploadFile] = File(...),
):
    print(f"[Agent2 Server] Received /extract request for project_id: {project_id} with {len(pdfs)} PDF(s).")
    
    project_specific_paths = {}
    agent1_metadata_path = ""
    agent2_output_dir_for_project = ""

    try:
        project_specific_paths = get_project_data_paths(project_id)
        agent1_metadata_path = project_specific_paths["agent1_metadata_file"]
        agent2_output_dir_for_project = project_specific_paths["agent2_extractions_dir"]
        os.makedirs(agent2_output_dir_for_project, exist_ok=True) # Ensure project-specific output dir exists
        print(f"    [Agent2 Server] Agent1 metadata path for project {project_id}: {agent1_metadata_path}")
        print(f"    [Agent2 Server] Agent2 output dir for project {project_id}: {agent2_output_dir_for_project}")
    except ValueError as e:
        print(f"    [Agent2 Server] Error getting project paths for {project_id}: {e}")
        raise HTTPException(status_code=404, detail=f"Project configuration error: {str(e)}")
    except Exception as e:
        print(f"    [Agent2 Server] Unexpected error setting up paths for {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during path setup.")

    agent1_full_metadata = None
    if os.path.exists(agent1_metadata_path):
        try:
            with open(agent1_metadata_path, "r", encoding="utf-8") as f:
                agent1_full_metadata = json.load(f)
            print(f"    [Agent2 Server] Agent1 metadata loaded successfully for project {project_id}.")
        except Exception as e:
            print(f"    [Agent2 Server] Error loading Agent1 metadata from {agent1_metadata_path}: {e}.")
    else:
        print(f"    [Agent2 Server] Warning: Agent1 metadata file not found at {agent1_metadata_path} for project {project_id}.")

    temp_pdf_info = [] 
    processing_tasks = []

    for pdf_upload_file in pdfs:
        if not pdf_upload_file.filename:
            print(f"    [Agent2 Server] Skipping a file without a filename.")
            continue
        
        # Use the global temp directory for initial save
        temp_pdf_path = os.path.join(AGENT2_TEMP_INPUT_PDFS_DIR, f"{project_id}_{pdf_upload_file.filename}")
        
        try:
            await save_upload_file(pdf_upload_file, temp_pdf_path)
            temp_pdf_info.append({"path": temp_pdf_path, "original_filename": pdf_upload_file.filename})
        except Exception as e:
            print(f"    [Agent2 Server] Failed to save {pdf_upload_file.filename}: {e}")
            processing_tasks.append( # Pre-failed task
                asyncio.create_task(
                    asyncio.sleep(0, result={"filename": pdf_upload_file.filename, "error": f"Failed to save file: {e}"})
                )
            )

    for pdf_info in temp_pdf_info:
        pdf_path = pdf_info["path"]
        original_filename = pdf_info["original_filename"]
        current_paper_agent1_meta = None

        if agent1_full_metadata and "papers" in agent1_full_metadata:
            for paper_meta in agent1_full_metadata["papers"]:
                # Match by suggested_filename (often DOI-based) or original title if available
                # This matching logic might need to be very robust depending on Agent1's output and user uploads
                sf = paper_meta.get("suggested_filename")
                # Assuming original_filename uploaded by user might directly match suggested_filename
                if sf and sf.lower() == original_filename.lower():
                    current_paper_agent1_meta = paper_meta
                    break
                # Fallback: try to match based on title if suggested_filename doesn't match
                # This is less reliable due to potential variations in titles.
                # A better strategy would be for the user to somehow link uploads to Agent1 papers on the frontend.
                if paper_meta.get("title") and paper_meta.get("title", "").strip().lower() in original_filename.lower().replace(".pdf",""):
                     if not current_paper_agent1_meta: # Prioritize suggested_filename match
                        current_paper_agent1_meta = paper_meta
                        # break #  don't break, keep looking for suggested_filename match
            
            if current_paper_agent1_meta:
                 print(f"    [Agent2 Server] Found Agent1 metadata for {original_filename} based on title/suggested_filename.")
            else:
                 print(f"    [Agent2 Server] No specific Agent1 metadata found for {original_filename}.")


        task = process_single_pdf_async(
            pdf_path=pdf_path,
            agent1_paper_metadata=current_paper_agent1_meta # Pass the specific paper's metadata
        )
        processing_tasks.append(task)

    all_results = []
    if processing_tasks: # Only run gather if there are tasks
        print(f"[Agent2 Server] Starting concurrent processing of {len(temp_pdf_info)} successfully saved PDFs.")
        # Filter out pre-failed tasks from gather, handle them separately
        tasks_for_gather = [t for t in processing_tasks if not (hasattr(t, '_coro') and isinstance(t._coro, asyncio.coroutines.coroutine) and t._coro.cr_code.co_name == 'sleep')]
        pre_failed_results = [t.result() for t in processing_tasks if hasattr(t, '_coro') and isinstance(t._coro, asyncio.coroutines.coroutine) and t._coro.cr_code.co_name == 'sleep']

        gathered_results = []
        if tasks_for_gather:
             gathered_results = await asyncio.gather(*tasks_for_gather, return_exceptions=True)
        
        all_results.extend(pre_failed_results)
        all_results.extend(gathered_results)

    print(f"[Agent2 Server] Finished concurrent processing.")

    final_extractions = []
    # Need to map results back to original filenames if gather shuffles them or if exceptions occur
    # Iterate through temp_pdf_info to maintain order and associate results
    
    result_idx = 0 # To iterate through 'gathered_results'
    for pdf_item_info in temp_pdf_info: # Iterate through successfully saved files
        original_fn = pdf_item_info["original_filename"]
        # Find its corresponding result in all_results
        # This mapping assumes that results from asyncio.gather maintain the order of input tasks.
        # And pre-failed tasks are handled first.
        # Let's refine this to be more robust if we added pre-failed tasks
        
        # A simpler way: Iterate through all_results and try to match back if needed,
        # or assume `gathered_results` corresponds to `temp_pdf_info` items that were not pre-failed.
        
        # This part needs careful handling of results vs exceptions
        if result_idx < len(all_results): # Make sure we don't go out of bounds
            res_or_exc = all_results[result_idx] # This assumes order is maintained
            
            current_extraction_result = {}
            if isinstance(res_or_exc, Exception):
                print(f"    [Agent2 Server] Exception for task processing {original_fn}: {res_or_exc}")
                current_extraction_result = {
                    "filename": original_fn,
                    "error": f"An unexpected error occurred during processing: {str(res_or_exc)}",
                    "technical_features": [],
                    "qualitative_insights": {}
                }
            elif isinstance(res_or_exc, dict) and "error" in res_or_exc and "filename" not in res_or_exc : # Error from process_single_pdf
                # This case should be covered by process_single_pdf_async returning a dict with filename
                 current_extraction_result = { "filename": original_fn, **res_or_exc}
            elif isinstance(res_or_exc, dict) and "filename" in res_or_exc: # Properly formed result
                current_extraction_result = res_or_exc
                # Ensure original_filename from upload is used if process_single_pdf_async might change it
                current_extraction_result["filename"] = original_fn 
            else: # Malformed result
                print(f"    [Agent2 Server] Malformed result for {original_fn}: {res_or_exc}")
                current_extraction_result = {
                    "filename": original_fn,
                    "error": "Malformed result from processing.",
                    "technical_features": [],
                    "qualitative_insights": {}
                }
            
            final_extractions.append(current_extraction_result)

            if not current_extraction_result.get("error"):
                # Determine output filename based on DOI or original filename
                output_basename_for_json = original_fn.lower().replace(".pdf", "")
                
                # Try to find the matched Agent1 metadata again for consistent naming
                # This is slightly redundant but ensures correct DOI is used for output filename
                final_agent1_meta_match = None
                if agent1_full_metadata and "papers" in agent1_full_metadata:
                    for paper_meta in agent1_full_metadata["papers"]:
                        sf = paper_meta.get("suggested_filename")
                        if sf and sf.lower() == original_fn.lower():
                            final_agent1_meta_match = paper_meta; break
                        if paper_meta.get("title","").strip().lower() in original_fn.lower().replace(".pdf",""):
                            if not final_agent1_meta_match: final_agent1_meta_match = paper_meta

                if final_agent1_meta_match and final_agent1_meta_match.get("doi"):
                    output_basename_for_json = sanitize_doi_for_filename(final_agent1_meta_match.get("doi"))
                else:
                    output_basename_for_json = sanitize_doi_for_filename(output_basename_for_json) # Sanitize original name

                output_json_path = os.path.join(agent2_output_dir_for_project, f"{output_basename_for_json}_extraction.json")
                try:
                    print(f"    [Agent2 Server] Saving extraction for {original_fn} to {output_json_path}")
                    with open(output_json_path, "w", encoding="utf-8") as f:
                        json.dump(current_extraction_result, f, indent=2, ensure_ascii=False)
                except Exception as e:
                    print(f"    [Agent2 Server] Warning: could not write extraction JSON for {original_fn} to {output_json_path}: {e}")
                    current_extraction_result["warning_saving_extraction"] = str(e)
            
            result_idx += 1
        else:
            # This case means a PDF was saved but somehow didn't get a result from gather. Should be rare.
             print(f"    [Agent2 Server] No result found for {original_fn} in gathered results.")
             final_extractions.append({
                "filename": original_fn,
                "error": "Processing did not yield a result for this file.",
                "technical_features": [], "qualitative_insights": {}
            })


    # Handle pre-failed tasks (save errors) if they were separated
    # The current logic already appends them to processing_tasks and then to all_results
    # So they should be covered. If not, explicitly add them here.

    print(f"[Agent2 Server] Cleaning up temporary PDF files from {AGENT2_TEMP_INPUT_PDFS_DIR}...")
    for pdf_info_to_clean in temp_pdf_info:
        try:
            if os.path.exists(pdf_info_to_clean["path"]):
                os.remove(pdf_info_to_clean["path"])
                print(f"    [Agent2 Server] Removed temp file: {pdf_info_to_clean['path']}")
        except Exception as e:
            print(f"    [Agent2 Server] Error removing temp file {pdf_info_to_clean['path']}: {e}")

    print(f"[Agent2 Server] Sending response with {len(final_extractions)} extraction results.")
    return JSONResponse(content={"extractions": final_extractions})