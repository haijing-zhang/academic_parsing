# Triad Processing Workflow

Complete automated workflow for processing academic paper triads (original paper, critique, and response).

## Overview

This workflow processes academic paper triads through 5 sequential steps:

1. **Generate XML** from original paper PDF using GROBID
2. **Extract metadata** (title, authors, abstract) from XML
3. **Extract text** from critique and response PDFs
4. **Structure data** using OpenAI to parse multiple articles
5. **Analyze relationships** to identify truly related papers

## Directory Structure

Each triad should follow this structure:

```
triad_samples/triad_N/
├── original_*.pdf                    # Original paper PDF (input)
├── critique_*.pdf                    # Critique paper PDF (input)
├── response_*.pdf                    # Response paper PDF (input)
├── output_orginal_*.xml              # Generated XML (step 1)
├── original_info_from_xml.json       # Extracted metadata (step 2)
├── extracted_texts/                  # PDF text extracts (step 3)
│   ├── critique_*_text.json
│   └── response_*_text.json
├── openai_structured/                # Structured data (step 4)
│   ├── critique_*_structured.json
│   └── response_*_structured.json
└── relationship_analysis/            # Final analysis (step 5)
    └── triad_relationship_analysis.json
```

## Prerequisites

1. **GROBID Service**: Must be running on `http://localhost:8070`
   ```bash
   # Start GROBID using Docker
   docker run -p 8070:8070 lfoppiano/grobid:0.8.0
   ```

2. **OpenAI API Key**: Set in environment
   ```bash
   export OPENAI_API_KEY='your-key-here'
   # or create a .env file with:
   # OPENAI_API_KEY=your-key-here
   ```

3. **Python Dependencies**:
   ```bash
   pip install openai python-dotenv pdfminer.six
   ```

## Usage

### Process a Single Triad

```bash
# Process triad_1 (default)
python process_triad_workflow.py

# Process a specific triad
python process_triad_workflow.py --triad-dir data/triad_samples/triad_1

# Start from a specific step (e.g., skip step 1 if XML already exists)
python process_triad_workflow.py --triad-dir data/triad_samples/triad_1 --start-from 2
```

### Process All Triads

```bash
# Process all triads in triad_samples/
python process_triad_workflow.py --all

# Process all triads starting from step 3
python process_triad_workflow.py --all --start-from 3
```

### Custom GROBID URL

```bash
python process_triad_workflow.py --grobid-url http://your-server:8070
```

## Step-by-Step Details

### Step 1: Generate XML from PDF

Calls GROBID service to convert original paper PDF to structured XML:

```bash
curl -v --form input=@original_W2795732318.pdf \
     "http://localhost:8070/api/processFulltextDocument" \
     -o output_orginal_W2795732318.xml
```

**Output**: `output_orginal_*.xml`

### Step 2: Extract Metadata from XML

Parses XML to extract:
- Title
- Authors
- Abstract

Uses `src/pdf_extract/xml_preprocessor.py`

**Output**: `original_info_from_xml.json`

Example:
```json
{
  "title": "Historical perspective: 10th year anniversary of TAVI",
  "authors": "Armoiry, Xavier, Jean-François Obadia, ...",
  "abstract": "Objective: To compare the clinical outcomes...",
  "source_file": "output_orginal_W2795732318.xml"
}
```

### Step 3: Extract Text from PDFs

Extracts raw text from critique and response PDFs using `pdfminer.six`.

Uses `extract_text_from_pdf.py`

**Output**: `extracted_texts/critique_*_text.json`, `extracted_texts/response_*_text.json`

### Step 4: Structure with OpenAI

Uses OpenAI GPT-4o-mini to parse extracted text and identify multiple articles within each PDF.

Extracts for each article:
- Title
- Authors
- Main body text

Uses `process_triad_with_openai.py`

**Output**: `openai_structured/critique_*_structured.json`, `openai_structured/response_*_structured.json`

Example:
```json
{
  "articles": [
    {
      "title": "Reply to criticism",
      "authors": "Smith, John, Doe, Jane",
      "body": "We appreciate the comments..."
    }
  ],
  "source_file": "critique_W2901912159_text.json",
  "model": "gpt-4o-mini"
}
```

### Step 5: Analyze Relationships

Uses OpenAI to analyze which critiques and responses are truly related to the original paper.

Checks for:
- Author overlap (response authors should match original authors)
- Content relevance
- Whether response explicitly replies to critique

Uses `analyze_triad_relationships.py`

**Output**: `relationship_analysis/triad_relationship_analysis.json`

Example:
```json
{
  "related_critiques": [
    {
      "title": "Concerns about TAVI study methodology",
      "authors": "Reviewer A, Reviewer B",
      "body": "We have concerns about..."
    }
  ],
  "related_responses": [
    {
      "title": "Response to concerns",
      "authors": "Armoiry, Xavier, Jean-François Obadia",
      "body": "We thank the reviewers..."
    }
  ],
  "talk_to_each_other": true,
  "explanation": "Response authors match original paper authors and explicitly address critique points.",
  "flag": null
}
```

## Individual Script Usage

You can also run each step independently:

```bash
# Step 1: Generate XML (manual curl command)
curl -v --form input=@original_*.pdf \
     "http://localhost:8070/api/processFulltextDocument" \
     -o output_orginal_*.xml

# Step 2: Extract metadata
python src/pdf_extract/xml_preprocessor.py

# Step 3: Extract text from PDFs
python extract_text_from_pdf.py

# Step 4: Structure with OpenAI
python process_triad_with_openai.py

# Step 5: Analyze relationships
python analyze_triad_relationships.py
```

## Command-Line Arguments

```
--triad-dir PATH      Path to specific triad directory
--all                 Process all triads in data/triad_samples
--start-from N        Start from step N (1-5). Skip earlier steps if already completed
--grobid-url URL      GROBID service URL (default: http://localhost:8070)
```

## Error Handling

The workflow:
- Checks for existing files and skips regeneration
- Validates each step before proceeding
- Provides detailed error messages
- Returns appropriate exit codes

## Output Files Summary

| File | Description | Generator |
|------|-------------|-----------|
| `output_orginal_*.xml` | GROBID XML output | GROBID service |
| `original_info_from_xml.json` | Original paper metadata | xml_preprocessor.py |
| `extracted_texts/*_text.json` | Raw PDF text | extract_text_from_pdf.py |
| `openai_structured/*_structured.json` | Parsed articles | process_triad_with_openai.py |
| `relationship_analysis/triad_relationship_analysis.json` | Final analysis | analyze_triad_relationships.py |

## Notes

- The workflow preserves intermediate results, so you can restart from any step
- Step 1 requires GROBID service to be running
- Steps 4-5 require OpenAI API key
- Processing time varies based on PDF size and OpenAI API response time
- All JSON files use UTF-8 encoding with proper formatting

## Troubleshooting

**GROBID Connection Error**:
```bash
# Check if GROBID is running
curl http://localhost:8070/api/isalive

# Start GROBID if not running
docker run -p 8070:8070 lfoppiano/grobid:0.8.0
```

**OpenAI API Error**:
```bash
# Verify API key is set
echo $OPENAI_API_KEY

# Set it if missing
export OPENAI_API_KEY='your-key-here'
```

**Missing Dependencies**:
```bash
pip install -r requirements.txt
```
