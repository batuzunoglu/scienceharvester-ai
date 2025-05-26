# backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
import sys
import pathlib

BACKEND_DIR = pathlib.Path(__file__).resolve().parent
sys.path.append(str(BACKEND_DIR))
load_dotenv()

from api.projects import router as projects_router
from api.agent1 import router as agent1_router
from api.agent2 import router as agent2_router
from api.agent3 import router as agent3_router

app = FastAPI(redirect_slashes=False) # Keep this as False

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agent1_router, prefix="/api/agent1", tags=["agent1"])
app.include_router(agent2_router, prefix="/api/agent2", tags=["agent2"])
app.include_router(agent3_router, prefix="/api/agent3", tags=["agent3"])

# --- Key Change for projects_router ---
app.include_router(projects_router, prefix="/api", tags=["projects"]) # Prefix is now just /api
# --------------------------------------

@app.get("/")
async def read_root():
    return {"message": "ScienceHarvester Backend is running"}
