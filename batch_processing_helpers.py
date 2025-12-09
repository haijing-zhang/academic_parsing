"""
Batch processing helper functions for the new folder structure.
These are adapted versions of existing functions that work with:
- raw_data/
- intermediate_results/
- final_outputs/
"""

from pathlib import Path
import json
from typing import Dict, Optional
from openai import OpenAI


def load_json_file(file_path: Path) -> dict:
    """Load JSON file and return its contents."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_extracted_text(json_path: Path) -> str:
    """Load extracted text from a JSON file."""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return data.get('text', '')


def process_with_openai(text: str, source_file: str, api_key: str, max_retries: int = 3) -> dict:
    """
    Use OpenAI to extract structured information from text.

    Args:
        text: The text to process
        source_file: Name of the source file
        api_key: OpenAI API key
        max_retries: Maximum number of retry attempts for API calls

    Returns:
        Dictionary containing extracted structure
    """
    client = OpenAI(api_key=api_key)

    prompt = """
The text below may contain multiple short scientific letters or replies merged together.
For each distinct article, extract:
- title
- authors (as a comma-separated string)
- main body text (KEEP ALL IN-TEXT CITATIONS INTACT, e.g., (Author, Year) or [1])
- references (list of reference strings from the bibliography/reference section)

**CRITICAL REQUIREMENT - REFERENCES ARE MANDATORY:**
- Each article MUST include a "references" field
- The "references" field must contain a list (array) of all reference strings found in the bibliography/reference section of that article
- Even if the article has no references, include an empty list: "references": []
- References are typically found at the end of each article in sections labeled "References", "Bibliography", "Works Cited", etc.
- Extract the complete reference string for each citation (e.g., "Smith, J. (2020). Title of paper. Journal Name, 15(3), 123-145.")
- DO NOT skip or omit the references field - it is essential for downstream processing

Return the data as a JSON object with this structure:
{
  "articles": [
    {
      "title": "...",
      "authors": "...",
      "body": "...",
      "references": ["ref1", "ref2", ...]
    }
  ]
}

If there's only one article, still use the list format.
Remember: Every article object MUST have a "references" field!
Ensure all string values are properly escaped (quotes, newlines, backslashes).

Text:
"""

    # Retry loop to handle transient errors and malformed JSON
    result_text = None
    for attempt in range(max_retries):
        try:
            # On first attempt, use normal prompt
            # On retry after truncation, use concise mode
            current_prompt = prompt + text
            current_max_tokens = 16000

            if attempt > 0 and hasattr(process_with_openai, '_last_truncated'):
                # Retry with instructions to be more concise
                current_prompt = """
The text below may contain multiple short scientific letters or replies merged together.
For each distinct article, extract:
- title
- authors (as a comma-separated string)
- main body text (KEEP IN-TEXT CITATIONS, but SUMMARIZE to fit within token limits)
- references (list of reference strings from the bibliography/reference section)

**CRITICAL - DUE TO LENGTH CONSTRAINTS:**
- Every article MUST have a "references" field (array of reference strings)
- SUMMARIZE the body text while keeping essential citations
- Prioritize completeness over detail - include ALL articles even if body is brief
- Extract complete reference list for each article

Return JSON:
{
  "articles": [
    {
      "title": "...",
      "authors": "...",
      "body": "... (summarized with key citations)",
      "references": ["ref1", "ref2", ...]
    }
  ]
}

Text:
""" + text
                current_max_tokens = 16000 
                print(f"  Retrying with concise mode and higher token limit...")

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that extracts structured information from scientific text. Always preserve in-text citations exactly as they appear. IMPORTANT: Every article must include a 'references' field with all bibliography entries - this is mandatory. Ensure all JSON strings are properly escaped."},
                    {"role": "user", "content": current_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=current_max_tokens
            )

            result_text = response.choices[0].message.content

            # Check if response was truncated
            if response.choices[0].finish_reason == 'length':
                print(f"  ⚠ Warning: Response truncated (hit token limit at {current_max_tokens} tokens)")

                # Mark for retry with concise mode
                if attempt < max_retries - 1:
                    process_with_openai._last_truncated = True
                    print(f"  Will retry with summarization strategy...")
                    continue  # Retry with concise prompt
                else:
                    print(f"  ⚠ Proceeding with truncated response (may be incomplete)")
            else:
                # Clear truncation flag on success
                if hasattr(process_with_openai, '_last_truncated'):
                    delattr(process_with_openai, '_last_truncated')

            break  # Success, exit retry loop

        except Exception as e:
            error_msg = str(e)
            print(f"  ⚠ API call attempt {attempt + 1}/{max_retries} failed: {e}")

            if attempt < max_retries - 1:
                import time
                import re

                # Check if it's a rate limit error
                if 'rate limit' in error_msg.lower():
                    # Try to extract wait time from error message
                    # Pattern: "Please try again in 46ms" or "Please try again in 2.5s"
                    wait_match = re.search(r'try again in (\d+(?:\.\d+)?)(ms|s)', error_msg)

                    if wait_match:
                        wait_value = float(wait_match.group(1))
                        wait_unit = wait_match.group(2)

                        # Convert to seconds
                        if wait_unit == 'ms':
                            wait_time = wait_value / 1000.0
                        else:
                            wait_time = wait_value

                        # Add small buffer
                        wait_time += 0.5
                        print(f"  Rate limit hit - waiting {wait_time:.2f} seconds as suggested...")
                    else:
                        # Default wait for rate limits
                        wait_time = 5
                        print(f"  Rate limit hit - waiting {wait_time} seconds...")
                else:
                    # Standard exponential backoff for other errors
                    wait_time = 2 ** attempt  # 1s, 2s, 4s
                    print(f"  Retrying in {wait_time} seconds...")

                time.sleep(wait_time)
            else:
                # All retries exhausted, return error structure
                print(f"  ❌ All retry attempts failed")
                return {
                    "articles": [],
                    "source_file": source_file,
                    "model": "gpt-4o",
                    "input_length": len(text),
                    "error": str(e)
                }

    # Parse the JSON response with robust error handling
    try:
        result = json.loads(result_text)
    except json.JSONDecodeError as e:
        print(f"  ⚠ Warning: Failed to parse JSON response: {e}")
        print(f"  Error details: {e.msg} at position {e.pos}")

        # Try to salvage partial JSON by fixing common issues
        try:
            # Attempt 1: Fix unterminated strings by adding closing quotes/braces
            fixed_text = result_text
            if not fixed_text.rstrip().endswith('}'):
                # Try to close incomplete JSON
                fixed_text = result_text.rstrip().rstrip(',') + ']}}'
            result = json.loads(fixed_text)
            print(f"  ✓ Successfully recovered JSON by adding missing closing braces")
        except:
            # Attempt 2: Use regex to extract whatever valid JSON we can
            import re
            try:
                # Try to find the articles array even if JSON is incomplete
                articles_match = re.search(r'"articles"\s*:\s*\[(.*)\]', result_text, re.DOTALL)
                if articles_match:
                    # Manually construct a minimal valid response
                    result = {
                        "articles": [],
                        "error": f"Partial parse after error: {str(e)}",
                        "raw_response": result_text[:1000]  # Truncate for debugging
                    }
                    print(f"  ⚠ Could not recover full JSON, returning empty articles")
                else:
                    result = {"articles": [], "error": str(e), "raw_response": result_text[:1000]}
            except:
                result = {"articles": [], "error": str(e), "raw_response": result_text[:1000]}

    # Add metadata
    result['source_file'] = source_file
    result['model'] = 'gpt-4o'
    result['input_length'] = len(text)

    return result


def process_triad_texts_batch(triad_dir: Path, api_key: str) -> Dict[str, Dict]:
    """
    Process extracted texts with OpenAI for batch processing.
    Reads from intermediate_results/extracted_texts/
    Writes to intermediate_results/openai_structured/

    Args:
        triad_dir: Path to triad directory (with new structure)
        api_key: OpenAI API key

    Returns:
        Dictionary with processing results
    """
    print("="*70)
    print("Processing Texts with OpenAI (Batch Mode)")
    print("="*70)
    print()

    extracted_texts_dir = triad_dir / "intermediate_results" / "extracted_texts"
    output_dir = triad_dir / "intermediate_results" / "openai_structured"
    output_dir.mkdir(parents=True, exist_ok=True)

    if not extracted_texts_dir.exists():
        print(f"❌ Extracted texts directory not found: {extracted_texts_dir}")
        return {}

    # Find text files
    text_files = list(extracted_texts_dir.glob("*_text.json"))

    if not text_files:
        print(f"❌ No text files found in {extracted_texts_dir}")
        return {}

    print(f"Found {len(text_files)} text file(s) to process\n")

    results = {}

    for text_file in text_files:
        print(f"Processing: {text_file.name}")

        # Determine type (critique or response)
        if 'critique' in text_file.name:
            doc_type = 'critique'
        elif 'response' in text_file.name:
            doc_type = 'response'
        else:
            print(f"  ⚠️ Skipping unknown file type")
            continue

        # Load text
        text = load_extracted_text(text_file)
        print(f"  Text length: {len(text):,} characters")

        # Process with OpenAI
        print(f"  Calling OpenAI API...")
        structured_data = process_with_openai(text, text_file.name, api_key)

        # Save result
        output_file = output_dir / f"{doc_type}_{text_file.stem.split('_')[1]}_structured.json"

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(structured_data, f, ensure_ascii=False, indent=2)

        article_count = len(structured_data.get('articles', []))
        print(f"  ✓ Extracted {article_count} article(s)")
        print(f"  ✓ Saved to: {output_file.name}\n")

        results[doc_type] = {
            'output_file': output_file,
            'article_count': article_count
        }

    print("="*70)
    print(f"✓ Processed {len(results)} file(s)")
    print(f"✓ Output directory: {output_dir}")
    print("="*70 + "\n")

    return results
