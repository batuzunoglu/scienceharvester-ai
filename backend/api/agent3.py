# backend/api/agent3.py
from __future__ import annotations # For type hints

import asyncio
import json
import os
import pathlib
import re
import traceback # For detailed error logging
from typing import Tuple, List, Dict, Any, Optional

import aiofiles # For async file operations
from fastapi import APIRouter, Form, Query, HTTPException, Request
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
# Removed OpenAI import as _llm_call_async is now in agent3_module

# MODIFIED: Import project utilities
from .projects import get_project_data_paths, _projects, save_projects_to_db
# MODIFIED: Import Agent3 module functions
from agent3_module import create_comprehensive_report_async, md_to_pdf_async # Removed generate_report_markdown_async as it's part of create_comprehensive_report_async

router = APIRouter()

# --- Configuration & Constants (can be removed if defined in agent3_module and not directly used here) ---
# YOUR_PERPLEXITY_API_KEY, AGENT1_METADATA_FILE, AGENT2_EXTRACTIONS_DIR, REPORTS_OUTPUT_DIR
# MATERIAL_KEYWORDS, etc. are used by synthesize_data_for_report_prompt in the module.

# --- API Endpoints ---
@router.get("/report/stream")
async def stream_report_md_endpoint(project_id: str = Query(..., min_length=1)):
    print(f"[Agent3 API /report/stream] Request for project_id: '{project_id}'")

    try:
        paths = get_project_data_paths(project_id)
        agent1_meta_path = paths["agent1_metadata_file"]
        agent2_extract_dir = paths["agent2_extractions_dir"]
        agent3_reports_dir = paths["agent3_reports_dir"] 
        os.makedirs(agent3_reports_dir, exist_ok=True) 
    except ValueError as e: 
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        print(f"[Agent3 API /report/stream] Error setting up paths for {project_id}: {e}\n{traceback.format_exc()}") # Add traceback
        raise HTTPException(status_code=500, detail=f"Server error setting up paths: {str(e)}")

    async def event_generator():
        # This is the "Corrected structure" that should work.
        # The nested report_task and asyncio.create_task(report_task()) was the issue.
        try:
            yield "data: ⏳ Initializing report generation...\n\n"
            await asyncio.sleep(0.1) # Allow client to receive initial message

            # Directly call and await the function that does the work
            markdown_content, md_filepath, error_message = await create_comprehensive_report_async(
                project_id=project_id,
                agent1_metadata_path=agent1_meta_path,
                agent2_extractions_path_for_project=agent2_extract_dir,
                reports_output_path_for_project=agent3_reports_dir
            )
            # await asyncio.sleep(0.1) # Optional small delay

            if error_message:
                print(f"[Agent3 API Stream] Error from report generation for {project_id}: {error_message}")
                yield f"data: __ERROR__{error_message}\n\n"
            elif markdown_content and md_filepath:
                # Update project metadata
                if project_id in _projects:
                    _projects[project_id]["agent3_report_md_file"] = md_filepath
                    # save_projects_to_db is synchronous, run in thread
                    await asyncio.to_thread(save_projects_to_db) 
                    print(f"[Agent3 API Stream] Updated project {project_id} with MD report path: {md_filepath}")
                else:
                     print(f"[Agent3 API Stream] Warning: Project {project_id} not found in _projects to update MD path.")
                
                payload = json.dumps({"report_md": markdown_content}) 
                yield f"data: __RESULT__{payload}\n\n"
                yield f"data: ✅ Markdown report generated and saved.\n\n" 
            else: # This case should ideally be covered by error_message
                unknown_error = "Report content or path missing without explicit error after generation."
                print(f"[Agent3 API Stream] Unknown error for {project_id}: {unknown_error}")
                yield f"data: __ERROR__{unknown_error}\n\n"
        except HTTPException as http_exc: # If create_comprehensive_report_async raises an HTTPException
            print(f"[Agent3 API Stream] HTTPException during report generation for {project_id}: {http_exc.detail}")
            yield f"data: __ERROR__{http_exc.detail}\n\n"
        except Exception as exc: # Catch any other unexpected errors
            tb_str = traceback.format_exc()
            print(f"[Agent3 API Stream] Unhandled exception in event_generator for {project_id}: {exc}\n{tb_str}")
            yield f"data: __ERROR__Internal server error during report generation: {str(exc)}\n\n"
        finally:
            print(f"[Agent3 API Stream] Event stream finished for {project_id}")

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@router.post("/report/pdf")
async def download_report_pdf_endpoint(project_id: str = Form(..., min_length=1)):
    print(f"[Agent3 API /report/pdf] Request for project_id: {project_id}")
    
    try:
        paths = get_project_data_paths(project_id)
        agent3_reports_dir = paths["agent3_reports_dir"] # Base dir for this project's reports
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error setting up paths: {str(e)}")

    # Define expected filenames within the project's agent3_reports_dir
    # The actual filename stored in project metadata will be the source of truth after generation.
    # For initial generation, we construct it.
    # Ensure consistent naming with how md_filepath is generated in create_comprehensive_report_async
    # (e.g. using project_id directly in filename)
    report_md_filename = f"{project_id}_report.md"
    report_pdf_filename = f"{project_id}_report.pdf"
    
    md_path_on_server = os.path.join(agent3_reports_dir, report_md_filename)
    pdf_path_on_server = os.path.join(agent3_reports_dir, report_pdf_filename)

    try:
        # Check if PDF already exists (from project metadata if available and reliable, or filesystem)
        if project_id in _projects and _projects[project_id].get("agent3_report_pdf_file"):
            pdf_metadata_path = _projects[project_id]["agent3_report_pdf_file"]
            if await asyncio.to_thread(os.path.exists, pdf_metadata_path):
                print(f"  [Agent3 PDF] PDF path found in metadata and file exists. Serving: {pdf_metadata_path}")
                return FileResponse(pdf_metadata_path, filename=os.path.basename(pdf_metadata_path), media_type="application/pdf")
        
        # Fallback to checking filesystem directly if not in metadata or path is invalid
        if await asyncio.to_thread(os.path.exists, pdf_path_on_server):
            print(f"  [Agent3 PDF] PDF found on filesystem. Serving existing: {pdf_path_on_server}")
            # Update metadata if it was missing
            if project_id in _projects and not _projects[project_id].get("agent3_report_pdf_file"):
                 _projects[project_id]["agent3_report_pdf_file"] = pdf_path_on_server
                 await asyncio.to_thread(save_projects_to_db)
            return FileResponse(pdf_path_on_server, filename=report_pdf_filename, media_type="application/pdf")

        print(f"  [Agent3 PDF] PDF not found at {pdf_path_on_server}. Checking for source MD: {md_path_on_server}")
        
        markdown_content: Optional[str] = None
        if not await asyncio.to_thread(os.path.exists, md_path_on_server):
            print(f"  [Agent3 PDF] MD file ({md_path_on_server}) also not found. Cannot generate PDF.")
            raise HTTPException(status_code=404, detail="Markdown report (source for PDF) not found. Please generate the report first.")
        else:
            async with aiofiles.open(md_path_on_server, "r", encoding="utf-8") as f:
                markdown_content = await f.read()
        
        if not markdown_content or not markdown_content.strip():
             raise HTTPException(status_code=500, detail="Markdown content is empty or invalid. Cannot generate PDF.")

        print(f"  [Agent3 PDF] Generating PDF from markdown for {project_id} (MD length: {len(markdown_content)} chars). Target: {pdf_path_on_server}")
        generated_pdf_filepath = await md_to_pdf_async(markdown_content, pdf_path_on_server)
        
        if generated_pdf_filepath:
            print(f"  [Agent3 PDF] PDF generated successfully: {generated_pdf_filepath}")
            # Update project metadata with the PDF file path
            if project_id in _projects:
                _projects[project_id]["agent3_report_pdf_file"] = generated_pdf_filepath
                # Also ensure MD path is set if it wasn't (though it should be if PDF is generated from it)
                if not _projects[project_id].get("agent3_report_md_file"):
                    _projects[project_id]["agent3_report_md_file"] = md_path_on_server
                await asyncio.to_thread(save_projects_to_db)
                print(f"  [Agent3 PDF] Updated project {project_id} with PDF report path: {generated_pdf_filepath}")
            else:
                print(f"  [Agent3 PDF] Warning: Project {project_id} not found in _projects to update PDF path.")

            return FileResponse(generated_pdf_filepath, filename=report_pdf_filename, media_type="application/pdf")
        else:
            raise HTTPException(status_code=500, detail="PDF generation failed. Check server logs.")
            
    except HTTPException as http_exc:
        raise http_exc
    except Exception as exc:
        tb_str = traceback.format_exc()
        print(f"[Agent3 API /report/pdf] Error for {project_id}: {exc}\n{tb_str}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(exc)}")