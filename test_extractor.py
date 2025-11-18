#!/usr/bin/env python3
"""
Test script for extractor.py using one row from sample.csv
"""

import csv
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from pdf_extract.extractor import extract_blocks, save_chunks


def main():
    # Setup paths
    base_dir = Path(__file__).parent
    data_dir = base_dir / "data"
    csv_path = data_dir / "sample.csv"
    pdf_dir = data_dir / "pdfs"
    output_dir = data_dir / "extracted_chunks"

    # Read the first data row from sample.csv
    print("Reading sample.csv...")
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        first_row = next(reader)

    print(f"\nFirst row triad_id: {first_row['triad_id']}")

    # Parse the triad_id to get the three work IDs
    triad_id = first_row['triad_id']
    work_ids = triad_id.split('_')

    if len(work_ids) != 3:
        print(f"Error: Expected 3 work IDs in triad_id, got {len(work_ids)}")
        return

    print(f"Work IDs: {work_ids}")
    print(f"  - Original: {work_ids[0]}")
    print(f"  - Critique: {work_ids[1]}")
    print(f"  - Response: {work_ids[2]}")

    # Process each PDF
    results = []
    for i, work_id in enumerate(work_ids):
        role = ['Original', 'Critique', 'Response'][i]
        pdf_path = pdf_dir / f"{work_id}.pdf"

        print(f"\n{'='*60}")
        print(f"Processing {role}: {work_id}")
        print(f"PDF path: {pdf_path}")

        if not pdf_path.exists():
            print(f"  WARNING: PDF not found!")
            continue

        try:
            # Extract blocks
            print(f"  Extracting blocks...")
            blocks = extract_blocks(pdf_path)
            print(f"  Found {len(blocks)} blocks")

            # Show first few blocks as sample
            print(f"\n  First 3 blocks:")
            for j, block in enumerate(blocks[:3]):
                print(f"    Block {j+1}:")
                print(f"      Page: {block['page']}")
                print(f"      Position: ({block['x0']:.2f}, {block['y0']:.2f}) to ({block['x1']:.2f}, {block['y1']:.2f})")
                text_preview = block['text'][:100].replace('\n', ' ')
                print(f"      Text: {text_preview}...")

            # Save chunks
            print(f"\n  Saving chunks to {output_dir}...")
            save_chunks(work_id, blocks, output_dir)
            print(f"  Saved to {output_dir / work_id}.json")

            results.append({
                'work_id': work_id,
                'role': role,
                'blocks': len(blocks),
                'success': True
            })

        except Exception as e:
            print(f"  ERROR: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            results.append({
                'work_id': work_id,
                'role': role,
                'success': False,
                'error': str(e)
            })

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for result in results:
        status = "OK" if result['success'] else "FAILED"
        if result['success']:
            print(f"[{status}] {result['role']} ({result['work_id']}): {result['blocks']} blocks")
        else:
            print(f"[{status}] {result['role']} ({result['work_id']}): {result.get('error', 'Unknown error')}")

    print(f"\nOutput directory: {output_dir}")


if __name__ == "__main__":
    main()
