"""
Generate final output files for the triad analysis pipeline.

This script creates:
1. Original paper final output with all academic sections
2. Separate final output files for critique and response papers
3. Summary file with analysis metadata and flags
"""
from pathlib import Path
import json
from typing import Dict, Optional
import os
from dotenv import load_dotenv
from xml_preprocessor import extract_metadata_from_xml

# Load environment variables
load_dotenv()


def load_json_file(file_path: Path) -> dict:
    """Load JSON file and return its contents."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def generate_original_paper_output(triad_dir: Path) -> Optional[Dict]:
    """
    Generate final output for the original paper with all sections.

    Args:
        triad_dir: Path to the triad directory

    Returns:
        Dictionary containing the complete original paper data
    """
    print("Generating original paper output...")

    # Find the XML file
    xml_files = list(triad_dir.glob("output_orginal_*.xml"))

    if not xml_files:
        print(f"  ❌ No original XML file found in {triad_dir}")
        return None

    xml_path = xml_files[0]
    print(f"  Processing: {xml_path.name}")

    # Extract full content with sections and references
    original_data = extract_metadata_from_xml(xml_path, include_full_content=True)

    print(f"  ✓ Extracted {len(original_data.get('sections', {}))} sections")
    print(f"  ✓ Extracted {len(original_data.get('references', []))} references")

    return original_data


def generate_critique_response_outputs(triad_dir: Path, analysis_data: Dict) -> Dict[str, Dict]:
    """
    Generate final outputs for critique and response papers.
    Only includes RELATED articles from the relationship analysis,
    enriched with their full reference lists from the structured data.

    Args:
        triad_dir: Path to the triad directory
        analysis_data: Relationship analysis data containing related articles

    Returns:
        Dictionary with 'critique' and 'response' keys containing their data,
        plus metadata about total vs related counts
    """
    print("\nGenerating critique and response outputs (related articles only)...")

    outputs = {}
    openai_structured_dir = triad_dir / "openai_structured"

    if not openai_structured_dir.exists():
        print(f"  ❌ Structured data directory not found: {openai_structured_dir}")
        return outputs

    # Get related articles from analysis
    related_critiques = analysis_data.get('related_critiques', [])
    related_responses = analysis_data.get('related_responses', [])

    # Load critique data
    critique_files = list(openai_structured_dir.glob("critique_*_structured.json"))
    if critique_files:
        critique_data = load_json_file(critique_files[0])
        total_critiques = len(critique_data.get('articles', []))

        # Enrich related critiques with references from structured data
        enriched_critiques = []
        for related_article in related_critiques:
            # Find matching article in structured data by title
            matching_article = next(
                (article for article in critique_data.get('articles', [])
                 if article.get('title') == related_article.get('title')),
                None
            )
            if matching_article:
                # Create enriched article with references
                enriched_article = related_article.copy()
                enriched_article['references'] = matching_article.get('references', [])
                enriched_critiques.append(enriched_article)
            else:
                # If no match found, keep original (shouldn't happen)
                enriched_critiques.append(related_article)

        # Store only related critiques with references
        outputs['critique'] = {
            'articles': enriched_critiques,
            'source_file': critique_data.get('source_file', ''),
            'model': critique_data.get('model', ''),
            'input_length': critique_data.get('input_length', 0)
        }
        print(f"  ✓ Loaded critique data: {len(enriched_critiques)} related / {total_critiques} total article(s)")
        outputs['critique_total_count'] = total_critiques
        outputs['critique_related_count'] = len(enriched_critiques)
    else:
        print("  ⚠ No critique structured file found")
        outputs['critique'] = {"articles": []}
        outputs['critique_total_count'] = 0
        outputs['critique_related_count'] = 0

    # Load response data
    response_files = list(openai_structured_dir.glob("response_*_structured.json"))
    if response_files:
        response_data = load_json_file(response_files[0])
        total_responses = len(response_data.get('articles', []))

        # Enrich related responses with references from structured data
        enriched_responses = []
        for related_article in related_responses:
            # Find matching article in structured data by title
            matching_article = next(
                (article for article in response_data.get('articles', [])
                 if article.get('title') == related_article.get('title')),
                None
            )
            if matching_article:
                # Create enriched article with references
                enriched_article = related_article.copy()
                enriched_article['references'] = matching_article.get('references', [])
                enriched_responses.append(enriched_article)
            else:
                # If no match found, keep original (shouldn't happen)
                enriched_responses.append(related_article)

        # Store only related responses with references
        outputs['response'] = {
            'articles': enriched_responses,
            'source_file': response_data.get('source_file', ''),
            'model': response_data.get('model', ''),
            'input_length': response_data.get('input_length', 0)
        }
        print(f"  ✓ Loaded response data: {len(enriched_responses)} related / {total_responses} total article(s)")
        outputs['response_total_count'] = total_responses
        outputs['response_related_count'] = len(enriched_responses)
    else:
        print("  ⚠ No response structured file found")
        outputs['response'] = {"articles": []}
        outputs['response_total_count'] = 0
        outputs['response_related_count'] = 0

    return outputs


def generate_summary_file(triad_dir: Path, original_data: Dict,
                         critique_response_outputs: Dict, analysis_data: Dict) -> Optional[Dict]:
    """
    Generate summary file with all metadata and analysis results.
    Includes quality label (P/B/IV) based on relationship analysis.

    Quality Labels:
    - P (Perfect): Papers are talking to each other AND all extracted articles are related
    - B (Broken): Papers are talking but PDFs contain extra unrelated articles (need parsing)
    - IV (Invalid): Papers are not talking to each other

    Args:
        triad_dir: Path to the triad directory
        original_data: Original paper data
        critique_response_outputs: Critique and response data with counts
        analysis_data: Relationship analysis data

    Returns:
        Summary dictionary
    """
    print("\nGenerating summary file...")

    # Load ground truth label from metadata.json
    metadata_file = triad_dir / "metadata.json"
    ground_truth_label = None

    if metadata_file.exists():
        try:
            metadata = load_json_file(metadata_file)
            ground_truth_label = metadata.get('csv_row', {}).get('status_label')
            if ground_truth_label:
                print(f"  Ground Truth Label: {ground_truth_label}")
        except Exception as e:
            print(f"  Warning: Could not load ground truth label from metadata.json: {e}")

    # Get metadata counts
    papers_talking = analysis_data.get('talk_to_each_other', False)
    critique_total = critique_response_outputs.get('critique_total_count', 0)
    critique_related = critique_response_outputs.get('critique_related_count', 0)
    response_total = critique_response_outputs.get('response_total_count', 0)
    response_related = critique_response_outputs.get('response_related_count', 0)

    # Determine quality label (prediction)
    if not papers_talking:
        quality_label = "IV"  # Invalid - not talking to each other
        quality_explanation = "Papers are not debating with one another"
    elif critique_related < critique_total or response_related < response_total:
        quality_label = "B"  # Broken - PDFs contain extra articles
        quality_explanation = f"PDFs contain extra articles (Critique: {critique_related}/{critique_total}, Response: {response_related}/{response_total})"
    else:
        quality_label = "P"  # Perfect - clean and complete
        quality_explanation = "PDFs are clean and papers are debating perfectly"

    print(f"  Prediction Label: {quality_label} - {quality_explanation}")

    # Create summary with both prediction and ground truth labels
    quality_dict = {
        "prediction_label": quality_label,
        "explanation": quality_explanation
    }

    # Add ground truth label if available
    if ground_truth_label is not None:
        quality_dict["ground_truth_label"] = ground_truth_label

    # Create summary
    summary = {
        "quality": quality_dict,
        "summary": {
            "papers_talking_to_each_other": papers_talking,
            "flag": analysis_data.get('flag', None),
            "explanation": analysis_data.get('explanation', '')
        },
        "original_metadata": {
            "title": original_data.get('title', ''),
            "authors": original_data.get('authors', ''),
            "abstract": original_data.get('abstract', ''),
            "num_sections": len(original_data.get('sections', {})),
            "num_references": len(original_data.get('references', []))
        },
        "critique_metadata": {
            "num_articles_total": critique_total,
            "num_articles_related": critique_related,
            "source_file": critique_response_outputs.get('critique', {}).get('source_file', ''),
            "model_used": critique_response_outputs.get('critique', {}).get('model', '')
        },
        "response_metadata": {
            "num_articles_total": response_total,
            "num_articles_related": response_related,
            "source_file": critique_response_outputs.get('response', {}).get('source_file', ''),
            "model_used": critique_response_outputs.get('response', {}).get('model', '')
        },
        "analysis_metadata": analysis_data.get('analysis_metadata', {})
    }

    print(f"  ✓ Summary created")

    return summary


def generate_all_final_outputs(triad_dir: Path):
    """
    Generate all final output files for a triad.

    Args:
        triad_dir: Path to the triad directory
    """
    print("="*70)
    print("Generating Final Output Files")
    print("="*70)
    print()

    triad_dir = Path(triad_dir)

    if not triad_dir.exists():
        print(f"❌ Triad directory does not exist: {triad_dir}")
        return

    # Create final outputs directory
    final_outputs_dir = triad_dir / "final_outputs"
    final_outputs_dir.mkdir(parents=True, exist_ok=True)

    # Load relationship analysis first
    analysis_file = triad_dir / "relationship_analysis" / "triad_relationship_analysis.json"

    if analysis_file.exists():
        analysis_data = load_json_file(analysis_file)
        print(f"✓ Loaded relationship analysis")
    else:
        print("⚠ No relationship analysis found, creating empty structure")
        analysis_data = {
            "talk_to_each_other": False,
            "flag": "no_analysis_available",
            "explanation": "No relationship analysis available",
            "related_critiques": [],
            "related_responses": []
        }

    # 1. Generate original paper output
    original_data = generate_original_paper_output(triad_dir)

    if original_data:
        output_path = final_outputs_dir / "original_paper_final.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(original_data, f, ensure_ascii=False, indent=2)
        print(f"  ✓ Saved to: {output_path}")

    # 2. Generate critique and response outputs (RELATED ONLY)
    critique_response_outputs = generate_critique_response_outputs(triad_dir, analysis_data)

    # Save critique output (related only)
    if 'critique' in critique_response_outputs:
        critique_path = final_outputs_dir / "critique_final.json"
        with open(critique_path, 'w', encoding='utf-8') as f:
            json.dump(critique_response_outputs['critique'], f, ensure_ascii=False, indent=2)
        print(f"  ✓ Saved critique to: {critique_path}")

    # Save response output (related only)
    if 'response' in critique_response_outputs:
        response_path = final_outputs_dir / "response_final.json"
        with open(response_path, 'w', encoding='utf-8') as f:
            json.dump(critique_response_outputs['response'], f, ensure_ascii=False, indent=2)
        print(f"  ✓ Saved response to: {response_path}")

    # 3. Generate summary file with quality label
    if original_data:
        summary = generate_summary_file(triad_dir, original_data, critique_response_outputs, analysis_data)

        if summary:
            summary_path = final_outputs_dir / "summary.json"
            with open(summary_path, 'w', encoding='utf-8') as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)
            print(f"  ✓ Saved summary to: {summary_path}")

    print("\n" + "="*70)
    print("✓ All Final Outputs Generated Successfully!")
    print(f"✓ Output directory: {final_outputs_dir}")
    print("="*70)

    # Print summary info
    if original_data:
        print("\nSummary:")
        print(f"  Original Paper: {original_data.get('title', 'N/A')[:60]}...")
        print(f"  Sections: {len(original_data.get('sections', {}))}")
        print(f"  References: {len(original_data.get('references', []))}")

    if 'critique' in critique_response_outputs:
        critique_related = critique_response_outputs.get('critique_related_count', 0)
        critique_total = critique_response_outputs.get('critique_total_count', 0)
        print(f"  Critique Articles: {critique_related} related / {critique_total} total")

    if 'response' in critique_response_outputs:
        response_related = critique_response_outputs.get('response_related_count', 0)
        response_total = critique_response_outputs.get('response_total_count', 0)
        print(f"  Response Articles: {response_related} related / {response_total} total")

    # Print quality labels
    if summary:
        quality = summary.get('quality', {})
        prediction = quality.get('prediction_label', 'N/A')
        ground_truth = quality.get('ground_truth_label', 'N/A')
        explanation = quality.get('explanation', 'N/A')
        print(f"\n  Prediction Label: {prediction}")
        print(f"  Ground Truth Label: {ground_truth}")
        print(f"  Explanation: {explanation}")

    print()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate final output files for triad analysis")
    parser.add_argument(
        "--triad-dir",
        type=str,
        help="Path to triad directory (e.g., data/triad_samples/triad_1)"
    )

    args = parser.parse_args()

    if args.triad_dir:
        triad_path = Path(args.triad_dir)
    else:
        # Default to triad_1
        triad_path = Path("data/triad_samples/triad_1")

    if not triad_path.exists():
        print(f"❌ Triad directory not found: {triad_path}")
        print("\nUsage:")
        print("  python generate_final_outputs.py --triad-dir data/triad_samples/triad_1")
        exit(1)

    generate_all_final_outputs(triad_path)
