# Batch Processing Guide

This guide explains how to process all 100 triads from `sample.csv` using the new batch processing workflow.

## New Folder Structure

Each triad now uses this organized structure:

```
data/triad_samples_batch/
├── triad_6925/              # Named by CSV index
│   ├── raw_data/            # Original input files
│   │   ├── original_*.pdf
│   │   ├── critique_*.pdf
│   │   ├── response_*.pdf
│   │   └── metadata.json    # Contains CSV row data + ground truth label
│   ├── intermediate_results/  # All processing intermediates
│   │   ├── output_orginal_*.xml
│   │   ├── original_info_from_xml.json
│   │   ├── extracted_texts/
│   │   │   ├── critique_*_text.json
│   │   │   └── response_*_text.json
│   │   ├── openai_structured/
│   │   │   ├── critique_*_structured.json
│   │   │   └── response_*_structured.json
│   │   └── relationship_analysis/
│   │       └── triad_relationship_analysis.json
│   └── final_outputs/       # Final deliverables
│       ├── original_paper_final.json
│       ├── critique_final.json
│       ├── response_final.json
│       └── summary.json     # Contains prediction_label + ground_truth_label
```

## Key Features

### 1. Resume Capability
- Automatically skips triads that already have `final_outputs/summary.json`
- Safe to interrupt and restart processing

### 2. Ground Truth Labels
- Automatically reads `status_label` from CSV
- Stored in `raw_data/metadata.json`
- Included in `summary.json` as `ground_truth_label`

### 3. Quality Prediction
- Pipeline generates `prediction_label` (P/B/IV)
- Compared against `ground_truth_label` in summary

## Usage

### Prerequisites

```bash
# 1. Install dependencies
pip install openai python-dotenv

# 2. Set OpenAI API key
export OPENAI_API_KEY='your-key-here'
# or create .env file with: OPENAI_API_KEY=your-key-here

# 3. Start GROBID service
docker run -p 8070:8070 lfoppiano/grobid:0.8.0
```

### Batch Processing

#### Process All 100 Triads

```bash
python process_batch_triads.py \
  --csv data/sample.csv \
  --output-dir data/triad_samples_batch \
  --pdfs-dir data/pdfs
```

#### Process Subset (e.g., first 10)

```bash
python process_batch_triads.py \
  --csv data/sample.csv \
  --output-dir data/triad_samples_batch \
  --pdfs-dir data/pdfs \
  --start-from 0 \
  --limit 10
```

#### Resume After Interruption

Simply run the same command again - already processed triads will be skipped:

```bash
python process_batch_triads.py \
  --csv data/sample.csv \
  --output-dir data/triad_samples_batch \
  --pdfs-dir data/pdfs
```

#### Custom GROBID URL

```bash
python process_batch_triads.py \
  --csv data/sample.csv \
  --output-dir data/triad_samples_batch \
  --pdfs-dir data/pdfs \
  --grobid-url http://localhost:8080
```

## Important Notes

### PDF Requirements

**PDFs are automatically copied from the `data/pdfs/` folder:**

The script automatically:
1. Reads work IDs from the CSV (work_id_original, work_id_critique, work_id_response)
2. Looks for corresponding PDFs in `data/pdfs/` (e.g., W1974155836.pdf)
3. Copies them to each triad's `raw_data/` folder with appropriate names:
   - `original_{work_id}.pdf`
   - `critique_{work_id}.pdf`
   - `response_{work_id}.pdf`

**The script will skip triads that don't have all 3 PDFs available in the pdfs directory.**

If you have PDFs in a different location, use the `--pdfs-dir` flag:
```bash
python process_batch_triads.py \
  --csv data/sample.csv \
  --output-dir data/triad_samples_batch \
  --pdfs-dir /path/to/your/pdfs
```

### Summary Output Format

The `final_outputs/summary.json` now includes both labels:

```json
{
  "quality": {
    "prediction_label": "B",
    "ground_truth_label": "B",
    "explanation": "PDFs contain extra articles (Critique: 1/2, Response: 1/2)"
  },
  "summary": {
    "papers_talking_to_each_other": true,
    "flag": null,
    "explanation": "..."
  },
  ...
}
```

## Workflow Steps

For each triad, the pipeline:

1. **Step 1**: Generate XML from original PDF using GROBID
2. **Step 2**: Extract metadata from XML
3. **Step 3**: Extract text from critique/response PDFs
4. **Step 4**: Structure texts with OpenAI (GPT-4)
5. **Step 5**: Analyze relationships between papers
6. **Step 6**: Generate final outputs with labels

## Output Summary

After processing, you'll see:

```
BATCH PROCESSING SUMMARY
======================================================================
Total records: 100
Successfully processed: 85
Skipped (already done): 10
Failed: 5
======================================================================
```

## Troubleshooting

### No PDFs Found
```
⚠️  Warning: Only 0 PDF(s) found in raw_data/
Skipping processing - please add PDFs manually
```
**Solution**: Add the 3 required PDFs to `raw_data/` folder

### GROBID Timeout
```
❌ GROBID request timed out after 5 minutes
```
**Solution**: Check GROBID is running, increase timeout if needed

### OpenAI API Error
```
❌ Error during OpenAI processing: ...
```
**Solution**: Check API key, rate limits, or network connection

## File Comparison

### Old Structure vs New Structure

**Old (single triad)**:
```
triad_1/
├── original_*.pdf
├── critique_*.pdf
├── response_*.pdf
├── output_orginal_*.xml
├── original_info_from_xml.json
├── extracted_texts/
├── openai_structured/
├── relationship_analysis/
└── final_outputs/
```

**New (batch processing)**:
```
triad_6925/
├── raw_data/              # 🆕 Organized inputs
│   ├── *.pdf (3 files)
│   └── metadata.json      # 🆕 Includes ground truth
├── intermediate_results/  # 🆕 All intermediates
│   ├── *.xml
│   ├── *.json
│   ├── extracted_texts/
│   ├── openai_structured/
│   └── relationship_analysis/
└── final_outputs/
    └── summary.json       # 🆕 prediction + ground truth
```

## Scripts Overview

- `process_batch_triads.py`: Main batch processor
- `triad_processor_batch.py`: Workflow orchestration
- `batch_processing_helpers.py`: OpenAI processing helpers
- `generate_final_outputs_batch.py`: Final output generation
- Original scripts remain unchanged for single-triad use
