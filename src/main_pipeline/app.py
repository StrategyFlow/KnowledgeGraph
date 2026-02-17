import os
import asyncio
from dotenv import load_dotenv
from main_pipeline.dspy_extractor import DSPyExtractor
from main_pipeline.redis_client import RedisClient
from main_pipeline.falkordb_client import FalkorDBClient
from main_pipeline.input_processor import InputProcessor

load_dotenv()

def _format_graph_url(url_template: str, host: str, port: int, graph: str) -> str:
    if not url_template:
        return ""
    try:
        return url_template.format(host=host, port=port, graph=graph)
    except Exception:
        return url_template

class AsyncDspyRedis:
    def __init__(self):
        REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
        REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
        REDIS_DB = int(os.getenv("REDIS_DB", 0))
        self.redis_client = RedisClient(REDIS_HOST, REDIS_PORT, db=REDIS_DB)
        OLLAMA_API_BASE = os.getenv("OLLAMA_API_BASE", "http://ares.westpoint.edu:11434")
        OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "")
        OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "dspy-ollama")
        self.extractor = DSPyExtractor(OLLAMA_MODEL, OLLAMA_API_BASE, OLLAMA_API_KEY)
        
        # FalkorDB configuration
        self.use_falkordb = os.getenv("USE_FALKORDB", "true").lower() == "true"
        self.auto_load_falkordb = os.getenv("AUTO_LOAD_FALKORDB", "true").lower() == "true"
        self.falkordb_client = None
        if self.use_falkordb:
            FALKORDB_HOST = os.getenv("FALKORDB_HOST", "localhost")
            FALKORDB_PORT = int(os.getenv("FALKORDB_PORT", 6379))
            FALKORDB_GRAPH = os.getenv("FALKORDB_GRAPH", "KnowledgeGraph")
            FALKORDB_BROWSER_URL = os.getenv("FALKORDB_BROWSER_URL", "")
            self.falkordb_client = FalkorDBClient(FALKORDB_HOST, FALKORDB_PORT, FALKORDB_GRAPH)
            self.graph_url = _format_graph_url(FALKORDB_BROWSER_URL, FALKORDB_HOST, FALKORDB_PORT, FALKORDB_GRAPH)
            if self.graph_url:
                print(f"🔗 Graph browser: {self.graph_url}")
        else:
            self.graph_url = ""
        
        # Input processor configuration
        INPUT_DIR = os.getenv("INPUT_DIR", "input")
        self.input_processor = InputProcessor(input_dir=INPUT_DIR)
        self.watch_files = os.getenv("WATCH_INPUT_FILES", "false").lower() == "true"

    async def listen(self):
        """Listen to Redis pub/sub and optionally watch input folder."""
        await self.redis_client.r.ping()
        print("Connected to Redis server.")
        
        # Create tasks for both Redis listening and file watching
        tasks = [
            asyncio.create_task(self._listen_redis()),
        ]
        
        if self.watch_files:
            tasks.append(
                asyncio.create_task(self._watch_input_files())
            )
        
        await asyncio.gather(*tasks)

    async def _listen_redis(self):
        """Listen to Redis pub/sub channel."""
        await self.redis_client.subscribe("ie_request", self.handle_query)
    
    async def _watch_input_files(self):
        """Watch input folder for new files."""
        print(f"File watching enabled. Monitoring input folder...")
        await self.input_processor.watch_and_process(self.handle_query)
        
    async def handle_query(self, query: str):
        print(f"Received query: {query}")
        response = await self.extractor.extract_info(query)
        
        # Save to files
        try:
            file_paths = self.extractor.save_to_files(response, output_dir="output")
            print(f"Saved to files: {file_paths}")
        except Exception as e:
            print(f"Error saving to files: {e}")
        
        # Execute queries in FalkorDB if enabled
        if self.use_falkordb and self.auto_load_falkordb and self.falkordb_client:
            try:
                queries = self.extractor.to_falkordb_queries(response)
                print(f"Executing {len(queries)} queries in FalkorDB...")
                results = self.falkordb_client.execute_queries(queries)
                success_count = sum(1 for r in results if r.get("success"))
                print(f"✓ {success_count}/{len(queries)} queries executed successfully")
                if self.graph_url:
                    print(f"🔗 View graph: {self.graph_url}")
            except Exception as e:
                print(f"Error executing FalkorDB queries: {e}")
        
        await self.redis_client.publish("ie_response", str(response))
        print(f"Published response to channel ie_response")

    async def close(self):
        await self.redis_client.close()
        if self.falkordb_client:
            self.falkordb_client.close()

def main():
    app = AsyncDspyRedis()
    try:
        asyncio.run(app.listen())
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        asyncio.run(app.close())

if __name__ == "__main__":
    main()
