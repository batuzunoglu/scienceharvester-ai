# backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv # <<<< ADD THIS IMPORT
import os                     # <<<< ADD THIS IMPORT (if not already there for other reasons)

load_dotenv() # <<<< ADD THIS LINE AT THE TOP (after imports, before app creation)

# You can add a print statement here to verify if the key is loaded for debugging:
# print(f"--- Main.py: PERPLEXITY_API_KEY from env: {os.getenv('PERPLEXITY_API_KEY')} ---")

from api.projects import router as projects_router
from api.agent1 import router as agent1_router
from api.agent2 import router as agent2_router
from api.agent3 import router as agent3_router
# from api.agent_chat import router as agent_chat_router # If you add this later

app = FastAPI()

# enable CORS for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# mount each router under /api/...
app.include_router(agent1_router, prefix="/api/agent1", tags=["agent1"])
app.include_router(agent2_router, prefix="/api/agent2", tags=["agent2"])
app.include_router(agent3_router, prefix="/api/agent3", tags=["agent3"])
app.include_router(projects_router, prefix="/api/projects", tags=["projects"])
# app.include_router(agent_chat_router, prefix="/api", tags=["chat_agent"]) # If you add this later