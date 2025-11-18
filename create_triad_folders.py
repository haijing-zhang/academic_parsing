#!/usr/bin/env python3
"""
Randomly select 3 rows from sample.csv and create triad folders with corresponding PDFs.
"""

import csv
import random
import shutil
from pathlib import Path


def main():
    # Setup paths
    base_dir = Path(__file__).parent
    data_dir = base_dir / "data"
    csv_path = data_dir / "sample.csv"
    pdf_dir = data_dir / "pdfs"
    output_dir = data_dir / "triad_samples"

    # Read all rows from sample.csv
    print("Reading sample.csv...")
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Total rows in sample.csv: {len(rows)}")

    # Randomly select 3 rows
    if len(rows) < 3:
        print(f"Error: Not enough rows in CSV. Found {len(rows)}, need at least 3.")
        return

    selected_rows = random.sample(rows, 3)
    print(f"\nRandomly selected 3 triads:")

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Process each selected row
    results = []
    for i, row in enumerate(selected_rows, 1):
        triad_id = row['triad_id']
        work_ids = triad_id.split('_')

        if len(work_ids) != 3:
            print(f"\n[WARNING] Row {i}: Invalid triad_id format: {triad_id}")
            continue

        print(f"\n{'='*70}")
        print(f"Triad {i}: {triad_id}")
        print(f"  Original:  {work_ids[0]}")
        print(f"  Critique:  {work_ids[1]}")
        print(f"  Response:  {work_ids[2]}")

        # Create triad folder
        triad_folder = output_dir / f"triad_{i}_{triad_id}"
        triad_folder.mkdir(parents=True, exist_ok=True)
        print(f"  Created folder: {triad_folder.name}")

        # Copy PDFs
        copied_count = 0
        missing_pdfs = []

        for j, work_id in enumerate(work_ids):
            role = ['original', 'critique', 'response'][j]
            source_pdf = pdf_dir / f"{work_id}.pdf"
            dest_pdf = triad_folder / f"{role}_{work_id}.pdf"

            if source_pdf.exists():
                shutil.copy2(source_pdf, dest_pdf)
                print(f"    ✓ Copied {role}: {work_id}.pdf")
                copied_count += 1
            else:
                print(f"    ✗ Missing {role}: {work_id}.pdf")
                missing_pdfs.append((role, work_id))

        # Save metadata
        metadata = {
            'triad_id': triad_id,
            'original_id': work_ids[0],
            'critique_id': work_ids[1],
            'response_id': work_ids[2],
            'csv_row': row
        }

        import json
        metadata_file = triad_folder / "metadata.json"
        metadata_file.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )
        print(f"    ✓ Saved metadata.json")

        results.append({
            'triad_num': i,
            'triad_id': triad_id,
            'folder': triad_folder,
            'copied': copied_count,
            'missing': missing_pdfs
        })

    # Print summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")

    for result in results:
        status = "✓ Complete" if result['copied'] == 3 else f"⚠ Partial ({result['copied']}/3)"
        print(f"\nTriad {result['triad_num']}: {result['triad_id']}")
        print(f"  Status: {status}")
        print(f"  Folder: {result['folder'].name}")
        if result['missing']:
            print(f"  Missing PDFs:")
            for role, work_id in result['missing']:
                print(f"    - {role}: {work_id}")

    print(f"\n{'='*70}")
    print(f"Output directory: {output_dir}")
    print(f"Total triads created: {len(results)}")


if __name__ == "__main__":
    # Set random seed for reproducibility (optional - remove if you want different results each time)
    random.seed(42)
    main()
