import dspy
import json
from pathlib import Path

class DSPyExtractor:
    """Class for extracting structured information from text using DSPy."""

    def __init__(self, model: str, api_base: str, api_key: str):
        import dspy
        self.lm = dspy.LM(
            f'ollama_chat/{model}',
            api_base=api_base,
            api_key=api_key,
            model_type="chat"
        )
        dspy.configure(lm=self.lm)

    async def extract_info(self, text: str) -> dict:
        """Extract structured information from the given text."""
        print(f"Extracting info from text ({len(text)} chars)...")
        
        # Use simple LM call instead of DSPy structured output
        prompt = f"""Extract the following information from this text and return as JSON:
- title: the name/title of the story
- actor_types: list of distinct character types (e.g., "human", "animal", "mythical")
- role_types: list of distinct roles (e.g., "protagonist", "helper", "villain")
- relation_types: list of types of relationships (e.g., "friendship", "conflict", "family")
- actors: list of {{name, actor_type}} objects
- relations: list of {{actor_a, actor_b, relation_type}} objects

TEXT:
{text[:2000]}

Return ONLY valid JSON with no other text:"""
        
        try:
            response = await self.lm.acall(prompt)
            
            # Handle different response formats
            result = ""
            if isinstance(response, str):
                result = response
            elif isinstance(response, list) and len(response) > 0:
                # List of responses, take first
                item = response[0]
                if isinstance(item, str):
                    result = item
                elif isinstance(item, dict):
                    result = item.get("content", item.get("text", str(item)))
            elif isinstance(response, dict):
                # Dict response
                if "choices" in response and isinstance(response["choices"], list) and len(response["choices"]) > 0:
                    choice = response["choices"][0]
                    if isinstance(choice, dict) and "message" in choice:
                        result = choice["message"].get("content", "")
                else:
                    result = response.get("content", response.get("text", str(response)))
            else:
                result = str(response)
            
            print(f"LM Response: {result[:200]}...")
            return self._parse_lm_response(result)
        except Exception as e:
            print(f"Error calling LM: {e}")
            import traceback
            traceback.print_exc()
            return self._empty_response()
    
    def to_falkordb_queries(self, extracted_data: dict) -> list[str]:
        """Convert extracted data to FalkorDB Cypher queries."""
        queries = []
        
        print(f"\nGenerating Cypher queries from extracted data...")
        
        # Create Actor Type nodes
        for actor_type in extracted_data.get("actor_types", []):
            if actor_type:
                queries.append(f"MERGE (:ActorType {{name: '{self._escape(actor_type)}'}})")
        
        # Create Role Type nodes
        for role_type in extracted_data.get("role_types", []):
            if role_type:
                queries.append(f"MERGE (:RoleType {{name: '{self._escape(role_type)}'}})")
        
        # Create Relation Type nodes
        for relation_type in extracted_data.get("relation_types", []):
            if relation_type:
                queries.append(f"MERGE (:RelationType {{name: '{self._escape(relation_type)}'}})")
        
        # Create Actor nodes with their types
        for actor in extracted_data.get("actors", []):
            actor_name = self._escape(actor.get("name", ""))
            actor_type = self._escape(actor.get("actor_type", ""))
            
            if actor_name:
                if actor_type:
                    queries.append(
                        f"MERGE (a:Actor {{name: '{actor_name}'}}) "
                        f"MERGE (at:ActorType {{name: '{actor_type}'}}) "
                        f"MERGE (a)-[:HAS_TYPE]->(at)"
                    )
                else:
                    queries.append(f"MERGE (:Actor {{name: '{actor_name}'}})")
        
        # Create Relations with roles
        relation_count = 0
        for relation in extracted_data.get("relations", []):
            actor_a = self._escape(relation.get("actor_a", ""))
            actor_b = self._escape(relation.get("actor_b", ""))
            relation_type = self._escape(relation.get("relation_type", ""))
            role_a = self._escape(relation.get("role_a", ""))
            role_b = self._escape(relation.get("role_b", ""))
            biography = self._escape(relation.get("relation_biography", ""))
            
            if not actor_a or not actor_b:
                print(f"  ⚠ Skipping relation with missing actors: {actor_a} -> {actor_b}")
                continue
            
            relation_count += 1
            
            # Build the relationship query
            query_parts = [
                f"MATCH (a1:Actor {{name: '{actor_a}'}}), (a2:Actor {{name: '{actor_b}'}})",
            ]
            
            if relation_type:
                query_parts.append(f"MERGE (rt:RelationType {{name: '{relation_type}'}})")
            
            # Create the main relation with biography
            rel_props = []
            if biography:
                rel_props.append(f"biography: '{biography}'")
            
            rel_props_str = ", ".join(rel_props) if rel_props else ""
            props = f" {{{rel_props_str}}}" if rel_props_str else ""
            
            query_parts.append(f"MERGE (r:Relation{props})")
            query_parts.append(f"MERGE (a1)-[:PARTICIPATES_IN]->(r)")
            query_parts.append(f"MERGE (r)-[:PARTICIPATES_IN]->(a2)")
            
            if relation_type:
                query_parts.append(f"MERGE (r)-[:HAS_TYPE]->(rt)")
            
            # Add roles
            if role_a:
                query_parts.append(
                    f"MERGE (rta:RoleType {{name: '{role_a}'}}) "
                    f"MERGE (a1)-[:PLAYS_ROLE {{in_relation: id(r)}}]->(rta)"
                )
            
            if role_b:
                query_parts.append(
                    f"MERGE (rtb:RoleType {{name: '{role_b}'}}) "
                    f"MERGE (a2)-[:PLAYS_ROLE {{in_relation: id(r)}}]->(rtb)"
                )
            
            queries.append(" ".join(query_parts))
        
        print(f"Generated {len(queries)} total queries ({relation_count} relations)")
        return queries
    
    def _empty_response(self) -> dict:
        """Return empty response structure."""
        return {
            "title": "unknown",
            "actor_types": [],
            "role_types": [],
            "relation_types": [],
            "actors": [],
            "relations": []
        }
    
    def _parse_lm_response(self, response_text: str) -> dict:
        """Parse LM response as JSON."""
        import json as json_lib
        import re
        
        # Try to extract JSON from response
        try:
            # Look for JSON block
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                data = json_lib.loads(json_match.group())
                
                # Normalize all data to lowercase for consistency
                title = str(data.get("title", "unknown")).lower().strip()
                actor_types = [str(at).lower().strip() for at in data.get("actor_types", [])]
                role_types = [str(rt).lower().strip() for rt in data.get("role_types", [])]
                relation_types = [str(relt).lower().strip() for relt in data.get("relation_types", [])]
                
                actors = self._normalize_actors(data.get("actors", []))
                relations = self._normalize_relations(data.get("relations", []))
                
                result = {
                    "title": title,
                    "actor_types": list(set(actor_types)),  # Deduplicate
                    "role_types": list(set(role_types)),    # Deduplicate
                    "relation_types": list(set(relation_types)),  # Deduplicate
                    "actors": actors,
                    "relations": relations
                }
                
                # Log extraction results
                print(f"✓ Extracted title: {result['title']}")
                print(f"✓ Actor types: {result['actor_types']}")
                print(f"✓ Role types: {result['role_types']}")
                print(f"✓ Relation types: {result['relation_types']}")
                print(f"✓ Actors: {len(result['actors'])} found")
                print(f"✓ Relations: {len(result['relations'])} found")
                
                if result['relations']:
                    for i, rel in enumerate(result['relations'][:3], 1):
                        print(f"  Relation {i}: {rel.get('actor_a')} --[{rel.get('relation_type')}]--> {rel.get('actor_b')}")
                
                return result
        except json_lib.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
        except Exception as e:
            print(f"Error parsing response: {e}")
        
        return self._empty_response()
    
    def _normalize_actors(self, actors) -> list:
        """Normalize actor list - lowercase and deduplicate."""
        result = []
        seen_names = set()
        
        if not isinstance(actors, list):
            return result
        
        for actor in actors:
            if isinstance(actor, dict):
                name = str(actor.get("name", "")).lower().strip()
                actor_type = str(actor.get("actor_type", actor.get("type", ""))).lower().strip()
                
                if name and name not in seen_names:
                    seen_names.add(name)
                    result.append({
                        "name": name,
                        "actor_type": actor_type
                    })
            elif isinstance(actor, str):
                name = str(actor).lower().strip()
                if name and name not in seen_names:
                    seen_names.add(name)
                    result.append({"name": name, "actor_type": ""})
        
        return result
    
    def _normalize_relations(self, relations) -> list:
        """Normalize relations list - ensure actor_a and actor_b are present and lowercase."""
        result = []
        
        if not isinstance(relations, list):
            return result
        
        for rel in relations:
            if isinstance(rel, dict):
                # Extract with multiple possible field names
                actor_a = str(rel.get("actor_a", rel.get("actor1", rel.get("from", "")))).lower().strip()
                actor_b = str(rel.get("actor_b", rel.get("actor2", rel.get("to", "")))).lower().strip()
                relation_type = str(rel.get("relation_type", rel.get("relation", rel.get("type", "")))).lower().strip()
                role_a = str(rel.get("role_a", "")).lower().strip()
                role_b = str(rel.get("role_b", "")).lower().strip()
                biography = str(rel.get("biography", rel.get("description", ""))).lower().strip()
                
                # Only add if we have both actors
                if actor_a and actor_b:
                    result.append({
                        "actor_a": actor_a,
                        "actor_b": actor_b,
                        "relation_type": relation_type,
                        "role_a": role_a,
                        "role_b": role_b,
                        "relation_biography": biography
                    })
        
        return result
    
    def _normalize_response(self, result) -> dict:
        """Normalize LM response with flexible field name parsing."""
        output = {}
        
        # Get raw output as string if available
        if hasattr(result, 'text'):
            try:
                import json as json_lib
                data = json_lib.loads(result.text)
            except:
                data = {}
        else:
            data = result.__dict__ if hasattr(result, '__dict__') else {}
        
        # Normalize field names (remove ## markers if present)
        normalized = {}
        for key, value in data.items():
            clean_key = key.replace('##', '').strip()
            normalized[clean_key] = value
        
        # Map to expected fields
        output["title"] = normalized.get("title", "unknown")
        output["actor_types"] = normalized.get("actor_types", [])
        output["role_types"] = normalized.get("role_types", [])
        output["relation_types"] = normalized.get("relation_types", [])
        
        # Normalize actors
        actors = normalized.get("actors", [])
        output["actors"] = []
        for actor in actors:
            if isinstance(actor, dict):
                output["actors"].append({
                    "name": actor.get("name", ""),
                    "actor_type": actor.get("type", actor.get("actor_type", ""))
                })
        
        # Normalize relations
        relations = normalized.get("relations", [])
        output["relations"] = []
        for rel in relations:
            if isinstance(rel, dict):
                output["relations"].append({
                    "actor_a": rel.get("actor1", rel.get("actor_a", "")),
                    "actor_b": rel.get("actor2", rel.get("actor_b", "")),
                    "relation_type": rel.get("relation", rel.get("relation_type", "")),
                    "role_a": rel.get("role_a", ""),
                    "role_b": rel.get("role_b", ""),
                    "relation_biography": rel.get("biography", "")
                })
        
        return output
    
    def _escape(self, value: str) -> str:
        """Escape single quotes for Cypher queries."""
        if isinstance(value, str):
            return value.replace("'", "\\'")
        return str(value)
    
    def save_to_files(self, extracted_data: dict, output_dir: str = ".") -> dict:
        """Save extracted data and FalkorDB queries to files.
        
        Args:
            extracted_data: The extracted information dictionary
            output_dir: Directory to save files (default: current directory)
            
        Returns:
            Dictionary with paths to created files
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        title = extracted_data.get("title", "output").replace(" ", "_").replace("/", "_")
        
        # Save extracted data as JSON
        json_file = output_path / f"{title}_extracted.json"
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(extracted_data, f, indent=2, ensure_ascii=False)
        
        # Generate and save FalkorDB queries
        queries = self.to_falkordb_queries(extracted_data)
        cypher_file = output_path / f"{title}_falkordb.cypher"
        with open(cypher_file, "w", encoding="utf-8") as f:
            f.write("// FalkorDB Cypher Queries\n")
            f.write(f"// Generated from: {title}\n\n")
            for i, query in enumerate(queries, 1):
                f.write(f"// Query {i}\n")
                f.write(query + ";\n\n")
        
        return {
            "json_file": str(json_file),
            "cypher_file": str(cypher_file),
            "num_queries": len(queries)
        }

class ExtractInfoSimple(dspy.Signature):
    """Extract structured information from text and return as JSON."""
    text: str = dspy.InputField()
    output: str = dspy.OutputField(
        desc="Complete JSON with: title, actor_types (list), role_types (list), relation_types (list), actors (list with name/type), relations (list with actor1, actor2, relation)"
    )

