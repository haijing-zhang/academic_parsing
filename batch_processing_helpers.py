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


def process_with_openai(text: str, source_file: str, api_key: str) -> dict:
    """Use OpenAI to extract structured information from text."""
    client = OpenAI(api_key=api_key)

    prompt = """
The text below may contain multiple short scientific letters or replies merged together.
For each distinct article, extract:
- title
- authors (as a comma-separated string)
- main body text (KEEP ALL IN-TEXT CITATIONS INTACT, e.g., (Author, Year) or [1])
- references (list of reference strings from the bibliography/reference section)

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

Text:
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that extracts structured information from scientific text. Always preserve in-text citations exactly as they appear."},
                {"role": "user", "content": prompt + text}
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )

        result = json.loads(response.choices[0].message.content)

        # Add metadata
        result['source_file'] = source_file
        result['model'] = 'gpt-4o'
        result['input_length'] = len(text)

        return result

    except Exception as e:
        print(f"Error during OpenAI processing: {e}")
        return {
            "articles": [],
            "source_file": source_file,
            "model": "gpt-4o",
            "input_length": len(text),
            "error": str(e)
        }


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
