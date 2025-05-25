# backend/agent2_module.py

import os
import json
import re
# import time # Keep if used, otherwise remove
import pdfplumber
from openai import AsyncOpenAI # Assuming this is for Perplexity based on base_url
import asyncio
import traceback # Good for more detailed error logging if needed

# ――― CONFIGURATION ―――
# MODIFIED: Secure API Key Handling
YOUR_PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY")

if not YOUR_PERPLEXITY_API_KEY:
    print("CRITICAL WARNING (agent2_module.py): PERPLEXITY_API_KEY environment variable is not set.")
    YOUR_PERPLEXITY_API_KEY = "API_KEY_NOT_SET_IN_ENV" # Placeholder
    print("    Using placeholder API key which will likely cause API call failures.")
elif not YOUR_PERPLEXITY_API_KEY.startswith("pplx-"):
    print(f"WARNING (agent2_module.py): PERPLEXITY_API_KEY does not look like a valid Perplexity key: '{YOUR_PERPLEXITY_API_KEY[:10]}...'")


MAX_TEXT_CHARS_FOR_API = 45000
# METADATA_EXTRACTION_SNIPPET_LENGTH = 7000 # Unused as per your comment

# AGENT2_EXTRACTIONS_DIR and its os.makedirs were already correctly removed.

def clean_extracted_text(full_text: str) -> str:
    if not full_text:
        return ""
    patterns_to_remove = [
        r"\n\s*(References|REFERENCES|Bibliography|BIBLIOGRAPHY)\s*(\n|$)",
        r"\n\s*(Acknowledgements|ACKNOWLEDGEMENTS|Acknowledgments|ACKNOWLEDGMENTS)\s*(\n|$)",
        r"\n\s*(Author Contributions|AUTHOR CONTRIBUTIONS)\s*(\n|$)",
        r"\n\s*(Conflicts of Interest|CONFLICTS_OF_INTEREST|Declaration of Competing Interest)\s*(\n|$)",
        r"\n\s*(Supporting Information|SUPPORTING_INFORMATION)\s*(\n|$)",
    ]
    temp = full_text
    for pat in patterns_to_remove:
        matches = list(re.finditer(pat, temp, re.IGNORECASE))
        if matches:
            last_match_start = matches[-1].start()
            if last_match_start > 0.6 * len(temp):
                temp = temp[:last_match_start]

    lines = temp.split("\n")
    filtered_lines = []
    for l in lines:
        stripped_line = l.strip()
        if len(stripped_line.split()) > 2 or len(stripped_line) > 15: # Keep lines with some substance
            if len(stripped_line) < 30 and not re.search(r'[a-zA-Z]{3,}', stripped_line): # Filter out short lines of only symbols
                continue
            filtered_lines.append(stripped_line)
    return "\n".join(filtered_lines).strip()


def sanitize_doi_for_filename(doi: str) -> str:
    if not doi:
        return "unknown_doi"
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi, flags=re.IGNORECASE)
    return re.sub(r'[<>:"/\\|?*]', "_", doi)


async def extract_text_from_pdf_path_async(pdf_path: str) -> str | None:
    # print(f"    [Agent2 Module] Starting text extraction from {pdf_path}") # Keep prints minimal
    try:
        def sync_extract_text():
            with pdfplumber.open(pdf_path) as pdf:
                pages = []
                for p in pdf.pages: # Simpler iteration
                    txt = p.extract_text(x_tolerance=1, y_tolerance=3)
                    if txt:
                        pages.append(txt)
            if not pages: return None
            full = "\n\n--- PAGE BREAK ---\n\n".join(pages)
            return clean_extracted_text(full)

        extracted_text = await asyncio.to_thread(sync_extract_text)
        # if extracted_text:
        #     print(f"    [Agent2 Module] Finished text extraction from {os.path.basename(pdf_path)}. Length: {len(extracted_text)}")
        # else:
        #     print(f"    [Agent2 Module] No text extracted from {os.path.basename(pdf_path)}.")
        return extracted_text
    except Exception as e:
        print(f"    [Agent2 Module] PDF text extraction error for {os.path.basename(pdf_path)}: {e}")
        return None


async def call_perplexity_llm_async(
    messages_for_llm: list[dict],
    model="sonar-reasoning-pro", # This model is for reasoning, ensure it's suitable for extraction tasks
                                 # sonar-small-online or sonar-medium-online might be better if web search helps context
                                 # Or a larger instruct model like llama-3-70b-instruct for pure extraction
    temperature=0.1,
    max_tokens_to_sample=2048 # Perplexity uses max_tokens
) -> str | None:
    # MODIFIED: Check API key before attempting to use it
    if not YOUR_PERPLEXITY_API_KEY or YOUR_PERPLEXITY_API_KEY == "API_KEY_NOT_SET_IN_ENV":
        print(f"    [Agent2 Module LLM] SKIPPING API call to {model}: PERPLEXITY_API_KEY is not properly configured.")
        return None

    client = AsyncOpenAI(api_key=YOUR_PERPLEXITY_API_KEY, base_url="https://api.perplexity.ai")
    try:
        # print(f"    [Agent2 Module LLM] Calling model: {model}...") # Reduce noise
        resp = await client.chat.completions.create(
            model=model,
            messages=messages_for_llm,
            temperature=temperature,
            max_tokens=max_tokens_to_sample # Ensure this matches OpenAI's param name if client is strictly OpenAI SDK
        )
        return resp.choices[0].message.content
    except Exception as e:
        print(f"    [Agent2 Module LLM] LLM call error (model: {model}): {e}")
        if "authentication" in str(e).lower() or "API key" in str(e).lower() or "401" in str(e):
             print("    [Agent2 Module LLM] This error often indicates an invalid or missing PERPLEXITY_API_KEY.")
        # traceback.print_exc() # For deeper debugging if needed
        return None


def parse_llm_json_output(llm_content: str | None, expecting_list=False) -> dict | list | None:
    if not llm_content:
        return None
    
    # Attempt to remove <think> blocks before further parsing
    cleaned_content = llm_content
    think_block_pattern = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
    cleaned_content = think_block_pattern.sub("", cleaned_content).strip()
    # if cleaned_content != llm_content:
    #     print("  DEBUG (agent2_module): Removed <think> block(s) from LLM response for JSON parsing.")

    start_char, end_char = ("[", "]") if expecting_list else ("{", "}")
    
    # Try to find JSON within markdown code fences first
    # Using a more robust regex for markdown code blocks
    match = re.search(r"```(?:json)?\s*(" + re.escape(start_char) + r"[\s\S]*?" + re.escape(end_char) + r")\s*```", cleaned_content, re.DOTALL | re.IGNORECASE)
    json_blob_to_parse = None

    if match:
        json_blob_to_parse = match.group(1)
    else:
        first_char_index = cleaned_content.find(start_char)
        last_char_index = cleaned_content.rfind(end_char)
        if first_char_index != -1 and last_char_index > first_char_index:
            # Ensure what's between is likely JSON, not just any brackets
            # A simple heuristic: the content inside should not be excessively long without JSON structure
            potential_json = cleaned_content[first_char_index : last_char_index + 1]
            # Check if the string predominantly looks like a JSON structure rather than prose with brackets
            if (potential_json.count('"') > 4 or potential_json.count(':') > 2) or \
               (len(potential_json) < 500 and not re.search(r'\s{3,}', potential_json)): # Avoid long prose sections
                json_blob_to_parse = potential_json
            else: # If it doesn't look like JSON, try parsing the whole cleaned content as a last resort
                json_blob_to_parse = cleaned_content.strip()

        else: # Fallback to the whole content if no clear delimiters are found
            json_blob_to_parse = cleaned_content.strip()


    if not json_blob_to_parse:
        return None

    try:
        return json.loads(json_blob_to_parse)
    except json.JSONDecodeError as e:
        # print(f"    [Agent2 Module] JSON parse error: {e}. Snippet: '{json_blob_to_parse[:200]}...'") # Reduce noise
        if "Trailing comma" in str(e): # Attempt to fix common issue
            try:
                fixed_blob = re.sub(r",\s*([}\]])", r"\1", json_blob_to_parse)
                return json.loads(fixed_blob)
            except json.JSONDecodeError:
                pass # If fix fails, fall through to return None
        return None


async def extract_technical_features_async(
    paper_text: str,
    paper_title: str, 
    paper_doi: str | None,
) -> list[dict]:
    # print(f"    [Agent2 Module] Starting technical feature extraction for “{paper_title}”")
    system_prompt = f"""
You are an AI assistant specialized in extracting structured technical features from scientific papers.
The paper title is: "{paper_title}"
{f"The paper DOI is: {paper_doi}" if paper_doi else ""}
Extract key quantitative and qualitative technical specifications, parameters, results, and material properties.
For each feature, provide:
- "feature_name": A concise name for the technical aspect.
- "feature_value": The value(s) of the feature (string, number, or list).
- "feature_unit": The unit of measurement, if applicable (null if none).
- "source_sentence": The exact sentence from the paper text where this feature was primarily found or inferred.
Return ONLY a valid JSON list of these objects. If no specific technical features are found, return an empty list [].
"""
    user_prompt_text = paper_text[:MAX_TEXT_CHARS_FOR_API]
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": f"<paper_text_start>\n{user_prompt_text}\n</paper_text_start>"}]

    llm_output = await call_perplexity_llm_async(messages, model="sonar-reasoning-pro", temperature=0.05, max_tokens_to_sample=3000)
    # sonar-reasoning-pro might be a good choice if it exists and is good at structured output.
    # Otherwise, a strong instruct model like llama-3-70b-instruct could work well.
    
    parsed_llm_response = parse_llm_json_output(llm_output, expecting_list=True)

    if isinstance(parsed_llm_response, list):
        valid_features = []
        for item in parsed_llm_response:
            if isinstance(item, dict) and \
               "feature_name" in item and \
               "feature_value" in item and \
               "source_sentence" in item: # Basic validation
                item.setdefault("feature_unit", None) # Ensure unit key exists
                valid_features.append(item)
        # print(f"    [Agent2 Module] Extracted {len(valid_features)} technical features for “{paper_title}”.")
        return valid_features
    # print(f"    [Agent2 Module] Failed to extract/parse technical features for “{paper_title}”. LLM output snippet: {llm_output[:100] if llm_output else 'None'}")
    return []


async def extract_qualitative_insights_async(
    paper_text: str,
    paper_title: str, 
    paper_doi: str | None
) -> dict:
    # print(f"    [Agent2 Module] Starting qualitative insights extraction for “{paper_title}”")
    system_prompt = f"""
You are an expert AI scientific reviewer. From the provided paper text (title: "{paper_title}"{f", DOI: {paper_doi}" if paper_doi else ""}), provide a concise summary.
Return ONLY a single valid JSON object with keys: "main_objective", "key_materials_studied", "key_methodology_summary", "primary_findings_conclusions", "limitations_discussed_by_authors", "future_work_suggested_by_authors", "novelty_significance_claim", "key_tables_figures_present".
Use reasonably short, direct phrases or lists of strings. If info not found, use null for strings or an empty list [] for lists.
"""
    user_prompt_text = paper_text[:MAX_TEXT_CHARS_FOR_API]
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": f"<paper_text_start>\n{user_prompt_text}\n</paper_text_start>"}]

    llm_output = await call_perplexity_llm_async(messages, model="sonar-reasoning-pro", temperature=0.2, max_tokens_to_sample=2000)
    parsed_response = parse_llm_json_output(llm_output, expecting_list=False)

    default_insights = {
        "main_objective": None, "key_materials_studied": [], "key_methodology_summary": None,
        "primary_findings_conclusions": [], "limitations_discussed_by_authors": None,
        "future_work_suggested_by_authors": None, "novelty_significance_claim": None,
        "key_tables_figures_present": None
    }
    if isinstance(parsed_response, dict):
        # Ensure all keys from default structure are present, filling with defaults if missing
        final_insights = default_insights.copy() # Start with defaults
        final_insights.update(parsed_response) # Override with parsed values
        # print(f"    [Agent2 Module] Extracted qualitative insights for “{paper_title}”.")
        return final_insights
        
    # print(f"    [Agent2 Module] Failed to extract/parse qualitative insights for “{paper_title}”. LLM output snippet: {llm_output[:100] if llm_output else 'None'}")
    return default_insights


async def process_single_pdf_async(
    pdf_path: str,
    agent1_paper_metadata: dict | None = None 
) -> dict:
    # Attempt to get original filename if project_id was prepended in a temp dir
    # Assumes format like "projectid_actualfilename.pdf"
    base_filename = os.path.basename(pdf_path)
    pdf_filename_original = base_filename.split('_', 1)[-1] if '_' in base_filename and len(base_filename.split('_', 1)[0]) > 20 else base_filename


    result_payload = {
        "filename": pdf_filename_original, # Use the original filename for the result
        "error": None, 
        "technical_features": [], 
        "qualitative_insights": {} # Should match default_insights structure
    }

    # Use title/DOI from Agent1 if available, otherwise fall back to filename
    display_title = agent1_paper_metadata.get("title", "").strip() if agent1_paper_metadata else ""
    if not display_title: display_title = pdf_filename_original.replace(".pdf", "")
    
    display_doi = agent1_paper_metadata.get("doi") if agent1_paper_metadata else None
    
    print(f"  [Agent2 Module] Processing PDF: '{pdf_filename_original}' (Display Title: '{display_title}', DOI: {display_doi or 'N/A'})")

    extracted_text = await extract_text_from_pdf_path_async(pdf_path)
    if not extracted_text:
        result_payload["error"] = "No text could be extracted from PDF or PDF is empty/unreadable."
        print(f"    [Agent2 Module] Error for '{pdf_filename_original}': {result_payload['error']}")
        result_payload["qualitative_insights"] = extract_qualitative_insights_async("", display_title, display_doi).get_default_value() # Ensure structure
        return result_payload

    try:
        # Run extractions concurrently
        tech_task = extract_technical_features_async(extracted_text, display_title, display_doi)
        qual_task = extract_qualitative_insights_async(extracted_text, display_title, display_doi)
        
        # Use asyncio.gather with return_exceptions=True to handle individual task failures
        results = await asyncio.gather(tech_task, qual_task, return_exceptions=True)
        
        # Check results from gather
        if isinstance(results[0], Exception):
            print(f"    [Agent2 Module] Error extracting technical features for '{pdf_filename_original}': {results[0]}")
            result_payload["technical_features"] = [] # Default empty list on error
            # Optionally, add a specific error note for this part of the extraction
            if not result_payload["error"]: result_payload["error"] = "Failed to extract technical features."
        else:
            result_payload["technical_features"] = results[0]

        if isinstance(results[1], Exception):
            print(f"    [Agent2 Module] Error extracting qualitative insights for '{pdf_filename_original}': {results[1]}")
            result_payload["qualitative_insights"] = { # Default structure on error
                "main_objective": None, "key_materials_studied": [], "key_methodology_summary": None,
                "primary_findings_conclusions": [], "limitations_discussed_by_authors": None,
                "future_work_suggested_by_authors": None, "novelty_significance_claim": None,
                "key_tables_figures_present": None
            }
            if not result_payload["error"]: result_payload["error"] = "Failed to extract qualitative insights."
        else:
            result_payload["qualitative_insights"] = results[1]

        # If any sub-task failed, the overall result might still be considered partially successful
        # but the `error` field in result_payload should reflect if any part failed.
        if isinstance(results[0], Exception) or isinstance(results[1], Exception):
            if not result_payload["error"]: # If no more specific error was set by a sub-task
                 result_payload["error"] = "One or more extraction sub-tasks failed. See server logs for details."

    except Exception as e: # Catch-all for unexpected errors in this function's orchestration
        error_msg = f"Unexpected error during overall PDF processing for '{pdf_filename_original}': {e}"
        result_payload["error"] = error_msg
        print(f"    [Agent2 Module] {error_msg}\n{traceback.format_exc()}")
    
    if not result_payload["error"]:
         print(f"  [Agent2 Module] Successfully processed: '{pdf_filename_original}'")
    else:
         print(f"  [Agent2 Module] Finished processing '{pdf_filename_original}' with error(s): {result_payload['error']}")
         
    return result_payload