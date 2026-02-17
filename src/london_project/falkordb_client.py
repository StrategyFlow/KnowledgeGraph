from falkordb import FalkorDB
from typing import List, Optional

class FalkorDBClient:
    """Client for connecting to FalkorDB and executing queries."""
    
    def __init__(self, host: str = "localhost", port: int = 6379, graph_name: str = "KnowledgeGraph"):
        """Initialize FalkorDB connection.
        
        Args:
            host: FalkorDB host (default: localhost)
            port: FalkorDB port (default: 6379)
            graph_name: Name of the graph to use
        """
        self.db = FalkorDB(host=host, port=port)
        self.graph_name = graph_name
        self.graph = self.db.select_graph(graph_name)
    
    def execute_query(self, query: str) -> Optional[dict]:
        """Execute a single Cypher query.
        
        Args:
            query: Cypher query string
            
        Returns:
            Query result or None if execution fails
        """
        try:
            result = self.graph.query(query)
            return {
                "success": True,
                "result_set": result.result_set if hasattr(result, 'result_set') else [],
                "nodes_created": result.nodes_created if hasattr(result, 'nodes_created') else 0,
                "relationships_created": result.relationships_created if hasattr(result, 'relationships_created') else 0,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "query": query
            }
    
    def execute_queries(self, queries: List[str]) -> List[dict]:
        """Execute multiple Cypher queries.
        
        Args:
            queries: List of Cypher query strings
            
        Returns:
            List of results for each query
        """
        results = []
        for i, query in enumerate(queries, 1):
            print(f"Executing query {i}/{len(queries)}...")
            result = self.execute_query(query)
            results.append(result)
            if not result.get("success"):
                print(f"  ❌ Query {i} failed: {result.get('error')}")
            else:
                print(f"  ✓ Query {i} succeeded")
        return results
    
    def query_actors(self) -> List[dict]:
        """Query all actors in the graph.
        
        Returns:
            List of actor nodes
        """
        result = self.graph.query("MATCH (a:Actor) RETURN a.name as name")
        return [{"name": row[0]} for row in result.result_set]
    
    def query_relations(self) -> List[dict]:
        """Query all relations in the graph.
        
        Returns:
            List of relations with actors
        """
        query = """
        MATCH (a1:Actor)-[:PARTICIPATES_IN]->(r:Relation)-[:PARTICIPATES_IN]->(a2:Actor)
        OPTIONAL MATCH (r)-[:HAS_TYPE]->(rt:RelationType)
        RETURN a1.name as actor_a, a2.name as actor_b, 
               rt.name as relation_type, r.biography as biography
        """
        result = self.graph.query(query)
        return [
            {
                "actor_a": row[0],
                "actor_b": row[1],
                "relation_type": row[2],
                "biography": row[3]
            }
            for row in result.result_set
        ]
    
    def clear_graph(self):
        """Delete all nodes and relationships in the graph."""
        try:
            self.graph.query("MATCH (n) DETACH DELETE n")
            print(f"Graph '{self.graph_name}' cleared.")
        except Exception as e:
            print(f"Error clearing graph: {e}")
    
    def close(self):
        """Close the database connection."""
        # FalkorDB client doesn't require explicit close
        pass
