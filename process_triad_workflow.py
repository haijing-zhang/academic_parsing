"""
Complete workflow for processing triad samples.

This script orchestrates the entire pipeline:
1. Generate XML from original paper PDF using GROBID
2. Extract metadata from original paper XML
3. Extract text from critique and response PDFs
4. Structure critique/response texts with OpenAI
5. Analyze relationships between papers

Directory structure for each triad:
triad_samples/triad_N/
├── original_*.pdf                    # Original paper PDF
├── critique_*.pdf                    # Critique paper PDF
├── response_*.pdf                    # Response paper PDF
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
"""

import subprocess
from pathlib import Path
import json
import os
import sys
from typing import Optional, Dict
from dotenv import load_dotenv

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src" / "pdf_extract"))

from xml_preprocessor import extract_metadata_from_xml
from extract_text_from_pdf import extract_and_save_pdf_text
from process_triad_with_openai import process_triad_texts
from analyze_triad_relationships import analyze_triad_relationships, load_json_file

# Load environment variables
load_dotenv()


class TriadProcessor:
    """Main class for processing triad samples."""

    def __init__(self, triad_dir: Path, grobid_url: str = "http://localhost:8070", openai_api_key: Optional[str] = None):
        """
        Initialize the triad processor.

        Args:
            triad_dir: Path to the triad directory
            grobid_url: URL for GROBID service
            openai_api_key: OpenAI API key
        """
        self.triad_dir = Path(triad_dir)
        self.grobid_url = grobid_url
        self.openai_api_key = openai_api_key or os.environ.get("OPENAI_API_KEY")

        if not self.openai_api_key:
            raise ValueError("OpenAI API key not found. Set OPENAI_API_KEY environment variable or pass it to the constructor.")

    def print_section_header(self, title: str):
        """Print a formatted section header."""
        print("\n" + "="*70)
        print(f"  {title}")
        print("="*70 + "\n")

    def step1_generate_xml_from_pdf(self) -> Optional[Path]:
        """
        Step 1: Generate XML from original paper PDF using GROBID.

        Returns:
            Path to generated XML file or None if failed
        """
        self.print_section_header("STEP 1: Generate XML from Original Paper PDF")

        # Find original PDF
        original_pdfs = list(self.triad_dir.glob("original_*.pdf"))

        if not original_pdfs:
            print("❌ No original PDF found in triad directory")
            return None

        original_pdf = original_pdfs[0]
        print(f"Found original PDF: {original_pdf.name}")

        # Generate output XML filename
        xml_output = self.triad_dir / f"output_orginal_{original_pdf.stem.replace('original_', '')}.xml"

        # Check if XML already exists
        if xml_output.exists():
            print(f"✓ XML file already exists: {xml_output.name}")
            print("  Skipping GROBID processing")
            return xml_output

        # Call GROBID service
        print(f"Calling GROBID service at {self.grobid_url}...")

        try:
            # Use just the filename since we're setting cwd to triad_dir
            curl_command = [
                'curl',
                '-v',
                '--form', f'input=@{original_pdf.name}',
                f'{self.grobid_url}/api/processFulltextDocument',
                '-o', xml_output.name
            ]

            result = subprocess.run(
                curl_command,
                cwd=self.triad_dir,
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes timeout
            )

            if xml_output.exists() and xml_output.stat().st_size > 0:
                print(f"✓ Successfully generated XML: {xml_output.name}")
                print(f"  File size: {xml_output.stat().st_size} bytes")
                return xml_output
            else:
                print(f"❌ Failed to generate XML")
                print(f"  Error: {result.stderr}")
                return None

        except subprocess.TimeoutExpired:
            print("❌ GROBID request timed out after 5 minutes")
            return None
        except Exception as e:
            print(f"❌ Error calling GROBID: {e}")
            return None

    def step2_extract_metadata_from_xml(self, xml_path: Path) -> Optional[Dict]:
        """
        Step 2: Extract metadata from original paper XML.

        Args:
            xml_path: Path to XML file

        Returns:
            Metadata dictionary or None if failed
        """
        self.print_section_header("STEP 2: Extract Metadata from XML")

        print(f"Processing XML: {xml_path.name}")

        try:
            # Extract metadata using xml_preprocessor
            metadata = extract_metadata_from_xml(xml_path)

            # Save to original_info_from_xml.json
            output_path = self.triad_dir / "original_info_from_xml.json"

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)

            print(f"✓ Metadata extracted and saved to: {output_path.name}")
            print(f"  Title: {metadata.get('title', 'N/A')[:80]}...")
            print(f"  Authors: {metadata.get('authors', 'N/A')[:80]}...")
            print(f"  Abstract length: {len(metadata.get('abstract', ''))} characters")

            return metadata

        except Exception as e:
            print(f"❌ Error extracting metadata: {e}")
            return None

    def step3_extract_text_from_pdfs(self) -> Dict[str, Dict]:
        """
        Step 3: Extract text from critique and response PDFs.

        Returns:
            Dictionary of extraction results
        """
        self.print_section_header("STEP 3: Extract Text from Critique and Response PDFs")

        # Create output directory
        output_dir = self.triad_dir / "extracted_texts"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Find critique and response PDFs
        critique_pdfs = list(self.triad_dir.glob("critique_*.pdf"))
        response_pdfs = list(self.triad_dir.glob("response_*.pdf"))

        all_pdfs = critique_pdfs + response_pdfs

        if not all_pdfs:
            print("❌ No critique or response PDFs found")
            return {}

        print(f"Found {len(all_pdfs)} PDF(s):")
        print(f"  - {len(critique_pdfs)} critique PDF(s)")
        print(f"  - {len(response_pdfs)} response PDF(s)")

        results = {}

        for pdf_path in all_pdfs:
            try:
                result = extract_and_save_pdf_text(pdf_path, output_dir)
                results[pdf_path.name] = result
            except Exception as e:
                print(f"❌ Error processing {pdf_path.name}: {e}")

        print(f"\n✓ Successfully extracted text from {len(results)}/{len(all_pdfs)} PDF(s)")
        print(f"✓ Output saved to: {output_dir}")

        return results

    def step4_structure_with_openai(self) -> Dict[str, Dict]:
        """
        Step 4: Process extracted texts with OpenAI to get structured data.

        Returns:
            Dictionary of structured results
        """
        self.print_section_header("STEP 4: Structure Texts with OpenAI")

        try:
            results = process_triad_texts(self.triad_dir, self.openai_api_key)
            return results or {}
        except Exception as e:
            print(f"❌ Error during OpenAI processing: {e}")
            return {}

    def step5_analyze_relationships(self) -> Optional[Dict]:
        """
        Step 5: Analyze relationships between original, critique, and response.

        Returns:
            Analysis result dictionary or None if failed
        """
        self.print_section_header("STEP 5: Analyze Triad Relationships")

        # Load original metadata
        original_metadata_file = self.triad_dir / "original_info_from_xml.json"
        if not original_metadata_file.exists():
            print(f"❌ Original metadata not found: {original_metadata_file}")
            return None

        print(f"Loading original metadata...")
        original_metadata = load_json_file(original_metadata_file)
        print(f"  Title: {original_metadata.get('title', 'N/A')[:60]}...")

        # Load structured critique data
        openai_structured_dir = self.triad_dir / "openai_structured"
        critique_files = list(openai_structured_dir.glob("critique_*_structured.json"))

        if critique_files:
            critique_data = load_json_file(critique_files[0])
            print(f"  Loaded {len(critique_data.get('articles', []))} critique article(s)")
        else:
            print("  Warning: No critique structured file found")
            critique_data = {"articles": []}

        # Load structured response data
        response_files = list(openai_structured_dir.glob("response_*_structured.json"))

        if response_files:
            response_data = load_json_file(response_files[0])
            print(f"  Loaded {len(response_data.get('articles', []))} response article(s)")
        else:
            print("  Warning: No response structured file found")
            response_data = {"articles": []}

        # Perform analysis
        print("\nPerforming relationship analysis...")

        try:
            analysis_result = analyze_triad_relationships(
                original_metadata,
                critique_data,
                response_data,
                self.openai_api_key
            )

            # Save result
            output_dir = self.triad_dir / "relationship_analysis"
            output_dir.mkdir(parents=True, exist_ok=True)

            output_path = output_dir / "triad_relationship_analysis.json"
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(analysis_result, f, ensure_ascii=False, indent=2)

            print(f"\n✓ Analysis saved to: {output_path}")

            # Print summary
            print("\n" + "-"*70)
            print("ANALYSIS SUMMARY:")
            print("-"*70)

            related_critiques = analysis_result.get('related_critiques', [])
            related_responses = analysis_result.get('related_responses', [])
            talk_to_each_other = analysis_result.get('talk_to_each_other', False)
            flag = analysis_result.get('flag')

            print(f"Related Critiques: {len(related_critiques)}")
            for critique in related_critiques:
                print(f"  - {critique.get('title', 'N/A')[:60]}...")

            print(f"\nRelated Responses: {len(related_responses)}")
            for response in related_responses:
                print(f"  - {response.get('title', 'N/A')[:60]}...")

            print(f"\nTalk to Each Other: {talk_to_each_other}")
            print(f"Flag: {flag if flag else 'None'}")

            if analysis_result.get('explanation'):
                print(f"\nExplanation: {analysis_result['explanation']}")

            return analysis_result

        except Exception as e:
            print(f"❌ Error during analysis: {e}")
            return None

    def run_full_workflow(self, start_from_step: int = 1) -> bool:
        """
        Run the complete workflow from start to finish.

        Args:
            start_from_step: Which step to start from (1-5)

        Returns:
            True if successful, False otherwise
        """
        print("\n" + "█"*70)
        print("  TRIAD PROCESSING WORKFLOW")
        print(f"  Directory: {self.triad_dir.name}")
        print("█"*70)

        if not self.triad_dir.exists():
            print(f"\n❌ Triad directory does not exist: {self.triad_dir}")
            return False

        # Step 1: Generate XML
        if start_from_step <= 1:
            xml_path = self.step1_generate_xml_from_pdf()
            if not xml_path:
                print("\n❌ Workflow failed at Step 1")
                return False
        else:
            xml_files = list(self.triad_dir.glob("output_orginal_*.xml"))
            if not xml_files:
                print("\n❌ No XML file found. Please run from Step 1.")
                return False
            xml_path = xml_files[0]

        # Step 2: Extract metadata
        if start_from_step <= 2:
            metadata = self.step2_extract_metadata_from_xml(xml_path)
            if not metadata:
                print("\n❌ Workflow failed at Step 2")
                return False

        # Step 3: Extract text from PDFs
        if start_from_step <= 3:
            text_results = self.step3_extract_text_from_pdfs()
            if not text_results:
                print("\n❌ Workflow failed at Step 3")
                return False

        # Step 4: Structure with OpenAI
        if start_from_step <= 4:
            structured_results = self.step4_structure_with_openai()
            if not structured_results:
                print("\n❌ Workflow failed at Step 4")
                return False

        # Step 5: Analyze relationships
        if start_from_step <= 5:
            analysis_result = self.step5_analyze_relationships()
            if not analysis_result:
                print("\n❌ Workflow failed at Step 5")
                return False

        # Success!
        print("\n" + "█"*70)
        print("  ✓ WORKFLOW COMPLETED SUCCESSFULLY!")
        print("█"*70 + "\n")

        return True


def process_all_triads(base_dir: Path = None, start_from_step: int = 1):
    """
    Process all triad directories in triad_samples folder.

    Args:
        base_dir: Base directory containing triad_samples
        start_from_step: Which step to start from (1-5)
    """
    if base_dir is None:
        base_dir = Path(__file__).parent / "data" / "triad_samples"
    else:
        base_dir = Path(base_dir)

    if not base_dir.exists():
        print(f"❌ Base directory does not exist: {base_dir}")
        return

    # Find all triad directories
    triad_dirs = sorted([d for d in base_dir.iterdir() if d.is_dir() and d.name.startswith("triad_")])

    if not triad_dirs:
        print(f"❌ No triad directories found in {base_dir}")
        return

    print(f"\nFound {len(triad_dirs)} triad director(ies) to process")

    results = {}

    for triad_dir in triad_dirs:
        print(f"\n{'='*70}")
        print(f"Processing: {triad_dir.name}")
        print(f"{'='*70}")

        try:
            processor = TriadProcessor(triad_dir)
            success = processor.run_full_workflow(start_from_step=start_from_step)
            results[triad_dir.name] = "SUCCESS" if success else "FAILED"
        except Exception as e:
            print(f"\n❌ Error processing {triad_dir.name}: {e}")
            results[triad_dir.name] = f"ERROR: {e}"

    # Print final summary
    print("\n" + "="*70)
    print("FINAL SUMMARY")
    print("="*70)

    for triad_name, status in results.items():
        status_icon = "✓" if status == "SUCCESS" else "❌"
        print(f"{status_icon} {triad_name}: {status}")

    print("="*70 + "\n")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Process triad samples through complete workflow")
    parser.add_argument(
        "--triad-dir",
        type=str,
        help="Path to specific triad directory (e.g., data/triad_samples/triad_1)"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all triad directories in data/triad_samples"
    )
    parser.add_argument(
        "--start-from",
        type=int,
        choices=[1, 2, 3, 4, 5],
        default=1,
        help="Which step to start from (1-5). Default: 1"
    )
    parser.add_argument(
        "--grobid-url",
        type=str,
        default="http://localhost:8070",
        help="GROBID service URL. Default: http://localhost:8070"
    )

    args = parser.parse_args()

    # Check for OpenAI API key
    if not os.environ.get("OPENAI_API_KEY"):
        print("❌ Error: OPENAI_API_KEY not set")
        print("\nTo set your API key:")
        print("1. Environment variable: export OPENAI_API_KEY='your-key-here'")
        print("2. Create .env file with: OPENAI_API_KEY=your-key-here")
        sys.exit(1)

    if args.all:
        # Process all triads
        process_all_triads(start_from_step=args.start_from)
    elif args.triad_dir:
        # Process specific triad
        triad_path = Path(args.triad_dir)
        processor = TriadProcessor(triad_path, grobid_url=args.grobid_url)
        success = processor.run_full_workflow(start_from_step=args.start_from)
        sys.exit(0 if success else 1)
    else:
        # Default: process triad_1
        default_triad = Path("data/triad_samples/triad_1")
        if default_triad.exists():
            processor = TriadProcessor(default_triad, grobid_url=args.grobid_url)
            success = processor.run_full_workflow(start_from_step=args.start_from)
            sys.exit(0 if success else 1)
        else:
            print(f"❌ Default triad directory not found: {default_triad}")
            print("\nUsage:")
            print("  python process_triad_workflow.py --triad-dir data/triad_samples/triad_1")
            print("  python process_triad_workflow.py --all")
            sys.exit(1)
