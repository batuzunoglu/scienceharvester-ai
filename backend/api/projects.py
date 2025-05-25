# backend/api/projects.py
from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from uuid import uuid4
import os
import json
import mimetypes # For guessing content type for file serving
from typing import Optional, List, Dict # Added List, Dict

router = APIRouter()

# --- Simple Project Store ---
PROJECTS_DB_FILE = "projects_db.json"
_projects: Dict[str, Dict] = {} # Explicitly type _projects

# Base directory for all project-specific data
# Ensure this directory exists where your backend runs, or create it manually once.
# The application will create subdirectories per project.
BASE_PROJECT_DATA_DIR = "project_data"
os.makedirs(BASE_PROJECT_DATA_DIR, exist_ok=True)


def load_projects_from_db():
    global _projects
    if os.path.exists(PROJECTS_DB_FILE):
        try:
            with open(PROJECTS_DB_FILE, "r", encoding="utf-8") as f:
                _projects = json.load(f)
            print(f"Loaded {len(_projects)} projects from {PROJECTS_DB_FILE}")
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from {PROJECTS_DB_FILE}: {e}. Starting with an empty project store.")
            _projects = {}
        except Exception as e:
            print(f"Error loading projects from {PROJECTS_DB_FILE}: {e}. Starting fresh.")
            _projects = {}
    else:
        print(f"Project DB file {PROJECTS_DB_FILE} not found. Starting fresh.")
        _projects = {}

def save_projects_to_db():
    try:
        with open(PROJECTS_DB_FILE, "w", encoding="utf-8") as f:
            json.dump(_projects, f, indent=2)
        # print(f"Saved {len(_projects)} projects to {PROJECTS_DB_FILE}") # Can be a bit noisy, enable if needed
    except Exception as e:
        print(f"Error saving projects to {PROJECTS_DB_FILE}: {e}")

# Load projects when the module is imported (app starts)
load_projects_from_db()


@router.get("/", summary="List all projects, optionally filtered by user_session_id")
async def list_projects(user_session_id: Optional[str] = Query(None)) -> List[Dict]:
    print(f"GET /api/projects/ - Received user_session_id: {user_session_id}")
    if user_session_id:
        filtered_projects = [
            p for p in _projects.values() 
            if p.get("user_session_id") == user_session_id
        ]
        print(f"GET /api/projects/ - Filtering for '{user_session_id}', found {len(filtered_projects)} projects.")
        return filtered_projects
    else:
        print(f"GET /api/projects/ - No user_session_id. Returning all {len(list(_projects.values()))} projects.")
        return list(_projects.values())

@router.post("/", summary="Create a new project")
async def create_project(body: Dict = Body(...)) -> Dict:
    new_id = str(uuid4())
    project_name = body.get("name", "Untitled Project")
    user_session_id = body.get("user_session_id", "anonymous_user") # Get from request body

    print(f"POST /api/projects/ - Creating project '{project_name}' (ID: {new_id}) for user_session_id: {user_session_id}")

    project_specific_data_dir = os.path.join(BASE_PROJECT_DATA_DIR, new_id)
    
    # Define subdirectories for project outputs
    agent1_output_path = os.path.join(project_specific_data_dir, "agent1_outputs")
    agent2_extractions_path = os.path.join(project_specific_data_dir, "agent2_extractions")
    agent3_reports_path = os.path.join(project_specific_data_dir, "agent3_reports")

    try:
        os.makedirs(agent1_output_path, exist_ok=True)
        os.makedirs(agent2_extractions_path, exist_ok=True)
        os.makedirs(agent3_reports_path, exist_ok=True)
    except OSError as e:
        print(f"Error creating project directories for {new_id}: {e}")
        raise HTTPException(status_code=500, detail="Could not create project storage directories.")

    pj = {
        "id": new_id,
        "name": project_name,
        "user_session_id": user_session_id,
        "data_dir": project_specific_data_dir, # Base data directory for this project
        "agent1_metadata_file": None, # Will store full path
        "agent2_extraction_dir": agent2_extractions_path, # Full path to dir
        "agent3_report_md_file": None, # Full path
        "agent3_report_pdf_file": None, # Full path
    }
    _projects[new_id] = pj
    save_projects_to_db()
    print(f"Project {new_id} created and saved.")
    return pj

@router.get("/{project_id}", summary="Get a specific project's details")
async def get_project_details(project_id: str) -> Dict:
    if project_id not in _projects:
        raise HTTPException(status_code=404, detail="Project not found")
    return _projects[project_id]

@router.put("/{project_id}/data", summary="Update project data paths (e.g., after agent runs)")
async def update_project_data_paths(project_id: str, data_updates: Dict = Body(...)) -> Dict:
    if project_id not in _projects:
        raise HTTPException(status_code=404, detail="Project not found")
    
    print(f"PUT /api/projects/{project_id}/data - Updating with: {data_updates}")
    # Only allow updating specific keys related to file paths
    valid_keys_to_update = ["agent1_metadata_file", "agent3_report_md_file", "agent3_report_pdf_file"]
    updated = False
    for key, value in data_updates.items():
        if key in valid_keys_to_update:
            _projects[project_id][key] = value
            updated = True
        
    if updated:
        save_projects_to_db()
        print(f"Project {project_id} data paths updated.")
    else:
        print(f"No valid data paths provided for update for project {project_id}.")
        
    return _projects[project_id]

# --- Helper function for constructing project-specific paths ---
def get_project_data_paths(project_id: str) -> Dict[str, str]:
    """Returns a dictionary of essential paths for a given project_id."""
    if project_id not in _projects:
        # This print helps diagnose if get_project_data_paths is called for a non-existent ID
        print(f"ERROR in get_project_data_paths: Project ID '{project_id}' not found in _projects. Current keys: {list(_projects.keys())}")
        raise ValueError(f"Project {project_id} not found for path generation.")
    
    project_meta = _projects[project_id]
    # data_dir should have been set at project creation
    base_data_dir_for_project = project_meta.get("data_dir")
    if not base_data_dir_for_project:
        raise ValueError(f"Project {project_id} is missing its base 'data_dir' configuration.")

    # Construct full paths for common files/dirs
    # The actual filenames for agent1_metadata, agent3_report might vary slightly
    # (e.g., include project_id in filename for extra safety, though dir structure isolates)
    # For now, using fixed basenames within their respective directories.
    return {
        "base_data_dir": base_data_dir_for_project,
        "agent1_metadata_file": os.path.join(base_data_dir_for_project, "agent1_outputs", "agent1_found_papers_metadata.json"),
        "agent2_extractions_dir": os.path.join(base_data_dir_for_project, "agent2_extractions"),
        "agent3_reports_dir": os.path.join(base_data_dir_for_project, "agent3_reports"),
        # Note: Actual report filenames in agent3_reports_dir will be like f"{project_id}_report.md"
    }


# --- Endpoints for Serving Project-Specific File Contents ---

@router.get("/{project_id}/files", summary="Get content of a specific project data file by key")
async def get_project_file_content_by_key(project_id: str, file_key: str = Query(...)):
    if project_id not in _projects:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project_data = _projects[project_id]
    file_path_to_serve = project_data.get(file_key) # e.g., file_key = "agent1_metadata_file"

    if not file_path_to_serve or not isinstance(file_path_to_serve, str):
        raise HTTPException(status_code=404, detail=f"File key '{file_key}' not found or path not set for project {project_id}.")

    if not os.path.exists(file_path_to_serve):
        print(f"File not found on server for key '{file_key}': {file_path_to_serve}")
        raise HTTPException(status_code=404, detail=f"File '{os.path.basename(file_path_to_serve)}' (for key: {file_key}) does not exist.")

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

    # Fallback for other types if any (or could raise 400 Bad Request for unsupported file_key)
    print(f"Serving file {file_path_to_serve} with media type {media_type}")
    return FileResponse(file_path_to_serve, media_type=media_type or "application/octet-stream", filename=filename)


@router.get("/{project_id}/agent2_extractions", summary="List Agent 2 extraction files")
async def list_agent2_extraction_files(project_id: str) -> Dict[str, List[str]]:
    if project_id not in _projects:
        raise HTTPException(status_code=404, detail="Project not found")
    
    try:
        project_paths = get_project_data_paths(project_id) # Ensures project and data_dir exist
        agent2_dir = project_paths["agent2_extractions_dir"]
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if not os.path.isdir(agent2_dir):
        # This state should ideally not occur if create_project works correctly
        print(f"Agent 2 extraction directory not found for project {project_id} at {agent2_dir}")
        return {"files": []} 

    try:
        files = [f for f in os.listdir(agent2_dir) if f.endswith("_extraction.json")]
        return {"files": sorted(files)}
    except Exception as e:
        print(f"Error listing Agent 2 extraction files for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Error listing Agent 2 extraction files.")

@router.get("/{project_id}/agent2_extractions/{filename}", summary="Get a specific Agent 2 extraction file")
async def get_agent2_extraction_file_content(project_id: str, filename: str):
    if project_id not in _projects:
        raise HTTPException(status_code=404, detail="Project not found")
    
    try:
        project_paths = get_project_data_paths(project_id)
        agent2_dir = project_paths["agent2_extractions_dir"]
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Basic security: prevent path traversal and ensure it's an extraction file
    if not filename.endswith("_extraction.json") or ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="Invalid or disallowed filename.")

    file_path = os.path.join(agent2_dir, filename)
    if not os.path.isfile(file_path): # More specific check than os.path.exists
        print(f"Agent 2 extraction file not found: {file_path}")
        raise HTTPException(status_code=404, detail="Extraction file not found.")
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = json.load(f)
        return JSONResponse(content=content)
    except Exception as e:
        print(f"Error reading Agent 2 extraction file {file_path}: {e}")
        raise HTTPException(status_code=500, detail=f"Error reading extraction file: {str(e)}")