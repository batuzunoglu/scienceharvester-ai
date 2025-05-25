# backend/api/agent1.py
import os
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json
import asyncio
import literature_harvester
# Assuming your projects.py is in the same 'api' directory or your PYTHONPATH is set up
from .projects import _projects, save_projects_to_db, get_project_data_paths # Using relative import if in same package
# If not in the same package and 'api' is not a package root recognized by Python,
# you might need to adjust your project structure or PYTHONPATH, or use a more absolute path if 'backend' is root.
# For now, let's assume relative import works or you've handled it.
# from api.projects import _projects, save_projects_to_db, get_project_data_paths
import httpx

router = APIRouter()

class HarvestRequest(BaseModel):
    project_id: str # Added for batch endpoint consistency
    topic: str
    dateAfter: str
    dateBefore: str
    maxPapers: int

@router.post("/harvest")
async def harvest(req: HarvestRequest):
    print(f"→ Received /harvest POST request for PID: {req.project_id}, Topic: {req.topic}, Max Papers: {req.maxPapers}")
    
    try:
        project_paths = get_project_data_paths(req.project_id)
        agent1_output_file = project_paths["agent1_metadata_file"]
        # Ensure directory exists for the output file
        os.makedirs(os.path.dirname(agent1_output_file), exist_ok=True)
    except ValueError as e: # This e is for get_project_data_paths
        print(f"Error configuring paths for project {req.project_id} in /harvest: {e}")
        raise HTTPException(status_code=404, detail=f"Project configuration error: {str(e)}")

    try:
        result = await literature_harvester.find_relevant_papers_and_guide_user_batch(
            topic_details=req.topic,
            date_after=req.dateAfter,
            date_before=req.dateBefore,
            max_papers_to_find=req.maxPapers,
            output_metadata_file_path=agent1_output_file # Pass the path
        )
        if result is None:
            raise HTTPException(status_code=500, detail="Failed to retrieve data from harvester.")
        
        # Update project store after successful batch operation
        if req.project_id in _projects:
            _projects[req.project_id]["agent1_metadata_file"] = agent1_output_file
            save_projects_to_db()
            print(f"Updated project {req.project_id} with Agent1 metadata path via batch: {agent1_output_file}")
        
        return result # Corrected: return the actual result
    except Exception as e: # This e is for the harvesting process
        print(f"Error in /harvest POST for project {req.project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/harvest/stream")
async def harvest_stream(
    project_id: str = Query(...),
    topic: str = Query(...),
    dateAfter: str = Query(...),
    dateBefore: str = Query(...),
    maxPapers: int = Query(...)
):
    print(f"→ Received /harvest/stream GET request for PID: {project_id}, Topic: {topic}")
    
    agent1_output_file_path_for_stream: str
    try:
        project_paths = get_project_data_paths(project_id)
        agent1_output_file_path_for_stream = project_paths["agent1_metadata_file"]
        os.makedirs(os.path.dirname(agent1_output_file_path_for_stream), exist_ok=True)
    except ValueError as ve: # Capture the exception instance
        # MODIFIED: Pass the exception message to error_gen
        async def error_gen(error_message_param: str):
            yield f"data: __ERROR__Project configuration error: {error_message_param}\n\n"
        return StreamingResponse(error_gen(str(ve)), media_type="text/event-stream")


    async def event_generator():
        try:
            async for message_or_result in literature_harvester.find_relevant_papers_and_guide_user_stream(
                topic_details=topic,
                date_after=dateAfter,
                date_before=dateBefore,
                max_papers_to_find=maxPapers,
                output_metadata_file_path=agent1_output_file_path_for_stream # Use the variable defined in the outer scope
            ):
                if isinstance(message_or_result, str):
                    yield f"data: {message_or_result}\n\n"
                elif isinstance(message_or_result, dict) and message_or_result.get("type") == "result":
                    payload = json.dumps(message_or_result["data"])
                    yield f"data: __RESULT__{payload}\n\n"
                    if project_id in _projects:
                        _projects[project_id]["agent1_metadata_file"] = agent1_output_file_path_for_stream
                        save_projects_to_db()
                        print(f"Updated project {project_id} with Agent1 metadata path: {agent1_output_file_path_for_stream}")
                    break
                await asyncio.sleep(0.01)
        except Exception as general_exc: # Capture general exceptions from the stream
            error_message = f"An error occurred during harvesting: {str(general_exc)}"
            print(f"Error in harvest_stream event_generator: {error_message}")
            yield f"data: __ERROR__{error_message}\n\n"
        finally:
            print(f"Stream closed for topic: {topic}, project: {project_id}")

    return StreamingResponse(event_generator(), media_type="text/event-stream")