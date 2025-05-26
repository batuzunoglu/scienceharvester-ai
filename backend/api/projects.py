# backend/api/projects.py
from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from uuid import uuid4
import os
import json
import mimetypes
from typing import Optional, List, Dict
from datetime import datetime

router = APIRouter() # No prefix here

# --- Determine effective paths based on environment ---
IS_ON_VERCEL = os.getenv("VERCEL_ENV") in ["production", "preview", "development"]

if IS_ON_VERCEL:
    print("INFO (projects.py): Running on Vercel, using /tmp for data storage.")
    VERCEL_TMP_DIR = "/tmp"
    EFFECTIVE_PROJECTS_DB_FILE = os.path.join(VERCEL_TMP_DIR, "projects_db.json")
    EFFECTIVE_BASE_PROJECT_DATA_DIR = os.path.join(VERCEL_TMP_DIR, "project_data")
else:
    print("INFO (projects.py): Running locally, using local project directory for data.")
    CURRENT_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
    BACKEND_ROOT_DIR = os.path.dirname(CURRENT_MODULE_DIR)
    EFFECTIVE_PROJECTS_DB_FILE = os.path.join(BACKEND_ROOT_DIR, "projects_db.json")
    EFFECTIVE_BASE_PROJECT_DATA_DIR = os.path.join(BACKEND_ROOT_DIR, "project_data")

_projects: Dict[str, Dict] = {}

try:
    os.makedirs(os.path.dirname(EFFECTIVE_PROJECTS_DB_FILE), exist_ok=True)
    os.makedirs(EFFECTIVE_BASE_PROJECT_DATA_DIR, exist_ok=True)
    print(f"INFO (projects.py): Effective projects DB path: {EFFECTIVE_PROJECTS_DB_FILE}")
    print(f"INFO (projects.py): Effective base project data path: {EFFECTIVE_BASE_PROJECT_DATA_DIR}")
except OSError as e:
    print(f"CRITICAL ERROR (projects.py): Could not create base directories. Error: {e}")

def load_projects_from_db():
    global _projects
    if os.path.exists(EFFECTIVE_PROJECTS_DB_FILE):
        try:
            with open(EFFECTIVE_PROJECTS_DB_FILE, "r", encoding="utf-8") as f:
                _projects = json.load(f)
            print(f"Loaded {len(_projects)} projects from {EFFECTIVE_PROJECTS_DB_FILE}")
        except Exception as e:
            print(f"Error loading/parsing projects from {EFFECTIVE_PROJECTS_DB_FILE}: {e}. Starting fresh.")
            _projects = {}
    else:
        print(f"Project DB file {EFFECTIVE_PROJECTS_DB_FILE} not found. Starting with empty project store.")
        _projects = {}

def save_projects_to_db():
    try:
        os.makedirs(os.path.dirname(EFFECTIVE_PROJECTS_DB_FILE), exist_ok=True)
        with open(EFFECTIVE_PROJECTS_DB_FILE, "w", encoding="utf-8") as f:
            json.dump(_projects, f, indent=2)
    except Exception as e:
        print(f"Error saving projects to {EFFECTIVE_PROJECTS_DB_FILE}: {e}")

load_projects_from_db()

# === Path changes for all endpoints in this router ===
@router.get("/projects", summary="List all projects, optionally filtered by user_session_id")
async def list_projects(user_session_id: Optional[str] = Query(None)) -> List[Dict]:
    active_projects = [p for p in _projects.values() if not p.get("is_deleted", False)]
    if user_session_id:
        return [p for p in active_projects if p.get("user_session_id") == user_session_id]
    return active_projects

@router.post("/projects", summary="Create a new project")
async def create_project(body: Dict = Body(...)) -> Dict:
    new_id = str(uuid4())
    project_name = body.get("name", "Untitled Project")
    user_session_id = body.get("user_session_id", "anonymous_user")
    print(f"POST /api/projects - Creating project '{project_name}' (ID: {new_id}) for user_session_id: {user_session_id}")

    project_specific_data_dir = os.path.join(EFFECTIVE_BASE_PROJECT_DATA_DIR, new_id)
    agent1_output_path = os.path.join(project_specific_data_dir, "agent1_outputs")
    agent2_extractions_path = os.path.join(project_specific_data_dir, "agent2_extractions")
    # Corrected a typo here: agent3_reports_path was using project_specific_data__dir
    agent3_reports_path = os.path.join(project_specific_data_dir, "agent3_reports")
    try:
        os.makedirs(agent1_output_path, exist_ok=True)
        os.makedirs(agent2_extractions_path, exist_ok=True)
        os.makedirs(agent3_reports_path, exist_ok=True)
    except OSError as e:
        print(f"  Error creating project directories for {new_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Could not create project storage: {e}")

    current_time_iso = datetime.utcnow().isoformat() + "Z"
    pj = {
        "id": new_id, "name": project_name, "user_session_id": user_session_id,
        "data_dir": project_specific_data_dir, "agent1_metadata_file": None,
        "agent2_extraction_dir": agent2_extractions_path, "agent3_report_md_file": None,
        "agent3_report_pdf_file": None, "is_deleted": False,
        "created_at": current_time_iso, "updated_at": current_time_iso
    }
    _projects[new_id] = pj
    save_projects_to_db()
    print(f"Project {new_id} created. Data dir: {project_specific_data_dir}")
    return pj

@router.get("/projects/{project_id}", summary="Get a specific project's details")
async def get_project_details_endpoint(project_id: str) -> Dict: # Renamed to avoid conflict if used internally
    if project_id not in _projects or _projects[project_id].get("is_deleted", False):
        raise HTTPException(status_code=404, detail="Project not found or has been deleted")
    return _projects[project_id]

@router.put("/projects/{project_id}/data", summary="Update project data paths")
async def update_project_data_paths(project_id: str, data_updates: Dict = Body(...)) -> Dict:
    project = await get_project_details_endpoint(project_id) # Use the renamed endpoint
    valid_keys_to_update = ["agent1_metadata_file", "agent3_report_md_file", "agent3_report_pdf_file", "name"]
    updated = False
    for key, value in data_updates.items():
        if key in valid_keys_to_update:
            project[key] = value # Update the fetched project dictionary
            updated = True
    if updated:
        project["updated_at"] = datetime.utcnow().isoformat() + "Z"
        _projects[project_id] = project # Save the updated project back to the global store
        save_projects_to_db()
    return project

@router.delete("/projects/{project_id}", summary="Soft delete a specific project")
async def delete_project_soft(project_id: str):
    if project_id not in _projects:
        raise HTTPException(status_code=404, detail="Project not found")
    project = _projects[project_id]
    if project.get("is_deleted", False):
        return {"message": f"Project '{project.get('name', project_id)}' was already marked as deleted."}
    
    project["is_deleted"] = True
    project["deleted_at"] = datetime.utcnow().isoformat() + "Z"
    project["updated_at"] = project["deleted_at"]
    save_projects_to_db()
    print(f"Soft deleted project {project_id}")
    return {"message": f"Project '{project.get('name', project_id)}' marked as deleted."}

def get_project_data_paths(project_id: str) -> Dict[str, str]:
    if project_id not in _projects or _projects[project_id].get("is_deleted", False):
        raise ValueError(f"Project {project_id} not found or deleted for path generation.")
    project_meta = _projects[project_id]
    base_data_dir_for_project = project_meta.get("data_dir")
    if not base_data_dir_for_project:
        raise ValueError(f"Project {project_id} missing 'data_dir' configuration.")
    try:
        os.makedirs(base_data_dir_for_project, exist_ok=True)
    except OSError as e:
        raise ValueError(f"Cannot access/create project data directory for {project_id}: {e}")
    return {
        "base_data_dir": base_data_dir_for_project,
        "agent1_metadata_file": os.path.join(base_data_dir_for_project, "agent1_outputs", "agent1_found_papers_metadata.json"),
        "agent2_extractions_dir": os.path.join(base_data_dir_for_project, "agent2_extractions"),
        "agent3_reports_dir": os.path.join(base_data_dir_for_project, "agent3_reports"),
    }

@router.get("/projects/{project_id}/files", summary="Get content of a specific project data file by key")
async def get_project_file_content_by_key(project_id: str, file_key: str = Query(...)):
    project = await get_project_details_endpoint(project_id)
    file_path_to_serve = project.get(file_key)
    if not file_path_to_serve or not isinstance(file_path_to_serve, str):
        raise HTTPException(status_code=404, detail=f"File key '{file_key}' not found or path not set.")
    if not os.path.exists(file_path_to_serve):
        raise HTTPException(status_code=404, detail=f"File '{os.path.basename(file_path_to_serve)}' does not exist.")
    filename = os.path.basename(file_path_to_serve)
    media_type, _ = mimetypes.guess_type(file_path_to_serve)
    if file_key == "agent1_metadata_file":
        return JSONResponse(content=json.load(open(file_path_to_serve, "r", encoding="utf-8")))
    return FileResponse(file_path_to_serve, media_type=media_type or "application/octet-stream", filename=filename)

@router.get("/projects/{project_id}/agent2_extractions", summary="List Agent 2 extraction files")
async def list_agent2_extraction_files(project_id: str) -> Dict[str, List[str]]:
    project = await get_project_details_endpoint(project_id)
    agent2_dir = project.get("agent2_extraction_dir")
    if not agent2_dir:
         raise HTTPException(status_code=500, detail="Agent 2 directory not configured.")
    if not os.path.isdir(agent2_dir):
        return {"files": []}
    try:
        files = [f for f in os.listdir(agent2_dir) if f.endswith("_extraction.json")]
        return {"files": sorted(files)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing Agent 2 files: {e}")

@router.get("/projects/{project_id}/agent2_extractions/{filename}", summary="Get specific Agent 2 extraction file")
async def get_agent2_extraction_file_content(project_id: str, filename: str):
    project = await get_project_details_endpoint(project_id)
    agent2_dir = project.get("agent2_extraction_dir")
    if not agent2_dir:
         raise HTTPException(status_code=500, detail="Agent 2 directory not configured.")
    if not filename.endswith("_extraction.json") or ".." in filename or os.path.sep in filename:
        raise HTTPException(status_code=400, detail="Invalid filename.")
    file_path = os.path.join(agent2_dir, filename)
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="Extraction file not found.")
    return JSONResponse(content=json.load(open(file_path, "r", encoding="utf-8")))
# =====================================================
