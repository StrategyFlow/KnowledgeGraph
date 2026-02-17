#!/usr/bin/env python3
"""Load extracted JSON data directly into FalkorDB."""

import json
import os
from pathlib import Path
from london_project.dspy_extractor import DSPyExtractor
from london_project.falkordb_client import FalkorDBClient


def load_json_to_falkordb(json_file: str, falkordb_host: str = "localhost", falkordb_port: int = 6379):
    """Load a JSON file into FalkorDB.
    
    Args:
        json_file: Path to the extracted JSON file
        falkordb_host: FalkorDB host
        falkordb_port: FalkorDB port
    """
    # Load JSON
    with open(json_file, 'r', encoding='utf-8') as f:
        extracted_data = json.load(f)
    
    print(f"Loaded data from: {json_file}")
    print(f"Title: {extracted_data.get('title')}")
    
    # Connect to FalkorDB
    try:
        client = FalkorDBClient(falkordb_host, falkordb_port, "KnowledgeGraph")
        print(f"Connected to FalkorDB at {falkordb_host}:{falkordb_port}")
    except Exception as e:
        print(f"Error connecting to FalkorDB: {e}")
        return
    
    # Generate and execute queries
    extractor = DSPyExtractor("dummy", "dummy", "dummy")  # Only use for query generation
    queries = extractor.to_falkordb_queries(extracted_data)
    
    print(f"\nExecuting {len(queries)} queries...")
    results = client.execute_queries(queries)
    
    # Summary
    success_count = sum(1 for r in results if r.get("success"))
    print(f"\n✓ {success_count}/{len(queries)} queries executed successfully")
    
    if success_count < len(queries):
        print("\nFailed queries:")
        for i, r in enumerate(results, 1):
            if not r.get("success"):
                print(f"  Query {i}: {r.get('error')}")


def main():
    """Main entry point."""
    output_dir = Path("output")
    
    if not output_dir.exists():
        print(f"Output directory not found: {output_dir}")
        return
    
    # Find all extracted JSON files
    json_files = list(output_dir.glob("*_extracted.json"))
    
    if not json_files:
        print("No extracted JSON files found in output directory")
        return
    
    print(f"Found {len(json_files)} extracted JSON file(s):\n")
    
    for i, json_file in enumerate(json_files, 1):
        print(f"{i}. {json_file.name}")
    
    # Load first file or let user choose
    if len(json_files) == 1:
        json_file = json_files[0]
    else:
        choice = input(f"\nEnter file number to load (1-{len(json_files)}): ").strip()
        try:
            idx = int(choice) - 1
            json_file = json_files[idx]
        except (ValueError, IndexError):
            print("Invalid choice")
            return
    
    load_json_to_falkordb(str(json_file))


if __name__ == "__main__":
    main()
