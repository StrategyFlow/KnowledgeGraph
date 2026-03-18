import os
import asyncio
import json
from pathlib import Path
from dotenv import load_dotenv
from main_pipeline.dspy_extractor import DSPyExtractor
from main_pipeline.falkordb_client import FalkorDBClient
from main_pipeline.input_processor import InputProcessor
from main_pipeline.redis_client import RedisClient

load_dotenv()

def _format_graph_url(url_template: str, host: str, port: int, graph: str) -> str:
    if not url_template:
        return ""
    try:
        return url_template.format(host=host, port=port, graph=graph)
    except Exception:
        return url_template

async def process_file(
    content: str,
    extractor: DSPyExtractor,
    falkordb_client=None,
    graph_url: str = "",
    redis_client=None,
    redis_channel: str = "ie_response",
    source_name: str = "",
):
    """Process a single file through the pipeline.

    Returns:
        bool: True when the file can be marked as processed.
    """
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
    mark_processed = True
    if falkordb_client:
        success_count = 0
        query_count = 0
        try:
            queries = extractor.to_falkordb_queries(response)
            query_count = len(queries)
            print(f"Executing {len(queries)} queries in FalkorDB...")
            results = falkordb_client.execute_queries(queries)
            success_count = sum(1 for r in results if r.get("success"))
            print(f"✓ {success_count}/{len(queries)} queries executed successfully in FalkorDB")
            if graph_url:
                print(f"🔗 View graph: {graph_url}")

            # Retry file on next run if FalkorDB writes were partial/failed.
            mark_processed = (query_count == 0) or (success_count == query_count)
            if not mark_processed:
                print(
                    f"⚠ Not marking '{source_name}' as processed because "
                    f"{query_count - success_count} query(ies) failed."
                )
        except Exception as e:
            print(f"✗ Error executing FalkorDB queries: {e}")
            mark_processed = False

        # Publish ingestion status to Redis after FalkorDB load attempt.
        if redis_client:
            try:
                payload = {
                    "event": "falkordb_ingest",
                    "source": source_name,
                    "title": response.get("title") if isinstance(response, dict) else "",
                    "queries_total": query_count,
                    "queries_succeeded": success_count,
                    "falkordb_graph": falkordb_client.graph_name,
                }
                await redis_client.publish(redis_channel, json.dumps(payload, default=str))
                print(f"✓ Published ingest event to Redis channel '{redis_channel}'")
            except Exception as e:
                print(f"✗ Error publishing ingest event to Redis: {e}")
    
    print(f"{'='*60}")
    print("Processing complete!")
    print(f"{'='*60}\n")
    return mark_processed

async def main():
    # Configuration
    INPUT_DIR = os.getenv("INPUT_DIR", "input")
    OLLAMA_API_BASE = os.getenv("OLLAMA_API_BASE", "http://ares.westpoint.edu:11434")
    OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "dspy-ollama")
    USE_FALKORDB = os.getenv("USE_FALKORDB", "true").lower() == "true"
    PUBLISH_REDIS_ON_INGEST = os.getenv("PUBLISH_REDIS_ON_INGEST", "true").lower() == "true"
    REDIS_PUBLISH_CHANNEL = os.getenv("REDIS_PUBLISH_CHANNEL", "ie_response")
    
    # Initialize components
    print("Initializing pipeline...")
    extractor = DSPyExtractor(OLLAMA_MODEL, OLLAMA_API_BASE, OLLAMA_API_KEY)
    
    falkordb_client = None
    graph_url = ""
    if USE_FALKORDB:
        FALKORDB_HOST = os.getenv("FALKORDB_HOST", "ares.westpoint.edu")
        FALKORDB_PORT = int(os.getenv("FALKORDB_PORT", 6379))
        FALKORDB_GRAPH = os.getenv("FALKORDB_GRAPH", "KnowledgeGraph")
        FALKORDB_BROWSER_URL = os.getenv("FALKORDB_BROWSER_URL", "")
        falkordb_client = FalkorDBClient(FALKORDB_HOST, FALKORDB_PORT, FALKORDB_GRAPH)
        print("✓ FalkorDB client initialized")
        print(f"  → Writing to graph: '{FALKORDB_GRAPH}'")
        graph_url = _format_graph_url(FALKORDB_BROWSER_URL, FALKORDB_HOST, FALKORDB_PORT, FALKORDB_GRAPH)
        if graph_url:
            print(f"🔗 Graph browser: {graph_url}")

    redis_client = None
    if USE_FALKORDB and PUBLISH_REDIS_ON_INGEST:
        REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
        REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
        REDIS_DB = int(os.getenv("REDIS_DB", 0))
        try:
            redis_client = RedisClient(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
            await redis_client.r.ping()
            print(f"✓ Redis publish enabled on channel '{REDIS_PUBLISH_CHANNEL}'")
        except Exception as e:
            print(f"⚠ Could not connect to Redis for ingest publishing: {e}")
            redis_client = None
    
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
            should_mark_processed = await process_file(
                content,
                extractor,
                falkordb_client,
                graph_url,
                redis_client,
                REDIS_PUBLISH_CHANNEL,
                filepath.name,
            )
            if should_mark_processed:
                processor.mark_as_processed(filepath)
                print(f"✓ Marked {filepath.name} as processed")
            else:
                print(f"⚠ Leaving {filepath.name} unprocessed for retry on next run")
        else:
            print(f"⚠ Skipped empty file: {filepath.name}")
            processor.mark_as_processed(filepath)
            print(f"✓ Marked empty file {filepath.name} as processed")
    
    # Cleanup
    if falkordb_client:
        falkordb_client.close()
    if redis_client:
        await redis_client.close()
    
    print("\n" + "="*60)
    print("Pipeline complete!")
    print("="*60)

def run():
    asyncio.run(main())

if __name__ == "__main__":
    run()