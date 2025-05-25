# backend/agent3_module.py
from __future__ import annotations
import os
import json
import re
# import time # Keep if used, otherwise remove
import pathlib
from collections import defaultdict
from openai import AsyncOpenAI # Assuming this is for Perplexity based on base_url
import asyncio
import aiofiles 
import traceback 

# ----------------------------------------------------------------------
#  LOW-LEVEL SETTINGS
# ----------------------------------------------------------------------
# MODIFIED: Secure API Key Handling
YOUR_PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY")

if not YOUR_PERPLEXITY_API_KEY:
    print("CRITICAL WARNING (agent3_module.py): PERPLEXITY_API_KEY environment variable is not set.")
    YOUR_PERPLEXITY_API_KEY = "API_KEY_NOT_SET_IN_ENV" # Placeholder
    print("    Using placeholder API key which will likely cause API call failures.")
elif not YOUR_PERPLEXITY_API_KEY.startswith("pplx-"):
    print(f"WARNING (agent3_module.py): PERPLEXITY_API_KEY does not look like a valid Perplexity key: '{YOUR_PERPLEXITY_API_KEY[:10]}...'")

# Global path constants removed as they are now passed into functions
# Keywords remain the same
MATERIAL_KEYWORDS = ["material", "sample", "catalyst", "electrode", "mof", "biochar", "qd", "quantum dot", "precursor", "linker", "dopant", "composite", "framework", "sorbent", "nanoparticle", "film", "membrane", "powder", "pellet", "active layer"]
SYNTHESIS_KEYWORDS = ["synthesis", "fabrication", "preparation", "pyrolysis", "solvothermal", "hydrothermal", "temperature", "time", "duration", "pressure", "solvent", "annealing", "calcination", "ratio", "concentration", "functionalization", "route", "doping", "coating", "treatment"]
PERFORMANCE_KEYWORDS = ["capacity", "uptake", "efficiency", "selectivity", "limit", "lod", "yield", "conversion", "eqe", "luminance", "current", "voltage", "lifetime", "stability", "power conversion", "activity", "performance"]
CHARACTERIZATION_KEYWORDS = ["xrd", "sem", "tem", "ftir", "raman", "xps", "nmr", "tga", "dsc", "bet", "voltammogram", "cyclic voltammetry", "eis", "afm", "plqy"]

MAX_DIGEST_CHARS_FOR_LLM = 45000 
LLM_MAX_TOKENS_REPORT = 8000    

# ----------------------------------------------------------------------
#  BASIC LLM WRAPPER (Async)
# ----------------------------------------------------------------------
async def _llm_call_async(msgs: list[dict], model: str = "sonar-reasoning", # <<< REVERTED TO YOUR ORIGINAL MODEL
                          temperature: float = 0.3, max_tokens: int = LLM_MAX_TOKENS_REPORT) -> str | None:
    # MODIFIED: Check API key before attempting to use it
    if not YOUR_PERPLEXITY_API_KEY or YOUR_PERPLEXITY_API_KEY == "API_KEY_NOT_SET_IN_ENV":
        print(f"    [Agent3 Module LLM] SKIPPING API call to {model}: PERPLEXITY_API_KEY is not properly configured.")
        return None 

    client = AsyncOpenAI(api_key=YOUR_PERPLEXITY_API_KEY, base_url="https://api.perplexity.ai")
    try:
        response = await client.chat.completions.create(
            model=model, # Uses the model passed in or the default "sonar-reasoning"
            messages=msgs,
            temperature=temperature,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"    [Agent3 Module LLM] LLM call error (model: {model}): {e}")
        if "authentication" in str(e).lower() or "API key" in str(e).lower() or "401" in str(e) or "Invalid model" in str(e): # Added "Invalid model"
             print("    [Agent3 Module LLM] This error often indicates an invalid or missing PERPLEXITY_API_KEY, or an invalid model name.")
        return None

# ---------------------------------------------------------------------------
#  Helper: synthesize_data_for_report_prompt (Your existing function - unchanged from previous correct version)
# ---------------------------------------------------------------------------
def format_value_for_digest(value_orig: any, unit_str: str | None = None) -> str:
    # ... (your existing code)
    if value_orig is None or str(value_orig).strip().lower() == "n/a": return "N/A"
    unit_display = f" {unit_str}" if unit_str and str(unit_str).strip().lower() not in ['none', 'null', ''] else ""
    if isinstance(value_orig, list):
        clean_list = [str(v).strip() for v in value_orig if str(v).strip()]
        return (", ".join(clean_list) + unit_display).strip() if clean_list else "N/A"
    return f"{str(value_orig).strip()}{unit_display}".strip()

def synthesize_data_for_report_prompt(all_papers_data: list[dict[str, any]], project_topic: str) -> str:
    # ... (your existing code, with minor refinements from previous step)
    if not all_papers_data: return "No extracted paper data available to synthesize for the report."
    overall = {
        "num_papers": len(all_papers_data), "main_topic": project_topic if project_topic else "Not Specified",
        "materials": set(), "synth_methods": set(), "synth_params": defaultdict(set),
        "perf_metrics": defaultdict(set), "char_techniques": set(), "limits": set(), "future": set(), "paper_overviews": []
    }
    for paper_data in all_papers_data:
        paper_title = paper_data.get("title", paper_data.get("filename", "Untitled Paper").replace("_extraction.json", "").replace(".pdf", "")) 
        paper_doi = paper_data.get("doi", "N/A") 
        current_paper_materials, current_paper_methods, current_paper_key_params, current_paper_perf_highlights = set(), set(), [], []
        
        for feature in paper_data.get("technical_features", []):
            name = feature.get("feature_name", "").strip()
            name_lower = name.lower()
            value, unit = feature.get("feature_value"), feature.get("feature_unit")
            formatted_value = format_value_for_digest(value, unit)

            if any(kw in name_lower for kw in MATERIAL_KEYWORDS):
                if isinstance(value, list): [current_paper_materials.add(str(v_item).strip()) for v_item in value if str(v_item).strip()]
                elif isinstance(value, str) and value.strip(): current_paper_materials.add(value.strip())
            
            if any(kw in name_lower for kw in SYNTHESIS_KEYWORDS):
                is_textual_method = isinstance(value, str) and len(value.strip()) > 3 and not value.strip().isdigit()
                if is_textual_method and any(tag in name_lower for tag in ["method","route","approach","protocol","functionalization","treatment"]):
                    overall["synth_methods"].add(value.strip()); current_paper_methods.add(value.strip())
                if any(kw_param in name_lower for kw_param in ["temperature","time","duration","ratio","conc","ph","pressure","yield"]): 
                    if name and formatted_value != "N/A": 
                        overall["synth_params"][name].add(formatted_value); current_paper_key_params.append(f"{name}: {formatted_value}")
            
            if any(kw in name_lower for kw in PERFORMANCE_KEYWORDS) and formatted_value != "N/A":
                if name: 
                    overall["perf_metrics"][name].add(formatted_value); current_paper_perf_highlights.append(f"{name}: {formatted_value}")

            for char_kw in CHARACTERIZATION_KEYWORDS:
                if char_kw in name_lower: overall["char_techniques"].add(char_kw.upper()); break
        
        overall["materials"].update(current_paper_materials)
        
        insights = paper_data.get("qualitative_insights", {})
        limitations = insights.get("limitations_discussed_by_authors")
        if isinstance(limitations, list): overall["limits"].update(s.strip() for s in limitations if s and s.strip())
        elif isinstance(limitations, str) and limitations.strip(): overall["limits"].add(limitations.strip())
        
        future_work = insights.get("future_work_suggested_by_authors")
        if isinstance(future_work, list): overall["future"].update(s.strip() for s in future_work if s and s.strip())
        elif isinstance(future_work, str) and future_work.strip(): overall["future"].add(future_work.strip())
        
        highlights = []
        if insights.get("main_objective"): highlights.append(f"Objective: {insights['main_objective']}")
        if current_paper_materials: highlights.append(f"Key Materials: {', '.join(list(current_paper_materials)[:3])}")
        if current_paper_perf_highlights: highlights.append(current_paper_perf_highlights[0])
        elif insights.get("primary_findings_conclusions") and insights["primary_findings_conclusions"]: 
            highlights.append(f"Finding: {insights['primary_findings_conclusions'][0]}")
        if current_paper_methods: highlights.append(f"Synthesis Method: {list(current_paper_methods)[0]}")
        if insights.get("novelty_significance_claim"): highlights.append(f"Novelty Claim: {insights['novelty_significance_claim']}")
        
        overall["paper_overviews"].append({"doi": paper_doi, "title": paper_title, "highlights": highlights[:3]}) 

    lines = [f"## Project Digest: {overall['main_topic']}", f"This digest summarizes findings from {overall['num_papers']} paper(s).\n"]
    if overall["materials"]: lines.extend(["### Key Materials Investigated", "- " + "; ".join(sorted(list(overall["materials"]))[:15]), ""])
    if overall["synth_methods"]: lines.extend(["### Common Synthesis Approaches", "- " + "; ".join(sorted(list(overall["synth_methods"]))[:10]), ""])
    if overall["synth_params"]:
        lines.append("### Notable Synthesis Parameters Reported")
        for k, v_set in list(overall["synth_params"].items())[:7]: lines.append(f"- **{k.capitalize()}**: {', '.join(sorted(list(v_set))[:3])}")
        lines.append("")
    if overall["char_techniques"]: lines.extend(["### Common Characterization Techniques", "- " + ", ".join(sorted(list(overall["char_techniques"]))), ""])
    if overall["perf_metrics"]:
        lines.append("### Key Performance Metrics Highlights")
        for k, v_set in list(overall["perf_metrics"].items())[:10]: lines.append(f"- **{k.capitalize()}**: {', '.join(sorted(list(v_set))[:3])}")
        lines.append("")
    if overall["limits"]: lines.extend(["### Common Limitations Discussed", "- " + "; ".join(sorted(list(overall["limits"]))[:7]), ""])
    if overall["future"]: lines.extend(["### Suggested Future Research", "- " + "; ".join(sorted(list(overall["future"]))[:7]), ""])
    
    lines.append("\n---\n\n## Individual Paper Highlights")
    for p_overview in overall["paper_overviews"]:
        lines.append(f"\n### {p_overview['title']}")
        lines.append(f"*(DOI: {p_overview['doi']})*")
        for highlight in p_overview["highlights"]: lines.append(f"- {highlight}")
        lines.append("") 
        
    return "\n".join(lines)[:MAX_DIGEST_CHARS_FOR_LLM]

# ------------- PDF helper (Async via to_thread) -------------
async def md_to_pdf_async(md_text: str, output_pdf_path: str) -> str | None:
    # ... (your existing md_to_pdf_async code, ensure CSS is correct and libraries are importable)
    def sync_md_to_pdf_conversion():
        try:
            from weasyprint import HTML, CSS 
            import markdown as md_lib
        except ImportError as exc:
            print(f"[Agent3 Module PDF] WeasyPrint or Markdown library unavailable: {exc}. PDF generation skipped.")
            return None
        try:
            html_content = md_lib.markdown(md_text, extensions=['extra', 'fenced_code', 'tables', 'sane_lists', 'toc', 'smarty'])
            base_css = """
                @page { size: A4; margin: 1.5cm; @bottom-center { content: "Page " counter(page) " of " counter(pages); font-size: 9pt; color: #666; } }
                body { font-family: 'Times New Roman', Times, serif; line-height: 1.6; font-size: 11pt; color: #222; }
                h1, h2, h3, h4, h5, h6 { font-family: 'Georgia', serif; color: #000; line-height: 1.25; margin-top: 1.4em; margin-bottom: 0.5em; page-break-after: avoid; font-weight: 500;}
                h1 { font-size: 20pt; border-bottom: 1.5px solid #ccc; padding-bottom: 0.3em; margin-top: 0.5em;} 
                h2 { font-size: 16pt; border-bottom: 1px solid #ddd; padding-bottom: 0.25em; }
                h3 { font-size: 13pt; font-weight: bold;} 
                h4 { font-size: 11pt; font-style: italic; font-weight: bold;} 
                p, li { margin-bottom: 0.6em; text-align: justify; }
                ul, ol { padding-left: 25px; } 
                li > p { margin-bottom: 0.2em; } 
                code { font-family: 'Consolas', 'Courier New', monospace; background-color: #f0f0f0; padding: 0.15em 0.3em; border-radius: 3px; font-size: 0.95em; }
                pre { background-color: #f0f0f0; border: 1px solid #e0e0e0; border-radius: 4px; padding: 0.8em 1em; overflow-x: auto; white-space: pre-wrap; word-wrap: break-word; font-size: 0.9em; line-height: 1.4;}
                pre code { background-color: transparent; padding: 0; border-radius: 0; border: none; } 
                table { border-collapse: collapse; width: 100%; margin-bottom: 1.2em; page-break-inside: avoid; font-size: 0.95em; }
                th, td { border: 1px solid #bbb; padding: 0.5em 0.7em; text-align: left; vertical-align: top;} 
                th { background-color: #e8e8e8; font-weight: 600; }
                blockquote { border-left: 3px solid #ccc; padding-left: 1.2em; margin-left: 0; color: #444; font-style: italic; }
                a { color: #0056b3; text-decoration: none; } a:hover { text-decoration: underline; } 
                hr { border: none; border-top: 1px solid #ccc; margin: 2.5em 0; }
            """
            pathlib.Path(output_pdf_path).parent.mkdir(parents=True, exist_ok=True)
            HTML(string=html_content).write_pdf(output_pdf_path, stylesheets=[CSS(string=base_css)])
            return str(pathlib.Path(output_pdf_path).resolve())
        except Exception as exc:
            print(f"[Agent3 Module PDF] Error during PDF conversion with WeasyPrint: {exc}")
            traceback.print_exc() 
            return None
    return await asyncio.to_thread(sync_md_to_pdf_conversion)

# ----------------------------------------------------------------------
#  MODIFIED MAIN CALLABLE FOR REPORT GENERATION
# ----------------------------------------------------------------------
async def create_comprehensive_report_async(
    project_id: str, 
    agent1_metadata_path: str,
    agent2_extractions_path_for_project: str,
    reports_output_path_for_project: str, 
) -> tuple[str | None, str | None, str | None]: 
    print(f"[Agent3 Module] Generating report for project_id: {project_id}")
    # ... (rest of your logic for loading agent1_metadata, agent2_extractions, and synthesizing digest) ...
    # Ensure this part is robust and uses the passed-in paths correctly.
    # My previous version of this function should be mostly correct in its path usage.

    project_topic_from_agent1 = f"Project Analysis: {project_id}" 
    try:
        if await asyncio.to_thread(os.path.exists, agent1_metadata_path):
            async with aiofiles.open(agent1_metadata_path, "r", encoding="utf-8") as f:
                agent1_data = json.loads(await f.read())
                if "project_topic" in agent1_data and agent1_data["project_topic"].strip():
                    project_topic_from_agent1 = agent1_data["project_topic"]
        else:
            print(f"  [Agent3 Module] Warning: Agent1 metadata file not found at {agent1_metadata_path}. Report may lack overall topic context.")
    except Exception as e:
        err_msg = f"Error loading project topic from Agent1 metadata ({agent1_metadata_path}): {e}"
        print(f"  [Agent3 Module] {err_msg}")

    paper_extractions_data = []
    try:
        if not await asyncio.to_thread(os.path.isdir, agent2_extractions_path_for_project):
            err_msg = f"Agent2 extractions directory not found: {agent2_extractions_path_for_project}"
            return None, None, err_msg
        extraction_files = [f for f in await asyncio.to_thread(os.listdir, agent2_extractions_path_for_project) if f.endswith("_extraction.json")]
        if not extraction_files:
            err_msg = f"No Agent 2 extraction files (*_extraction.json) found in {agent2_extractions_path_for_project}."
            return None, None, err_msg
        for filename in extraction_files:
            filepath = os.path.join(agent2_extractions_path_for_project, filename)
            try:
                async with aiofiles.open(filepath, "r", encoding="utf-8") as f_content:
                    paper_extractions_data.append(json.loads(await f_content.read()))
            except Exception as e_file:
                print(f"  [Agent3 Module] Error reading/parsing Agent2 file {filepath}: {e_file}. Skipping.")
    except Exception as e:
        err_msg = f"Error listing Agent2 extractions in {agent2_extractions_path_for_project}: {e}"
        return None, None, err_msg
    if not paper_extractions_data:
        err_msg = "No valid Agent 2 data loaded after checking all files. Cannot generate report."
        return None, None, err_msg

    try:
        digest_for_llm = await asyncio.to_thread(
            synthesize_data_for_report_prompt, paper_extractions_data, project_topic_from_agent1
        )
        if not digest_for_llm or digest_for_llm == "No extracted paper data available to synthesize for the report.":
            err_msg = "Digest generation resulted in no usable content. Check Agent 2 outputs."
            return None, None, err_msg
    except Exception as e_synth:
        err_msg = f"Error during data synthesis for LLM prompt: {e_synth}"
        print(f"  [Agent3 Module] {err_msg}\n{traceback.format_exc()}")
        return None, None, err_msg
    
    system_prompt = """You are an expert AI scientific writer tasked with generating a comprehensive project report in Markdown format.
The report should be well-structured, insightful, and based *solely* on the provided digest of information from multiple research papers.
Do NOT invent or infer data beyond what is present in the digest. If specific details are missing, state that they were not available in the provided data.

**Markdown Report Structure:**
1.  **Title:** Create a concise and informative title for the project based on the main topic from the digest.
2.  **Abstract:** ... (Your detailed abstract prompt)
3.  **Introduction:** ... (Your detailed intro prompt)
4.  **Key Materials and Synthesis Insights:** ...
5.  **Performance Analysis and Characterization:** ...
6.  **Discussion (Commonalities, Divergences, Limitations):** ...
7.  **Summary of Key Findings from Individual Papers:** ...
8.  **Identified Gaps and Future Outlook:** ...
9.  **Conclusion:** ...

**Formatting and Tone:** ... (Your detailed formatting/tone prompt)
"""
    user_prompt = f"Please generate a Markdown research report for the project titled '{project_topic_from_agent1}', based on the following digest of information:\n\n<digest_start>\n{digest_for_llm}\n</digest_start>"
    
    markdown_report_content = await _llm_call_async(
        [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        model="sonar-reasoning", # <<< REVERTED TO YOUR ORIGINAL WORKING MODEL
        max_tokens=LLM_MAX_TOKENS_REPORT 
    )

    if not markdown_report_content:
        err_msg = "LLM failed to generate markdown report content. This might be due to an API key issue, service problem, or invalid model."
        print(f"  [Agent3 Module] {err_msg}")
        return None, None, err_msg
    
    markdown_report_content = re.sub(r"<think>.*?</think>", "", markdown_report_content, flags=re.IGNORECASE | re.DOTALL).strip()
    if markdown_report_content.startswith("```markdown") and markdown_report_content.endswith("```"):
        markdown_report_content = markdown_report_content[len("```markdown"):-len("```")].strip()
    elif markdown_report_content.startswith("```") and markdown_report_content.endswith("```"):
         markdown_report_content = markdown_report_content[len("```"):-len("```")].strip()

    if not markdown_report_content.strip():
        err_msg = "LLM returned an empty or whitespace-only report. The digest might have been insufficient."
        print(f"  [Agent3 Module] {err_msg}")
        return None, None, err_msg

    await asyncio.to_thread(os.makedirs, reports_output_path_for_project, exist_ok=True)
    safe_project_id_fn = project_id # Use the original project_id
    md_filename = f"{safe_project_id_fn}_report.md" 
    md_filepath = os.path.join(reports_output_path_for_project, md_filename)
    
    try:
        async with aiofiles.open(md_filepath, "w", encoding="utf-8") as f:
            await f.write(markdown_report_content)
        print(f"  [Agent3 Module] Markdown report saved to: {md_filepath}")
        return markdown_report_content, md_filepath, None 
    except Exception as e:
        err_msg = f"Error saving markdown report to {md_filepath}: {e}"
        print(f"  [Agent3 Module] {err_msg}")
        return markdown_report_content, None, err_msg