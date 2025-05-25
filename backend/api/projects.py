# backend/api/projects.py
from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from uuid import uuid4
import os
import json
import mimetypes 
from typing import Optional, List, Dict
from datetime import datetime # For optional created_at/updated_at timestamps

router = APIRouter()

# --- Determine effective paths based on environment ---
IS_ON_VERCEL = os.getenv("VERCEL_ENV") in ["production", "preview", "development"] # Vercel sets VERCEL_ENV

if IS_ON_VERCEL:
    print("INFO (projects.py): Running on Vercel, using /tmp for data storage.")
    # On Vercel, all writable paths must be under /tmp
    VERCEL_TMP_DIR = "/tmp"
    EFFECTIVE_PROJECTS_DB_FILE = os.path.join(VERCEL_TMP_DIR, "projects_db.json")
    EFFECTIVE_BASE_PROJECT_DATA_DIR = os.path.join(VERCEL_TMP_DIR, "project_data")
else:
    print("INFO (projects.py): Running locally, using local project directory for data.")
    # Local development paths (relative to where backend/main.py is run, typically project root if backend is a module)
    # If projects.py is in backend/api/, and main.py is in backend/, these paths are relative to backend/
    # For robustness, let's make them relative to the projects.py file's directory
    CURRENT_MODULE_DIR = os.path.dirname(os.path.abspath(__file__)) # api/
    BACKEND_ROOT_DIR = os.path.dirname(CURRENT_MODULE_DIR)           # backend/
    
    EFFECTIVE_PROJECTS_DB_FILE = os.path.join(BACKEND_ROOT_DIR, "projects_db.json")
    EFFECTIVE_BASE_PROJECT_DATA_DIR = os.path.join(BACKEND_ROOT_DIR, "project_data")

_projects: Dict[str, Dict] = {} 

# --- Ensure base directories exist ---
try:
    # Ensure the directory for projects_db.json exists
    os.makedirs(os.path.dirname(EFFECTIVE_PROJECTS_DB_FILE), exist_ok=True)
    # Ensure the base project data directory exists
    os.makedirs(EFFECTIVE_BASE_PROJECT_DATA_DIR, exist_ok=True)
    print(f"INFO (projects.py): Effective projects DB path: {EFFECTIVE_PROJECTS_DB_FILE}")
    print(f"INFO (projects.py): Effective base project data path: {EFFECTIVE_BASE_PROJECT_DATA_DIR}")
except OSError as e:
    # This would be a critical failure, especially on Vercel if /tmp is somehow not writable at this stage
    print(f"CRITICAL ERROR (projects.py): Could not create base directories. DB: {os.path.dirname(EFFECTIVE_PROJECTS_DB_FILE)}, Data: {EFFECTIVE_BASE_PROJECT_DATA_DIR}. Error: {e}")
    # Depending on severity, you might raise an exception here to halt app startup
    # For now, we'll let it proceed and fail later if these dirs are crucial.

def load_projects_from_db():
    global _projects
    if os.path.exists(EFFECTIVE_PROJECTS_DB_FILE):
        try:
            with open(EFFECTIVE_PROJECTS_DB_FILE, "r", encoding="utf-8") as f:
                _projects = json.load(f)
            print(f"Loaded {len(_projects)} projects from {EFFECTIVE_PROJECTS_DB_FILE}")
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from {EFFECTIVE_PROJECTS_DB_FILE}: {e}. Starting with an empty project store.")
            _projects = {}
        except Exception as e:
            print(f"Error loading projects from {EFFECTIVE_PROJECTS_DB_FILE}: {e}. Starting fresh.")
            _projects = {}
    else:
        print(f"Project DB file {EFFECTIVE_PROJECTS_DB_FILE} not found. Starting with empty project store.")
        _projects = {}

def save_projects_to_db():
    try:
        # Ensure directory for DB file exists, especially for /tmp which might be cleared
        os.makedirs(os.path.dirname(EFFECTIVE_PROJECTS_DB_FILE), exist_ok=True)
        with open(EFFECTIVE_PROJECTS_DB_FILE, "w", encoding="utf-8") as f:
            json.dump(_projects, f, indent=2)
        # print(f"Saved {len(_projects)} projects to {EFFECTIVE_PROJECTS_DB_FILE}")
    except Exception as e:
        print(f"Error saving projects to {EFFECTIVE_PROJECTS_DB_FILE}: {e}")

load_projects_from_db()

@router.get("/", summary="List all projects, optionally filtered by user_session_id")
async def list_projects(user_session_id: Optional[str] = Query(None)) -> List[Dict]:
    # print(f"GET /api/projects/ - Received user_session_id: {user_session_id}") # Reduce noise
    # Soft delete is handled by not including deleted projects in _projects or filtering here
    active_projects = [p for p in _projects.values() if not p.get("is_deleted", False)]
    if user_session_id:
        filtered_projects = [p for p in active_projects if p.get("user_session_id") == user_session_id]
        # print(f"GET /api/projects/ - Filtering for '{user_session_id}', found {len(filtered_projects)} projects.")
        return filtered_projects
    else:
        # print(f"GET /api/projects/ - No user_session_id. Returning all {len(active_projects)} projects.")
        return active_projects

@router.post("/", summary="Create a new project")
async def create_project(body: Dict = Body(...)) -> Dict:
    new_id = str(uuid4())
    project_name = body.get("name", "Untitled Project")
    user_session_id = body.get("user_session_id", "anonymous_user")

    print(f"POST /api/projects/ - Creating project '{project_name}' (ID: {new_id}) for user_session_id: {user_session_id}")

    # project_specific_data_dir will now be under EFFECTIVE_BASE_PROJECT_DATA_DIR (e.g., /tmp/project_data/[id] on Vercel)
    project_specific_data_dir = os.path.join(EFFECTIVE_BASE_PROJECT_DATA_DIR, new_id)
    
    agent1_output_path = os.path.join(project_specific_data_dir, "agent1_outputs")
    agent2_extractions_path = os.path.join(project_specific_data_dir, "agent2_extractions")
    agent3_reports_path = os.path.join(project_specific_data_dir, "agent3_reports")

    try:
        # These will create subdirs like /tmp/project_data/[new_id]/agent1_outputs
        os.makedirs(agent1_output_path, exist_ok=True)
        os.makedirs(agent2_extractions_path, exist_ok=True)
        os.makedirs(agent3_reports_path, exist_ok=True)
        print(f"  Created project subdirectories in: {project_specific_data_dir}")
    except OSError as e:
        print(f"  Error creating project directories for {new_id} in {project_specific_data_dir}: {e}")
        raise HTTPException(status_code=500, detail=f"Could not create project storage directories: {e}")

    current_time_iso = datetime.utcnow().isoformat() + "Z" # UTC ISO format
    pj = {
        "id": new_id,
        "name": project_name,
        "user_session_id": user_session_id,
        "data_dir": project_specific_data_dir, 
        "agent1_metadata_file": None, 
        "agent2_extraction_dir": agent2_extractions_path, # This path is already project specific
        "agent3_report_md_file": None, 
        "agent3_report_pdf_file": None,
        "is_deleted": False, # For soft delete
        "created_at": current_time_iso,
        "updated_at": current_time_iso
    }
    _projects[new_id] = pj
    save_projects_to_db()
    print(f"Project {new_id} created and saved. Data dir: {project_specific_data_dir}")
    return pj

@router.get("/{project_id}", summary="Get a specific project's details")
async def get_project_details(project_id: str) -> Dict:
    if project_id not in _projects or _projects[project_id].get("is_deleted", False):
        raise HTTPException(status_code=404, detail="Project not found or has been deleted")
    return _projects[project_id]

@router.put("/{project_id}/data", summary="Update project data paths (e.g., after agent runs)")
async def update_project_data_paths(project_id: str, data_updates: Dict = Body(...)) -> Dict:
    if project_id not in _projects or _projects[project_id].get("is_deleted", False):
        raise HTTPException(status_code=404, detail="Project not found or has been deleted")
    
    # print(f"PUT /api/projects/{project_id}/data - Updating with: {data_updates}")
    valid_keys_to_update = ["agent1_metadata_file", "agent3_report_md_file", "agent3_report_pdf_file", "name"]
    updated = False
    for key, value in data_updates.items():
        if key in valid_keys_to_update:
            _projects[project_id][key] = value
            updated = True
    if updated:
        _projects[project_id]["updated_at"] = datetime.utcnow().isoformat() + "Z"
        save_projects_to_db()
        # print(f"Project {project_id} data paths updated.")
    # else:
        # print(f"No valid data paths provided for update for project {project_id}.")
    return _projects[project_id]


# Soft Delete Endpoint (if you implemented it)
@router.delete("/{project_id}", summary="Soft delete a specific project")
async def delete_project_soft(project_id: str):
    if project_id not in _projects:
        raise HTTPException(status_code=404, detail="Project not found")
    if _projects[project_id].get("is_deleted", False):
        return {"message": f"Project '{_projects[project_id].get('name', project_id)}' was already marked as deleted."}
    
    _projects[project_id]["is_deleted"] = True
    _projects[project_id]["deleted_at"] = datetime.utcnow().isoformat() + "Z"
    _projects[project_id]["updated_at"] = _projects[project_id]["deleted_at"]
    save_projects_to_db()
    print(f"Soft deleted project {project_id}")
    return {"message": f"Project '{_projects[project_id].get('name', project_id)}' marked as deleted successfully."}


# --- Helper function for constructing project-specific paths ---
# This function remains critical. It now gets the base_data_dir_for_project,
# which will be correctly rooted in /tmp on Vercel or ./project_data locally.
def get_project_data_paths(project_id: str) -> Dict[str, str]:
    """Returns a dictionary of essential paths for a given project_id."""
    if project_id not in _projects or _projects[project_id].get("is_deleted", False):
        print(f"ERROR in get_project_data_paths: Project ID '{project_id}' not found or deleted. Current keys: {list(_projects.keys())}")
        raise ValueError(f"Project {project_id} not found or deleted for path generation.")
    
    project_meta = _projects[project_id]
    base_data_dir_for_project = project_meta.get("data_dir") # This path is now correctly /tmp/... or ./project_data/...
    if not base_data_dir_for_project:
        # This should ideally not happen if project creation is robust
        raise ValueError(f"Project {project_id} is missing its base 'data_dir' configuration.")

    # Ensure the base_data_dir_for_project itself exists (important for Vercel's /tmp)
    # This might be redundant if create_project always creates it, but good for safety
    # when other agents call this function before creating their specific subdirs.
    try:
        os.makedirs(base_data_dir_for_project, exist_ok=True)
    except OSError as e:
        # This is a more critical error if the base project data dir can't be ensured.
        print(f"CRITICAL ERROR: Could not ensure base project data directory exists at {base_data_dir_for_project}: {e}")
        raise ValueError(f"Cannot access or create project data directory for {project_id}: {e}")


    return {
        "base_data_dir": base_data_dir_for_project,
        "agent1_metadata_file": os.path.join(base_data_dir_for_project, "agent1_outputs", "agent1_found_papers_metadata.json"),
        "agent2_extractions_dir": os.path.join(base_data_dir_for_project, "agent2_extractions"),
        "agent3_reports_dir": os.path.join(base_data_dir_for_project, "agent3_reports"),
    }


# --- Endpoints for Serving Project-Specific File Contents ---
# These endpoints should now work correctly as they use paths derived from get_project_data_paths
# or from project_meta which now has paths rooted correctly for the environment.

@router.get("/{project_id}/files", summary="Get content of a specific project data file by key")
async def get_project_file_content_by_key(project_id: str, file_key: str = Query(...)):
    project = await get_project_details(project_id) # This will raise 404 if project deleted/not found
    
    file_path_to_serve = project.get(file_key) 

    if not file_path_to_serve or not isinstance(file_path_to_serve, str):
        raise HTTPException(status_code=404, detail=f"File key '{file_key}' not found or path not set for project {project_id}.")

    if not os.path.exists(file_path_to_serve): # This check uses the absolute path
        print(f"File not found on server for key '{file_key}': {file_path_to_serve}")
        raise HTTPException(status_code=404, detail=f"File '{os.path.basename(file_path_to_serve)}' (key: {file_key}) does not exist at specified path.")

    filename = os.path.basename(file_path_to_serve)
    media_type, _ = mimetypes.guess_type(file_path_to_serve)

    if file_key == "agent1_metadata_file":
        try:
            with open(file_path_to_serve, "r", encoding="utf-8") as f:
                content = json.load(f)
            return JSONResponse(content=content)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error reading or parsing Agent 1 metadata: {str(e)}")
            
    elif file_key == "agent3_report_md_file":
        return FileResponse(file_path_to_serve, media_type="text/markdown", filename=filename)
    
    elif file_key == "agent3_report_pdf_file":
        return FileResponse(file_path_to_serve, media_type="application/pdf", filename=filename)

    print(f"Serving file {file_path_to_serve} with media type {media_type}")
    return FileResponse(file_path_to_serve, media_type=media_type or "application/octet-stream", filename=filename)


@router.get("/{project_id}/agent2_extractions", summary="List Agent 2 extraction files")
async def list_agent2_extraction_files(project_id: str) -> Dict[str, List[str]]:
    project = await get_project_details(project_id) # Handles deleted/not found check
    
    try:
        # agent2_dir path comes directly from project metadata, which is now correctly rooted
        agent2_dir = project.get("agent2_extraction_dir")
        if not agent2_dir: # Should have been set at project creation
             raise HTTPException(status_code=500, detail=f"Agent 2 extraction directory not configured for project {project_id}.")

        # Ensure the directory exists before listing (might be first time after project creation)
        # This is important for Vercel's /tmp as it might not persist subdirs unless they contain files.
        # However, if it doesn't exist, it just means no extractions yet.
        if not os.path.isdir(agent2_dir):
            # print(f"Agent 2 extraction directory {agent2_dir} not found or not a directory for project {project_id}. Returning empty list.")
            return {"files": []} 

    except ValueError as e: # From get_project_data_paths if project somehow misses data_dir
        raise HTTPException(status_code=404, detail=str(e))

    try:
        files = [f for f in os.listdir(agent2_dir) if f.endswith("_extraction.json")]
        return {"files": sorted(files)}
    except FileNotFoundError: # If agent2_dir itself doesn't exist
        print(f"Agent 2 extraction directory {agent2_dir} does not exist. Returning empty list.")
        return {"files": []}
    except Exception as e:
        print(f"Error listing Agent 2 extraction files for project {project_id} from {agent2_dir}: {e}")
        raise HTTPException(status_code=500, detail="Error listing Agent 2 extraction files.")

@router.get("/{project_id}/agent2_extractions/{filename}", summary="Get a specific Agent 2 extraction file")
async def get_agent2_extraction_file_content(project_id: str, filename: str):
    project = await get_project_details(project_id) # Handles deleted/not found check
    
    try:
        agent2_dir = project.get("agent2_extraction_dir")
        if not agent2_dir:
             raise HTTPException(status_code=500, detail=f"Agent 2 extraction directory not configured for project {project_id}.")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if not filename.endswith("_extraction.json") or ".." in filename or os.path.sep in filename:
        raise HTTPException(status_code=400, detail="Invalid or disallowed filename.")

    file_path = os.path.join(agent2_dir, filename) # Path is now correctly /tmp/... or ./project_data/...
    
    if not os.path.isfile(file_path): 
        print(f"Agent 2 extraction file not found: {file_path}")
        raise HTTPException(status_code=404, detail="Extraction file not found.")
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = json.load(f)
        return JSONResponse(content=content)
    except Exception as e:
        print(f"Error reading Agent 2 extraction file {file_path}: {e}")
        raise HTTPException(status_code=500, detail=f"Error reading extraction file: {str(e)}")