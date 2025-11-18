"""
Process extracted texts from triad_1 using OpenAI to extract structured information.
Extracts title, authors, and main body from critique and response documents.
"""
from openai import OpenAI
from pathlib import Path
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def load_extracted_text(json_path: Path) -> str:
    """
    Load extracted text from a JSON file.

    Args:
        json_path: Path to the JSON file containing extracted text

    Returns:
        The text content
    """
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return data.get('text', '')


def process_with_openai(text: str, source_file: str, api_key: str) -> dict:
    """
    Use OpenAI to extract structured information from text.

    Args:
        text: The text to process
        source_file: Name of the source file
        api_key: OpenAI API key

    Returns:
        Dictionary containing extracted structure
    """
    client = OpenAI(api_key=api_key)

    prompt = """
The text below may contain multiple short scientific letters or replies merged together.
For each distinct article, extract:
- title
- authors (as a comma-separated string)
- main body text

Return JSON array with one object per article.

Format:
{
    "articles": [
        {
            "title": "extracted title",
            "authors": "author1, author2, author3",
            "body": "main body text"
        }
    ]
}

If there is only one article, return an array with one object.
Make sure the JSON is valid and properly formatted.

Text:
""" + text

    print(f"  Calling OpenAI API (gpt-4o-mini)...")

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        response_format={"type": "json_object"}
    )

    result_text = response.choices[0].message.content

    # Parse the JSON response
    try:
        result = json.loads(result_text)
    except json.JSONDecodeError as e:
        print(f"  Warning: Failed to parse JSON response: {e}")
        result = {"articles": [], "error": str(e), "raw_response": result_text}

    # Add metadata
    result['source_file'] = source_file
    result['model'] = 'gpt-4o-mini'
    result['input_length'] = len(text)

    return result


def process_triad_texts(triad_dir: Path, api_key: str):
    """
    Process all extracted text files from triad_1 directory.

    Args:
        triad_dir: Path to the triad directory
        api_key: OpenAI API key
    """
    # Define paths
    extracted_texts_dir = triad_dir / "extracted_texts"
    output_dir = triad_dir / "openai_structured"

    # Check if extracted texts directory exists
    if not extracted_texts_dir.exists():
        print(f"Error: {extracted_texts_dir} does not exist")
        print("Please run extract_text_from_pdf.py first to extract text from PDFs")
        return

    # Find all text JSON files (critique and response)
    text_files = list(extracted_texts_dir.glob("*_text.json"))

    if not text_files:
        print(f"No text files found in {extracted_texts_dir}")
        return

    print(f"Found {len(text_files)} text file(s) to process\n")

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    results = {}

    for text_file in text_files:
        print(f"Processing: {text_file.name}")

        # Load extracted text
        text = load_extracted_text(text_file)
        print(f"  Text length: {len(text)} characters")

        # Process with OpenAI
        try:
            structured_data = process_with_openai(text, text_file.name, api_key)

            # Save structured data
            output_filename = text_file.stem.replace('_text', '_structured') + '.json'
            output_path = output_dir / output_filename

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(structured_data, f, ensure_ascii=False, indent=2)

            print(f"  ✓ Saved to: {output_path}")

            # Print summary
            articles = structured_data.get('articles', [])
            print(f"  Found {len(articles)} article(s)")
            for i, article in enumerate(articles, 1):
                title = article.get('title', 'N/A')
                authors = article.get('authors', 'N/A')
                body_len = len(article.get('body', ''))
                print(f"    Article {i}:")
                print(f"      Title: {title[:70]}..." if len(title) > 70 else f"      Title: {title}")
                print(f"      Authors: {authors[:70]}..." if len(authors) > 70 else f"      Authors: {authors}")
                print(f"      Body length: {body_len} characters")

            results[text_file.name] = structured_data
            print()

        except Exception as e:
            print(f"  ✗ Error processing {text_file.name}: {e}\n")
            continue

    print("="*60)
    print(f"✓ Successfully processed {len(results)}/{len(text_files)} file(s)")
    print(f"✓ Output saved to: {output_dir}")
    print("="*60)

    return results


if __name__ == "__main__":
    # Get API key from environment variable
    api_key = os.environ.get("OPENAI_API_KEY")

    if not api_key:
        print("Error: OPENAI_API_KEY not set")
        print("\nTo set your API key:")
        print("1. Environment variable: export OPENAI_API_KEY='your-key-here'")
        print("2. Create .env file with: OPENAI_API_KEY=your-key-here")
        exit(1)

    # Define triad_1 directory
    triad_1_dir = Path("data/triad_samples/triad_1")

    if not triad_1_dir.exists():
        print(f"Error: {triad_1_dir} does not exist")
        exit(1)

    # Process texts
    print("="*60)
    print("Processing triad_1 extracted texts with OpenAI")
    print("="*60)
    print()

    process_triad_texts(triad_1_dir, api_key)
