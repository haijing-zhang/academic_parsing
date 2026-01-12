"""
Generate final output files for batch processing with new folder structure.

Folder structure:
- raw_data/: metadata.json and PDFs
- intermediate_results/: XML, structured data, analysis
- final_outputs/: final JSON outputs
"""
from pathlib import Path
import json
from typing import Dict, Optional
from xml_preprocessor import extract_metadata_from_xml


def load_json_file(file_path: Path) -> dict:
    """Load JSON file and return its contents."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def calculate_similarity(article1: Dict, article2: Dict) -> float:
    """
    Calculate similarity between two articles based on title and authors.

    Args:
        article1: First article dictionary
        article2: Second article dictionary

    Returns:
        Similarity score between 0.0 and 1.0
    """
    def normalize_text(text: str) -> str:
        """Normalize text for comparison."""
        if not text:
            return ""
        return text.lower().strip()

    def jaccard_similarity(str1: str, str2: str) -> float:
        """Calculate Jaccard similarity between two strings."""
        if not str1 or not str2:
            return 0.0

        words1 = set(normalize_text(str1).split())
        words2 = set(normalize_text(str2).split())

        if not words1 or not words2:
            return 0.0

        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))

        return intersection / union if union > 0 else 0.0

    # Extract fields
    title1 = article1.get('title', '')
    title2 = article2.get('title', '')
    authors1 = article1.get('authors', '')
    authors2 = article2.get('authors', '')

    # Calculate similarity for each field
    title_sim = jaccard_similarity(title1, title2)
    authors_sim = jaccard_similarity(authors1, authors2)

    # Weighted average: title is more important than authors
    weighted_similarity = (
        title_sim * 0.7 +      # Title: 70%
        authors_sim * 0.3      # Authors: 30%
    )

    return weighted_similarity


def find_best_match(target_article: Dict, candidate_articles: list) -> Optional[Dict]:
    """
    Find the best matching article from candidates using similarity.

    Args:
        target_article: Article to match
        candidate_articles: List of candidate articles

    Returns:
        Best matching article or None if no good match found
    """
    if not candidate_articles:
        return None

    best_match = None
    best_score = 0.0

    for candidate in candidate_articles:
        score = calculate_similarity(target_article, candidate)
        if score > best_score:
            best_score = score
            best_match = candidate

    # Only return match if similarity is above threshold
    # Threshold of 0.3 means at least some overlap in title/authors
    if best_score >= 0.3:
        return best_match

    return None


def generate_original_paper_output(triad_dir: Path) -> Optional[Dict]:
    """Generate final output for the original paper with all sections."""
    print("Generating original paper output...")

    # Find the XML file in intermediate_results
    intermediate_dir = triad_dir / "intermediate_results"
    xml_files = list(intermediate_dir.glob("output_orginal_*.xml"))

    if not xml_files:
        print(f"  ❌ No original XML file found in {intermediate_dir}")
        return None

    xml_path = xml_files[0]
    print(f"  Processing: {xml_path.name}")

    # Extract full content with sections and references
    original_data = extract_metadata_from_xml(xml_path, include_full_content=True)

    print(f"  ✓ Extracted {len(original_data.get('sections', {}))} sections")
    print(f"  ✓ Extracted {len(original_data.get('references', []))} references")

    return original_data


def generate_critique_response_outputs(triad_dir: Path, analysis_data: Dict) -> Dict[str, Dict]:
    """Generate final outputs for critique and response papers (RELATED ONLY)."""
    print("\nGenerating critique and response outputs (related articles only)...")

    outputs = {}
    openai_structured_dir = triad_dir / "intermediate_results" / "openai_structured"

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
        all_critique_articles = critique_data.get('articles', [])
        total_critiques = len(all_critique_articles)

        # Use similarity-based matching for related critiques
        enriched_critiques = []
        for related_article in related_critiques:
            print(f"  Matching critique: {related_article.get('title', 'N/A')[:60]}...")

            # Find best match using similarity
            best_match = find_best_match(related_article, all_critique_articles)

            if best_match:
                # Calculate similarity score for logging
                score = calculate_similarity(related_article, best_match)
                print(f"    ✓ Found match (similarity: {score:.2f}): {best_match.get('title', 'N/A')[:60]}...")
                enriched_critiques.append(best_match)
            else:
                # Fallback to related_article if no good match found
                print(f"    ⚠ Warning: No good match found (using analysis data)")
                enriched_critiques.append(related_article)

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
        all_response_articles = response_data.get('articles', [])
        total_responses = len(all_response_articles)

        # Use similarity-based matching for related responses
        enriched_responses = []
        for related_article in related_responses:
            print(f"  Matching response: {related_article.get('title', 'N/A')[:60]}...")

            # Find best match using similarity
            best_match = find_best_match(related_article, all_response_articles)

            if best_match:
                # Calculate similarity score for logging
                score = calculate_similarity(related_article, best_match)
                print(f"    ✓ Found match (similarity: {score:.2f}): {best_match.get('title', 'N/A')[:60]}...")
                enriched_responses.append(best_match)
            else:
                # Fallback to related_article if no good match found
                print(f"    ⚠ Warning: No good match found (using analysis data)")
                enriched_responses.append(related_article)

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
    Generate summary file with prediction and ground truth labels.

    Quality Labels:
    - P (Perfect): Papers are talking to each other AND all extracted articles are related
    - B (Broken): Papers are talking but PDFs contain extra unrelated articles (need parsing)
    - IV (Invalid): Original paper is broken (missing sections or sections too short) OR papers are not talking to each other
    """
    print("\nGenerating summary file...")

    # Load ground truth label from raw_data/metadata.json
    metadata_file = triad_dir / "raw_data" / "metadata.json"
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
    papers_talking = (
        analysis_data.get('talk_to_each_other')
        or analysis_data.get('talk_to_each other')
        or False
    )
    critique_total = critique_response_outputs.get('critique_total_count', 0)
    critique_related = critique_response_outputs.get('critique_related_count', 0)
    response_total = critique_response_outputs.get('response_total_count', 0)
    response_related = critique_response_outputs.get('response_related_count', 0)

    # Determine quality label (prediction)
    # Check if the original paper itself is valid
    original_authors = original_data.get('authors', '')

    # Check if the original paper itself is valid
    if len(original_data.get('sections', {}).keys()) < 2:
        quality_label = "IV"  # Invalid - original paper is broken
        original_sections = original_data.get('sections', {})
        missing_parts = []
        if not original_sections:
            missing_parts.append("sections")
        if len(original_sections.keys()) < 2:
            missing_parts.append("sections too short")
        quality_explanation = f"Original paper is broken (missing: {', '.join(missing_parts)})"
    # Check if papers are talking to each other
    elif not papers_talking:
        quality_label = "IV"  # Invalid - not talking to each other
        quality_explanation = "Papers are not debating with one another"
    elif critique_related < critique_total or response_related < response_total:
        quality_label = "B"  # Broken - PDFs contain extra articles
        quality_explanation = f"PDFs contain extra articles (Critique: {critique_related}/{critique_total}, Response: {response_related}/{response_total})"
    else:
        quality_label = "P"  # Perfect - clean and complete
        quality_explanation = "PDFs are clean and papers are debating perfectly"

    print(f"  Prediction Label: {quality_label} - {quality_explanation}")

    # Create quality dict with both prediction and ground truth
    quality_dict = {
        "prediction_label": quality_label,
        "explanation": quality_explanation
    }

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


def generate_all_final_outputs_batch(triad_dir: Path):
    """Generate all final output files for a triad (batch mode with new structure)."""
    print("="*70)
    print("Generating Final Output Files (Batch Mode)")
    print("="*70)
    print()

    triad_dir = Path(triad_dir)

    if not triad_dir.exists():
        print(f"❌ Triad directory does not exist: {triad_dir}")
        return

    # Create final outputs directory
    final_outputs_dir = triad_dir / "final_outputs"
    final_outputs_dir.mkdir(parents=True, exist_ok=True)

    # Load relationship analysis from intermediate_results
    analysis_file = triad_dir / "intermediate_results" / "relationship_analysis" / "triad_relationship_analysis.json"

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

    # 2. Generate critique and response outputs
    critique_response_outputs = generate_critique_response_outputs(triad_dir, analysis_data)

    if 'critique' in critique_response_outputs:
        critique_path = final_outputs_dir / "critique_final.json"
        with open(critique_path, 'w', encoding='utf-8') as f:
            json.dump(critique_response_outputs['critique'], f, ensure_ascii=False, indent=2)
        print(f"  ✓ Saved critique to: {critique_path}")

    if 'response' in critique_response_outputs:
        response_path = final_outputs_dir / "response_final.json"
        with open(response_path, 'w', encoding='utf-8') as f:
            json.dump(critique_response_outputs['response'], f, ensure_ascii=False, indent=2)
        print(f"  ✓ Saved response to: {response_path}")

    # 3. Generate summary file
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
