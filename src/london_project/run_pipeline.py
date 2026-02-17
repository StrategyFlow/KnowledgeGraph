import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from london_project.dspy_extractor import DSPyExtractor
from london_project.falkordb_client import FalkorDBClient
from london_project.input_processor import InputProcessor

load_dotenv()

async def process_file(content: str, extractor: DSPyExtractor, falkordb_client=None):
    """Process a single file through the pipeline."""
    print(f"\n{'='*60}")
    print("Running DSPy extraction...")
    print(f"{'='*60}")
    
    # Extract information
    response = await extractor.extract_info(content)
    
    # Save to output files
    try:
        file_paths = extractor.save_to_files(response, output_dir="output")
        print(f"✓ Saved to files: {file_paths}")
    except Exception as e:
        print(f"✗ Error saving to files: {e}")
    
    # Load to FalkorDB if enabled
    if falkordb_client:
        try:
            queries = extractor.to_falkordb_queries(response)
            print(f"Executing {len(queries)} queries in FalkorDB...")
            results = falkordb_client.execute_queries(queries)
            success_count = sum(1 for r in results if r.get("success"))
            print(f"✓ {success_count}/{len(queries)} queries executed successfully in FalkorDB")
        except Exception as e:
            print(f"✗ Error executing FalkorDB queries: {e}")
    
    print(f"{'='*60}")
    print("Processing complete!")
    print(f"{'='*60}\n")

async def main():
    # Configuration
    INPUT_DIR = os.getenv("INPUT_DIR", "input")
    OLLAMA_API_BASE = os.getenv("OLLAMA_API_BASE", "http://ares.westpoint.edu:11434")
    OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "dspy-ollama")
    USE_FALKORDB = os.getenv("USE_FALKORDB", "true").lower() == "true"
    
    # Initialize components
    print("Initializing pipeline...")
    extractor = DSPyExtractor(OLLAMA_MODEL, OLLAMA_API_BASE, OLLAMA_API_KEY)
    
    falkordb_client = None
    if USE_FALKORDB:
        FALKORDB_HOST = os.getenv("FALKORDB_HOST", "localhost")
        FALKORDB_PORT = int(os.getenv("FALKORDB_PORT", 6379))
        FALKORDB_GRAPH = os.getenv("FALKORDB_GRAPH", "KnowledgeGraph")
        falkordb_client = FalkorDBClient(FALKORDB_HOST, FALKORDB_PORT, FALKORDB_GRAPH)
        print("✓ FalkorDB client initialized")
    
    # Check for new files in input directory
    processor = InputProcessor(input_dir=INPUT_DIR)
    files_to_process = processor.get_new_or_changed_files()
    
    if not files_to_process:
        print(f"\nNo new files found in '{INPUT_DIR}' directory.")
        print(f"Add .txt, .md, or .json files to '{INPUT_DIR}' and run again.")
        return
    
    print(f"\nFound {len(files_to_process)} file(s) to process:")
    for f in files_to_process:
        print(f"  - {f.name}")
    print()
    
    # Process each file
    for filepath in files_to_process:
        print(f"\n{'#'*60}")
        print(f"Processing: {filepath.name}")
        print(f"{'#'*60}")
        
        content = processor.read_file_content(filepath)
        if content:
            await process_file(content, extractor, falkordb_client)
            processor.mark_as_processed(filepath)
            print(f"✓ Marked {filepath.name} as processed")
        else:
            print(f"⚠ Skipped empty file: {filepath.name}")
    
    # Cleanup
    if falkordb_client:
        falkordb_client.close()
    
    print("\n" + "="*60)
    print("Pipeline complete!")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())