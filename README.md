# Insight Harvester AI 

**Insight Harvester AI** is a multi-agent system designed to assist researchers by automating the discovery, extraction, and synthesis of information from academic literature on a user-defined topic. It streamlines the research workflow, enabling users to quickly move from a research question to a synthesized report with key insights.

**(Optional: Add a Screenshot or GIF of the app in action here if you have one)**
![Insight Harvester AI Screenshot](<img width="1360" alt="image" src="image.png" />
) 
*Replace `placeholder_for_your_screenshot.png` with an actual image in your repo or a link to an image.*

## Problem Statement

Researchers today are often overwhelmed by the sheer volume of academic publications. Manually sifting through papers, extracting relevant data points, and synthesizing this information into a coherent understanding is a laborious and time-consuming process. This can significantly slow down the pace of research and discovery.

## Our Solution: Insight Harvester AI

Insight Harvester AI tackles this challenge by employing a pipeline of specialized AI agents:

1.  **Agent 1 (Literature Harvester):** Finds relevant academic papers.
2.  **Agent 2 (PDF Feature Extractor):** Extracts detailed technical and qualitative information from uploaded PDFs.
3.  **Agent 3 (Report Synthesizer):** Generates a comprehensive Markdown report and a downloadable PDF summarizing the findings from all processed papers.

The system is built around "Projects," allowing users to manage and revisit different research topics independently. Each project's data is stored and can be preloaded when a user returns to it.

## Features

*   **Project-Based Workflow:** Create and manage distinct research projects.
*   **Automated Literature Search (Agent 1):** Specify a topic, date range, and number of papers to find relevant academic literature.
*   **Deep PDF Analysis (Agent 2):** Upload PDFs and extract:
    *   Structured technical features (parameters, materials, results, with values, units, and source sentences).
    *   Qualitative insights (objectives, methods, findings, limitations, future work, novelty).
*   **Comprehensive Report Generation (Agent 3):**
    *   Synthesizes information from all processed papers within a project.
    *   Generates a structured Markdown report with sections like Abstract, Introduction, Key Findings, etc.
    *   Provides an option to download the report as a PDF.
*   **Data Persistence & Preloading:** Project data and agent outputs are saved, allowing users to resume work and view previously generated results.
*   **User-Friendly Interface:** Built with Next.js and modern UI components for a smooth experience.

## How Perplexity API Was Used

The Perplexity API, specifically its powerful Sonar models, is the core AI engine driving the intelligent capabilities of Insight Harvester AI across its agents:

1.  **Agent 1 (Literature Harvester):**
    *   **API & Model:** Utilizes the Perplexity API with a model like `sonar-deep-research`.
    *   **Purpose & Why:** This model is chosen for its strong web search capabilities and understanding of academic contexts. Agent 1 sends the user's research topic, date constraints, and desired paper count as a natural language query to the API.
    *   **Functionality:** The API performs a focused search across academic sources to identify peer-reviewed papers. It's prompted to return structured JSON metadata for each paper, including title, authors, DOI, abstract snippets, and an explanation of the paper's relevance to the query. This automates the tedious initial discovery phase.

2.  **Agent 2 (PDF Feature Extractor):**
    *   **API & Model:** Employs the Perplexity API with a model like `sonar-reasoning-pro` (or a similar capable instruct/reasoning model).
    *   **Purpose & Why:** After text is extracted from user-uploaded PDFs, Agent 2 needs to perform deep content analysis. `sonar-reasoning-pro` is chosen for its ability to understand complex scientific text and follow detailed instructions for structured data extraction.
    *   **Functionality:** Two main calls are made per PDF:
        *   **Technical Feature Extraction:** The LLM is prompted to identify and extract specific quantitative data, material properties, experimental parameters, and key results, formatting them as a list of JSON objects (feature name, value, unit, source sentence).
        *   **Qualitative Insights Extraction:** The LLM is prompted to provide a structured summary of the paper, including its main objective, key materials studied, methodology, primary findings, limitations, future work, and novelty claims, returned as a single JSON object.
        This detailed extraction provides the granular data needed for the final synthesis.

3.  **Agent 3 (Report Synthesizer):**
    *   **API & Model:** Leverages a powerful Perplexity API model suitable for long-form generation and synthesis, such as `sonar-reasoning` or a large instruction-tuned model like `llama-3-70b-instruct`.
    *   **Purpose & Why:** This agent's task is to create a coherent, multi-section research report from the potentially diverse information extracted by Agent 1 (overall topic) and Agent 2 (detailed data from multiple papers). A model with strong reasoning and generation capabilities is essential.
    *   **Functionality:**
        *   A "digest" is created by consolidating all key information from Agent 1 and Agent 2 for the current project.
        *   This digest, along with the project topic, is formatted into a detailed prompt instructing the LLM to generate a structured Markdown report. The prompt specifies sections like Abstract, Introduction, Materials & Synthesis, Performance, Discussion, Individual Paper Summaries, Future Outlook, and Conclusion.
        *   The LLM synthesizes the information from the digest into a narrative report.

**Why Perplexity API?** The Perplexity API was chosen for its access to powerful and up-to-date Sonar models, which excel at search, understanding complex text, following structured output instructions, and generating coherent long-form content – all critical for the different stages of this research automation pipeline.

## Tech Stack

*   **Backend:**
    *   **Language:** Python 3.11+
    *   **Web Framework:** FastAPI
    *   **ASGI Server:** Uvicorn
    *   **Environment Variables:** `python-dotenv`
    *   **Asynchronous Operations:** `asyncio`, `aiofiles`
    *   **PDF Text Extraction:** `pdfplumber`
    *   **Markdown-to-PDF:** `WeasyPrint`, `Markdown` (Python library)
    *   **LLM Interaction:** `openai` Python client (for Perplexity API)
*   **Frontend:**
    *   **Framework:** Next.js 14+ (App Router)
    *   **Language:** TypeScript
    *   **UI Library:** React
    *   **Styling:** Tailwind CSS
    *   **Component Library:** shadcn/ui
    *   **Server-Sent Events:** `EventSourcePolyfill`
    *   **Markdown Rendering:** `react-markdown`, `remark-gfm`
    *   **Icons:** `lucide-react`
*   **AI Service:** Perplexity API (Models: `sonar-deep-research`, `sonar-reasoning-pro`, `sonar-reasoning` / `llama-3-70b-instruct`)
*   **Data Storage:**
    *   Local File System (for project-specific agent outputs: JSON, MD, PDF files).
    *   `projects_db.json` (local JSON file for project metadata).
    *   Browser `localStorage` (for `user_session_id`).

## Local Setup & Running Instructions

**Prerequisites:**
*   Python 3.11 or newer
*   Node.js 18.x or newer
*   npm or yarn

**1. Clone the Repository:**
   ```bash
   git clone https://github.com/batuzunoglu/scienceharvester-ai.git 
   cd scienceharvester-ai

   2. Backend Setup:


cd backend
python -m venv .venv         # Create a virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

API Key Setup:
This submitted version of the code (on the main branch based on the initial working commit) contains a pre-configured API key for Perplexity for ease of testing by judges during the hackathon.
For any future development or personal use beyond the hackathon evaluation, it is strongly recommended to remove the hardcoded key and use environment variables. To do this:
Create a file named .env in the backend/ directory.
Add your Perplexity API key to it: PERPLEXITY_API_KEY="pplx-yourActualKeyGoesHere"
The Python code in later development branches is already set up to read from this .env file.

Run Backend Server:
uvicorn main:app --reload --port 8000


3. Frontend Setup:
cd frontend
npm install   # or yarn install
npm run dev   # or yarn dev
