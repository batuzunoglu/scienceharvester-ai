# backend/literature_harvester.py

import os
import json
import re
from openai import AsyncOpenAI # Assuming this is for Perplexity, as client is configured for it
import urllib.parse
import time
import asyncio
import traceback 

# --- CONFIGURATION ---
# MODIFIED: Load API key and check for its existence securely
YOUR_API_KEY = os.environ.get("PERPLEXITY_API_KEY")

if not YOUR_API_KEY:
    print("CRITICAL WARNING (literature_harvester.py): PERPLEXITY_API_KEY environment variable is not set.")
    # This placeholder will cause API calls to fail clearly if the key isn't set in .env or production env
    YOUR_API_KEY = "API_KEY_NOT_SET_IN_ENV" 
    print("    Using placeholder API key which will cause API call failures if not overridden by environment.")
elif not YOUR_API_KEY.startswith("pplx-"):
    # This is just a warning, as some valid keys might not start with "pplx-" in the future,
    # but it's a good sanity check for current Perplexity keys.
    print(f"WARNING (literature_harvester.py): PERPLEXITY_API_KEY loaded, but it does not look like a typical Perplexity key (expected to start with 'pplx-'). Key starts with: '{YOUR_API_KEY[:10]}...'")


DEFAULT_AGENT1_METADATA_BASENAME = "agent1_found_papers_metadata.json"
USER_PDF_DOWNLOAD_FOLDER_SUGGESTION = "input_pdfs_for_agent2" # This seems like a leftover from local script, review if needed for server


# --- HELPER FUNCTIONS ---
def sanitize_doi_for_filename(doi):
    if not doi: return "unknown_doi"
    # Remove http(s)://doi.org/ prefix if present
    doi = re.sub(r"^(https?://)?(dx\.)?doi\.org/", "", doi, flags=re.IGNORECASE)
    return re.sub(r'[<>:"/\\|?*]', '_', doi)

async def call_perplexity_llm_helper(messages_for_llm, model="sonar-deep-research", temperature=0.1, max_tokens=None):
    # MODIFIED: Check if the API key is valid before making a call
    if not YOUR_API_KEY or YOUR_API_KEY == "API_KEY_NOT_SET_IN_ENV":
        print(f"    [LLM HELPER (literature_harvester)] SKIPPING API call to {model}: PERPLEXITY_API_KEY is not properly configured.")
        return None # Crucial to return None if key is bad, so calling code handles it

    client = AsyncOpenAI(api_key=YOUR_API_KEY, base_url="https://api.perplexity.ai")
    try:
        completion_params = {
            "model": model,
            "messages": messages_for_llm,
            "temperature": temperature,
        }
        if max_tokens:
            completion_params["max_tokens"] = max_tokens

        # print(f"    [LLM HELPER] About to call Perplexity API. Model: {model}. Max Tokens: {max_tokens}. Message sample: {str(messages_for_llm[1]['content'][:100]) if len(messages_for_llm) > 1 else 'N/A'}")
        response = await client.chat.completions.create(**completion_params)
        # print(f"    [LLM HELPER] Perplexity API call successful. Response ID: {response.id if response else 'N/A'}")
        return response.choices[0].message.content
    except Exception as e:
        print(f"    [LLM HELPER (literature_harvester)] Error calling Perplexity API ({model}): {e}")
        if "authentication" in str(e).lower() or "API key" in str(e).lower() or "401" in str(e): # Check for common auth error indicators
             print("    [LLM HELPER (literature_harvester)] This error often indicates an invalid or missing PERPLEXITY_API_KEY.")
        # traceback.print_exc() # Uncomment for full trace during deep debugging
        return None

def parse_llm_json_list_output(llm_response_content: str | None) -> list | None:
    if not llm_response_content:
        # print("  DEBUG (literature_harvester): LLM response content is None or empty for list parsing.")
        return None
        
    json_string_to_parse = ""
    
    # Attempt to remove <think> blocks before further parsing
    cleaned_content = llm_response_content
    think_block_pattern = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
    cleaned_content = think_block_pattern.sub("", cleaned_content).strip()
    # if cleaned_content != llm_response_content:
        # print("  DEBUG (literature_harvester): Removed <think> block(s) from LLM response.")
    
    match_json_block = re.search(r"```json\s*(\[[\s\S]*?\])\s*```", cleaned_content, re.DOTALL)
    if match_json_block:
        json_string_to_parse = match_json_block.group(1)
        # print("  DEBUG (literature_harvester): Extracted JSON list from markdown code block after cleaning.")
    else:
        first_bracket = cleaned_content.find('[')
        last_bracket = cleaned_content.rfind(']')
        if first_bracket != -1 and last_bracket != -1 and last_bracket > first_bracket:
            json_string_to_parse = cleaned_content[first_bracket : last_bracket+1]
            # print("  DEBUG (literature_harvester): Extracted JSON list by finding first '[' and last ']'.")
        elif cleaned_content.strip().startswith('[') and cleaned_content.strip().endswith(']'):
            json_string_to_parse = cleaned_content.strip()
            # print("  DEBUG (literature_harvester): Extracted JSON list because content starts/ends with brackets.")
        else:
            # print(f"  DEBUG (literature_harvester): No clear JSON list structure found after cleaning. Raw cleaned snippet: {cleaned_content[:300]}")
            return None 

    try:
        return json.loads(json_string_to_parse)
    except json.JSONDecodeError as e:
        print(f"  Initial JSON list parsing failed after cleaning. Details: {e}")
        # print(f"  Problematic string snippet for list parsing after cleaning: '{json_string_to_parse[:500]}...'")
        
        # Fallback: Try to extract individual objects
        # print("  Attempting to clean/extract individual JSON objects from the problematic list string (using original problematic string)...")
        # Use json_string_to_parse as it was the target of the failed main parse
        try:
            cleaned_objects = []
            # Using a simpler regex for object extraction, as the more complex one with lookahead might be too strict sometimes.
            object_strs = re.findall(r"({[\s\S]*?})", json_string_to_parse) 

            if object_strs:
                # print(f"    Found {len(object_strs)} potential JSON object strings using regex for fallback.")
                for i, obj_s in enumerate(object_strs):
                    try:
                        obj_s_stripped = obj_s.strip()
                        if '"title":' in obj_s_stripped and ('"doi":' in obj_s_stripped or '"landing_page_url":' in obj_s_stripped):
                            cleaned_objects.append(json.loads(obj_s_stripped))
                        # else:
                            # print(f"    Skipping potential object {i} during fallback: {obj_s_stripped[:100]}...")
                    except json.JSONDecodeError: # Don't print item_e to reduce noise if an object is partial/bad
                        # print(f"    Could not parse individual item {i} during fallback. Snippet: {obj_s[:100]}")
                        continue 
                if cleaned_objects:
                    print(f"  Successfully parsed {len(cleaned_objects)} items using fallback object extraction.")
                    return cleaned_objects
            # else:
                # print("    Fallback regex found no distinct JSON objects within the list string.")
        except Exception as clean_e:
            print(f"    Error during advanced list cleaning fallback: {clean_e}")
            # traceback.print_exc() # Keep for debugging if needed
        
        # print("  Could not recover JSON list after all attempts.")
        return None

def parse_llm_json_object_output(llm_response_content: str | None) -> dict | None:
    # This function can remain largely the same, just ensure it also uses a cleaned_content approach if needed
    if not llm_response_content:
        return None
    
    cleaned_content = llm_response_content
    think_block_pattern = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
    cleaned_content = think_block_pattern.sub("", cleaned_content).strip()

    json_string_to_parse = ""
    match_json_block = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", cleaned_content, re.DOTALL)
    if match_json_block:
        json_string_to_parse = match_json_block.group(1)
    else:
        first_brace = cleaned_content.find('{')
        last_brace = cleaned_content.rfind('}')
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            json_string_to_parse = cleaned_content[first_brace : last_brace+1]
        elif cleaned_content.strip().startswith('{') and cleaned_content.strip().endswith('}'):
            json_string_to_parse = cleaned_content.strip()
        else:
            json_string_to_parse = cleaned_content.strip() # Last resort attempt

    if not json_string_to_parse:
        return None
    try:
        return json.loads(json_string_to_parse)
    except json.JSONDecodeError:
        # print(f"  Error: Could not parse LLM response as JSON object. Snippet: '{json_string_to_parse[:200]}...'")
        return None

# --- AGENT 1 MAIN FUNCTION (STREAMING) ---
async def find_relevant_papers_and_guide_user_stream(
    topic_details: str,
    date_after: str,
    date_before: str,
    max_papers_to_find: int,
    output_metadata_file_path: str
):
    agent1_final_output = {
        "project_topic": topic_details,
        "date_filter_used": f"{date_after} to {date_before}",
        "max_papers_requested": max_papers_to_find,
        "project_keywords": {
            "material_keywords": [], "synthesis_keywords": [],
            "performance_keywords": [], "characterization_keywords": []
        },
        "papers": []
    }
    
    system_prompt_papers = """
You are an AI assistant that returns ONLY a valid JSON list of paper objects.
Your entire response MUST be a single JSON list, starting with '[' and ending with ']'.
Do NOT include any other text, conversational Preamble, explanations, or markdown formatting like ```json before or after the list.
Each object in the list MUST represent a single paper and strictly follow the schema provided.
If no papers are found, or if you cannot reliably extract the information, you MUST return an empty JSON list: [].
Example of expected output format for one paper in a list:
[{"title": "Example Paper Title", "authors": ["Author X", "Author Y"], "publication_year": 2023, "doi": "10.1234/example.doi", "journal_name": "Journal of Examples", "abstract_snippet": "This is a brief snippet...", "relevance_to_query": "This paper is relevant because...", "landing_page_url": "https://doi.org/10.1234/example.doi", "potential_oa_pdf_url": null}]
If there are multiple papers, ensure objects are separated by a comma. If there are no papers, the output is simply: []
""" # Shortened example for brevity, your original was good.
    user_prompt_papers = f"""
Find up to {max_papers_to_find} peer-reviewed academic papers published between {date_after} and {date_before} on the topic: '{topic_details}'.
For each paper, provide a JSON object with these exact keys: "title", "authors", "publication_year", "doi", "journal_name", "abstract_snippet", "relevance_to_query", "landing_page_url", "potential_oa_pdf_url".
If a value for a key is not found, use JSON null. Return ONLY the list of these JSON objects.
"""
    messages_papers = [{"role": "system", "content": system_prompt_papers}, {"role": "user", "content": user_prompt_papers}]

    yield f"🔍 Starting search for papers on topic: '{topic_details}'..."
    await asyncio.sleep(0) 

    # print("--- DEBUG: Prompts for LLM Paper List ---") # Reduce print noise
    # print(f"System Prompt:\n{system_prompt_papers}")
    # print(f"User Prompt:\n{user_prompt_papers}")
    
    raw_llm_paper_list_response = await call_perplexity_llm_helper(messages_papers, model="sonar-deep-research", temperature=0.0)
    
    # print("--- DEBUG: FULL RAW LLM RESPONSE ---") # Reduce print noise
    # print(raw_llm_paper_list_response)
    # print("--- END RAW LLM RESPONSE ---")

    parsed_paper_list_from_llm = []
    if raw_llm_paper_list_response:
        yield "📝 LLM response received, attempting to parse..."
        await asyncio.sleep(0)
        parsed_data = parse_llm_json_list_output(raw_llm_paper_list_response)
        if parsed_data is None:
            yield "⚠️ Could not parse paper list. Proceeding with empty list."
        elif not isinstance(parsed_data, list):
            yield f"⚠️ Parsed output is not a list (type: {type(parsed_data)}). Trying to adapt..."
            if isinstance(parsed_data, dict) and "title" in parsed_data: # Simple check for single paper dict
                parsed_paper_list_from_llm = [parsed_data]
                yield f"✅ Parsed {len(parsed_paper_list_from_llm)} paper candidate(s)."
            else:
                yield "⚠️ Could not interpret non-list paper output. Treating as empty."
        else:
            parsed_paper_list_from_llm = parsed_data
            yield f"✅ Successfully parsed {len(parsed_paper_list_from_llm)} paper candidate(s)."
    else:
        yield "⚠️ No response or error from LLM for paper search. Check API key and service status."
    await asyncio.sleep(0)

    retrieved_papers_metadata = []
    if isinstance(parsed_paper_list_from_llm, list) and parsed_paper_list_from_llm:
        yield f"⚙️ Processing {len(parsed_paper_list_from_llm)} paper(s)..."
        await asyncio.sleep(0)
        for i, item in enumerate(parsed_paper_list_from_llm):
            if not isinstance(item, dict):
                yield f"❗️ Item {i+1} is not a dictionary, skipping."
                continue
            if not item.get("title") or not (item.get("doi") or item.get("landing_page_url")):
                yield f"❗️ Paper '{item.get('title', 'N/A')}' missing essential fields (title/DOI/URL), skipping."
                continue

            paper_info = {
                "id": i + 1,
                "title": item.get("title"), "authors": item.get("authors", []),
                "publication_year": item.get("publication_year"), "doi": item.get("doi"),
                "journal_name": item.get("journal_name"), "abstract_snippet": item.get("abstract_snippet"),
                "relevance_explanation_from_llm": item.get("relevance_to_query"),
                "landing_page_url": item.get("landing_page_url"),
                "potential_oa_pdf_url": item.get("potential_oa_pdf_url"),
                "suggested_filename": None
            }
            if not isinstance(paper_info["authors"], list) and paper_info["authors"] is not None:
                paper_info["authors"] = [str(paper_info["authors"])] # Simplified author handling
            elif paper_info["authors"] is None: paper_info["authors"] = []

            if paper_info["doi"]:
                paper_info["suggested_filename"] = sanitize_doi_for_filename(paper_info["doi"]) + ".pdf"
                if not paper_info["landing_page_url"] or not str(paper_info["landing_page_url"]).startswith("http"):
                    paper_info["landing_page_url"] = f"https://doi.org/{urllib.parse.quote_plus(paper_info['doi'])}"
            
            retrieved_papers_metadata.append(paper_info)
            yield f"📄 Processed: {paper_info['title'][:40]}..."
            await asyncio.sleep(0)
    else:
        yield "ℹ️ No valid papers to process after parsing."
    
    agent1_final_output["papers"] = retrieved_papers_metadata

    try:
        dir_name = os.path.dirname(output_metadata_file_path)
        if dir_name: os.makedirs(dir_name, exist_ok=True)
        
        async with aiofiles.open(output_metadata_file_path, "w", encoding="utf-8") as f: # Use aiofiles for async save
            await f.write(json.dumps(agent1_final_output, indent=2, ensure_ascii=False))
        
        yield f"💾 Metadata for {len(retrieved_papers_metadata)} papers saved to: {os.path.basename(output_metadata_file_path)}"
    except Exception as e_save:
        yield f"❌ Error saving metadata file: {e_save}"
        # traceback.print_exc() # Keep for debugging
    
    yield {"type": "result", "data": agent1_final_output}


# --- AGENT 1 BATCH FUNCTION ---
async def find_relevant_papers_and_guide_user_batch(
    topic_details: str, date_after: str, date_before: str,
    max_papers_to_find: int, output_metadata_file_path: str
):
    final_result = None
    async for item in find_relevant_papers_and_guide_user_stream(
        topic_details, date_after, date_before, max_papers_to_find,
        output_metadata_file_path=output_metadata_file_path
    ):
        if isinstance(item, dict) and item.get("type") == "result":
            final_result = item["data"]
        elif isinstance(item, str):
            # print(f"[Agent1 Batch Log] {item}") # Reduce noise
            pass
    return final_result


# --- MAIN SCRIPT EXECUTION (for local testing if needed) ---
async def main_script_execution():
    # This local testing part should also rely on .env or a local config for API_KEY
    # For simplicity, it will use the YOUR_API_KEY loaded at the top of this module.
    if not YOUR_API_KEY or YOUR_API_KEY == "API_KEY_NOT_SET_IN_ENV":
        print("Local test cannot run: PERPLEXITY_API_KEY is not configured.")
        print("Please set it in your environment or a .env file at the project root.")
        return
        
    print("--- Running Agent 1: Literature Harvester (Local Test) ---")
    # ... (rest of your main_script_execution logic, unchanged) ...
    search_topic = input("Enter your detailed research topic: ")
    if not search_topic:
        search_topic = "development of quantum dot materials for display technologies"
        print(f"No topic entered, using default: '{search_topic}'")

    start_date = input("Enter start date (YYYY-MM-DD, e.g., 2020-01-01) or press Enter for default: ") or "2020-01-01"
    default_end_date = f"{time.strftime('%Y')}-{time.strftime('%m')}-{time.strftime('%d')}"
    end_date = input(f"Enter end date (YYYY-MM-DD, e.g., {default_end_date}) or press Enter for default: ") or default_end_date
    
    try:
        max_papers_input = input("Enter max papers to find (e.g., 5) or press Enter for default (5): ")
        max_papers = int(max_papers_input) if max_papers_input else 5
        if max_papers <=0: max_papers = 5
    except ValueError:
        max_papers = 5
        print("Invalid input for max papers, using default 5.")

    print(f"Agent will search for up to {max_papers} papers.")

    local_test_output_dir = "local_agent1_test_outputs"
    os.makedirs(local_test_output_dir, exist_ok=True)
    sanitized_topic_for_filename = re.sub(r'\W+', '_', search_topic.lower())[:50] 
    test_output_file = os.path.join(local_test_output_dir, f"{sanitized_topic_for_filename}_{DEFAULT_AGENT1_METADATA_BASENAME}")
    print(f"Local test output will be saved to: {test_output_file}")


    # Suggestion for PDF download folder (remains useful for local testing)
    if USER_PDF_DOWNLOAD_FOLDER_SUGGESTION and not os.path.exists(USER_PDF_DOWNLOAD_FOLDER_SUGGESTION):
        try:
            os.makedirs(USER_PDF_DOWNLOAD_FOLDER_SUGGESTION)
            print(f"\nSuggestion: A folder named '{USER_PDF_DOWNLOAD_FOLDER_SUGGESTION}' was created for saving PDFs.")
        except OSError as e:
            print(f"Could not create suggested folder '{USER_PDF_DOWNLOAD_FOLDER_SUGGESTION}': {e}")
    if USER_PDF_DOWNLOAD_FOLDER_SUGGESTION:
        print(f"Please consider saving downloaded PDFs for Agent 2 in '{USER_PDF_DOWNLOAD_FOLDER_SUGGESTION}'.\n")


    print("\n--- Streaming Output from Agent ---")
    final_output_data = None
    try:
        async for message_or_result_item in find_relevant_papers_and_guide_user_stream(
            search_topic,
            date_after=start_date,
            date_before=end_date,
            max_papers_to_find=max_papers,
            output_metadata_file_path=test_output_file
        ):
            if isinstance(message_or_result_item, str):
                print(message_or_result_item)
            elif isinstance(message_or_result_item, dict) and message_or_result_item.get("type") == "result":
                final_output_data = message_or_result_item["data"]
                print("--- End of Streaming ---") # Moved here to signal end of useful stream messages
    except Exception as main_e:
        print(f"MAIN TEST EXECUTION ERROR: {main_e}")
        traceback.print_exc()


    if final_output_data and final_output_data.get("papers"):
        print(f"\nAgent 1 local test finished. {len(final_output_data['papers'])} paper(s) suggested.")
    else:
        print("\nAgent 1 local test finished. No papers found/suggested or an error occurred.")


if __name__ == "__main__":
    # Ensure aiofiles is imported if you use it for saving in find_relevant_papers_and_guide_user_stream
    try:
        import aiofiles
    except ImportError:
        print("Please install aiofiles for async file operations: pip install aiofiles")
        # Fallback or error if aiofiles is critical for operation. 
        # The current find_relevant_papers... uses synchronous open for saving, which can block.
        # For the main_script_execution, if output_metadata_file_path is used by the stream function
        # ensure that function handles file I/O appropriately (async or sync in thread).
        # I've updated find_relevant_papers_and_guide_user_stream to use aiofiles.
    
    asyncio.run(main_script_execution())