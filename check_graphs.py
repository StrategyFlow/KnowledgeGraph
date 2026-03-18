import os
from dotenv import load_dotenv

load_dotenv()

host = os.getenv("FALKORDB_HOST", "localhost")
port = int(os.getenv("FALKORDB_PORT", 6379))
graph = os.getenv("FALKORDB_GRAPH", "KnowledgeGraph")

print(f"Config loaded from .env:")
print(f"  Host: {host}")
print(f"  Port: {port}")
print(f"  Graph: {graph}")

try:
    from falkordb import FalkorDB
    db = FalkorDB(host=host, port=port)
    
    # Try to query both possible graphs
    print("\nAttempting to query graphs...")
    
    for graph_name in ["KnowledgeGraph", "KnowledgeGraphTest"]:
        try:
            g = db.select_graph(graph_name)
            result = g.query("MATCH (doc:Document) RETURN doc LIMIT 1")
            print(f"\n✓ Graph '{graph_name}' exists and has {len(result)} results")
        except Exception as e:
            print(f"\n✗ Graph '{graph_name}': {str(e)[:80]}")
            
except Exception as e:
    print(f"Connection error: {e}")
