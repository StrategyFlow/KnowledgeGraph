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
        """Extract comprehensive information from OPORD documents using 5-phase approach."""
        print(f"Extracting info from OPORD ({len(text)} chars)...")
        print("Using 5-phase extraction: Situation → Mission → Execution → Sustainment → C2")
        
        # Run extraction phases sequentially
        phase_results = {}
        phase_results["situation"] = await self._extract_situation(text)
        phase_results["mission"] = await self._extract_mission(text)
        phase_results["execution"] = await self._extract_execution(text)
        phase_results["sustainment"] = await self._extract_sustainment(text)
        phase_results["c2"] = await self._extract_command_and_signal(text)
        
        # Merge phase results with deduplication
        merged = self._merge_phase_results(phase_results)
        
        # Add completeness validation
        self._validate_completeness(merged)
        
        return merged
    
    async def _extract_situation(self, text: str) -> dict:
        """Extract SITUATION section: friendly/enemy strength, disposition, terrain, weather."""
        print("\n[Phase 1/5] Extracting SITUATION...")
        prompt = f"""Extract SITUATION section from OPORD. Return JSON only.

SITUATION includes: friendly disposition/strength, enemy disposition/strength/COA, terrain analysis, weather data, and relevant civil considerations.

Return JSON:
{{
  "phase": "situation",
  "sections": [{{"header": "Situation", "key_points": ["all points about friendly and enemy forces, terrain, weather"]}}],
  "sections": [{{"header": "Terrain", "key_points": ["terrain features, key terrain, obstacles, avenues of approach"]}}],
  "sections": [{{"header": "Weather", "key_points": ["weather data, sunrise/sunset, moonrise/moonset, precipitation"]}}],
  "actors": [{{"name": "unit/enemy name", "actor_type": "unit|enemy_unit|equipment|location"}}],
  "relations": [{{"actor_a": "name1", "actor_b": "name2", "relation_type": "supports|subordinates|occupies", "relation_biography": "context"}}]
}}

TEXT:
{text}"""
        return await self._call_lm_and_parse(prompt, "situation")
    
    async def _extract_mission(self, text: str) -> dict:
        """Extract MISSION section: task organization, commander's intent, end state."""
        print("[Phase 2/5] Extracting MISSION...")
        prompt = f"""Extract MISSION section from OPORD. Return JSON only.

Also extract the OPORD TITLE/OPERATION NAME from anywhere in the document.

MISSION includes: task organization, commander's intent, key guidance, and end state (friendly/enemy/terrain/civil).

Return JSON:
{{
  "phase": "mission",
  "title": "operation name if found",
  "commanders_intent": "complete intent statement",
  "sections": [{{"header": "Mission", "key_points": ["mission task(s), unit composition, chain of command"]}}],
  "sections": [{{"header": "Task Organization", "key_points": ["all OPCON changes, attachments, detachments"]}}],
  "actors": [{{"name": "unit name", "actor_type": "unit|equipment|location"}}],
  "relations": [{{"actor_a": "parent_unit", "actor_b": "subordinate_unit", "relation_type": "subordinate", "relation_biography": "OPCON relationship"}}]
}}

TEXT:
{text}"""
        return await self._call_lm_and_parse(prompt, "mission")
    
    async def _extract_execution(self, text: str) -> dict:
        """Extract EXECUTION section: COA, scheme of maneuver, fires, tasks, coordinating instructions."""
        print("[Phase 3/5] Extracting EXECUTION...")
        prompt = f"""Extract EXECUTION section from OPORD. Return JSON only.

EXECUTION includes: concept of operations (scheme of maneuver), scheme of fires, specific tasks to subordinate units, and coordinating instructions.

Return JSON:
{{
  "phase": "execution",
  "concept_of_operations": "complete scheme of maneuver and overall approach",
  "scheme_of_fires": "artillery/fire support plan and priorities",
  "key_tasks": ["task: do X to achieve Y", "task: do A to achieve B"],
  "timelines": ["DTG: 29 0600 AUG 24 - event", "DTG: 30 2000 AUG 24 - event"],
  "sections": [{{"header": "Concept of Operations", "key_points": ["commander's approach, main effort, supporting efforts"]}}],
  "actors": [{{"name": "unit name", "actor_type": "unit|equipment|objective"}}],
  "relations": [{{"actor_a": "unit1", "actor_b": "unit2", "relation_type": "supports|executes_task", "relation_biography": "task relationship"}}]
}}

TEXT:
{text}"""
        return await self._call_lm_and_parse(prompt, "execution")
    
    async def _extract_sustainment(self, text: str) -> dict:
        """Extract SUSTAINMENT section: logistics, personnel, supply, and support."""
        print("[Phase 4/5] Extracting SUSTAINMENT...")
        prompt = f"""Extract SERVICE SUPPORT / SUSTAINMENT section from OPORD. Return JSON only.

SUSTAINMENT includes: supply operations, transport, maintenance, medical support, casualty procedures, and logistics.

Return JSON:
{{
  "phase": "sustainment",
  "sections": [{{"header": "Sustainment", "key_points": ["supply points, logistics operations, medical support, resupply procedures"]}}],
  "actors": [{{"name": "supply_point|medical_unit|logistics_element", "actor_type": "location|unit|equipment"}}],
  "relations": [{{"actor_a": "unit", "actor_b": "supply_point", "relation_type": "supplied_by|supported_by", "relation_biography": "sustainment relationship"}}]
}}

If sustainment section is not found, return empty arrays.

TEXT:
{text}"""
        return await self._call_lm_and_parse(prompt, "sustainment")
    
    async def _extract_command_and_signal(self, text: str) -> dict:
        """Extract COMMAND AND SIGNAL section: C2, comms, succession of command."""
        print("[Phase 5/5] Extracting COMMAND AND SIGNAL...")
        prompt = f"""Extract COMMAND AND SIGNAL section from OPORD. Return JSON only.

COMMAND AND SIGNAL includes: chain of command, commander location, communications plan, succession of command, and signal security.

Return JSON:
{{
  "phase": "c2",
  "sections": [{{"header": "Command and Signal", "key_points": ["chain of command, commander location, communications plan, succession of command, signal instructions"]}}],
  "actors": [{{"name": "commander|unit|location", "actor_type": "personnel|unit|location"}}],
  "relations": [{{"actor_a": "superior_commander", "actor_b": "subordinate_commander", "relation_type": "commands|reports_to", "relation_biography": "chain of command"}}]
}}

If command and signal section is not found, return empty arrays.

TEXT:
{text}"""
        return await self._call_lm_and_parse(prompt, "c2")
    
    async def _call_lm_and_parse(self, prompt: str, phase_name: str) -> dict:
        """Call LM and parse response with error handling."""
        try:
            response = await self.lm.acall(prompt)
            
            # Handle different response formats
            result = ""
            if isinstance(response, str):
                result = response
            elif isinstance(response, list) and len(response) > 0:
                item = response[0]
                if isinstance(item, str):
                    result = item
                elif isinstance(item, dict):
                    result = item.get("content", item.get("text", str(item)))
            elif isinstance(response, dict):
                if "choices" in response and isinstance(response["choices"], list) and len(response["choices"]) > 0:
                    choice = response["choices"][0]
                    if isinstance(choice, dict) and "message" in choice:
                        result = choice["message"].get("content", "")
                else:
                    result = response.get("content", response.get("text", str(response)))
            else:
                result = str(response)
            
            parsed = self._parse_phase_response(result, phase_name)
            print(f"  ✓ Phase {phase_name} parsed: {len(parsed.get('actors', []))} actors, {len(parsed.get('relations', []))} relations")
            return parsed
        except Exception as e:
            print(f"Error in phase {phase_name}: {e}")
            return self._empty_phase_response(phase_name)
    
    def _parse_phase_response(self, response_text: str, phase_name: str) -> dict:
        """Parse single phase response."""
        import json as json_lib
        
        try:
            sanitized = self._sanitize_json_text(response_text)
            if not sanitized:
                print(f"  ⚠ No JSON found in {phase_name} response")
                return self._empty_phase_response(phase_name)
            
            data = json_lib.loads(sanitized, strict=False)
            
            return {
                "phase": phase_name,
                "title": str(data.get("title", "unknown")).lower().strip() or "unknown",
                "sections": data.get("sections", []),
                "actors": self._normalize_actors(data.get("actors", [])),
                "relations": self._normalize_relations(data.get("relations", [])),
                "commanders_intent": str(data.get("commanders_intent", "")).lower().strip() or "",
                "concept_of_operations": str(data.get("concept_of_operations", "")).lower().strip() or "",
                "scheme_of_fires": str(data.get("scheme_of_fires", "")).lower().strip() or "",
                "key_tasks": [str(t).lower().strip() for t in data.get("key_tasks", []) if t],
                "timelines": [str(t).lower().strip() for t in data.get("timelines", []) if t]
            }
        except Exception as e:
            print(f"  ⚠ Error parsing {phase_name}: {e}")
            return self._empty_phase_response(phase_name)
    
    def _empty_phase_response(self, phase_name: str) -> dict:
        """Return empty response for a single phase."""
        return {
            "phase": phase_name,
            "title": "unknown",
            "sections": [],
            "actors": [],
            "relations": [],
            "commanders_intent": "",
            "concept_of_operations": "",
            "scheme_of_fires": "",
            "key_tasks": [],
            "timelines": []
        }
    
    def _merge_phase_results(self, phase_results: dict) -> dict:
        """Merge results from all 5 phases with deduplication."""
        print("\nMerging phase results with deduplication...")
        
        merged = {
            "title": "unknown",
            "sections": [],
            "actors": [],
            "relations": [],
            "commanders_intent": "",
            "concept_of_operations": "",
            "scheme_of_fires": "",
            "key_tasks": [],
            "timelines": [],
            "actor_types": [],
            "role_types": ["executor", "receiver", "target"],
            "relation_types": []
        }
        
        # Extract title from first phase that has it
        for phase_name in ["situation", "mission", "execution", "sustainment", "c2"]:
            phase = phase_results.get(phase_name, {})
            title = phase.get("title", "unknown").lower().strip()
            if title and title != "unknown":
                merged["title"] = title
                break
        
        # Merge sections (preserve order by phase)
        seen_section_headers = set()
        for phase_name in ["situation", "mission", "execution", "sustainment", "c2"]:
            phase = phase_results.get(phase_name, {})
            for section in phase.get("sections", []):
                header = section.get("header", "").lower().strip()
                if header and header not in seen_section_headers:
                    seen_section_headers.add(header)
                    merged["sections"].append(section)
        
        # Merge actors with deduplication
        seen_actors = {}
        for phase_name in ["situation", "mission", "execution", "sustainment", "c2"]:
            phase = phase_results.get(phase_name, {})
            for actor in phase.get("actors", []):
                actor_name = actor.get("name", "").lower().strip()
                if actor_name and actor_name not in seen_actors:
                    seen_actors[actor_name] = actor
                    merged["actors"].append(actor)
                elif actor_name and actor_name in seen_actors:
                    # If we see the same actor again with a type, update if empty
                    existing = seen_actors[actor_name]
                    if not existing.get("actor_type") and actor.get("actor_type"):
                        existing["actor_type"] = actor.get("actor_type")
        
        # Merge relations with deduplication
        seen_relations = set()
        for phase_name in ["situation", "mission", "execution", "sustainment", "c2"]:
            phase = phase_results.get(phase_name, {})
            for relation in phase.get("relations", []):
                rel_key = (
                    relation.get("actor_a", "").lower().strip(),
                    relation.get("actor_b", "").lower().strip(),
                    relation.get("relation_type", "").lower().strip()
                )
                if rel_key not in seen_relations and all(rel_key):
                    seen_relations.add(rel_key)
                    merged["relations"].append(relation)
        
        # Merge text fields (take first non-empty)
        for field in ["commanders_intent", "concept_of_operations", "scheme_of_fires"]:
            for phase_name in ["situation", "mission", "execution", "sustainment", "c2"]:
                phase = phase_results.get(phase_name, {})
                if not merged[field] and phase.get(field):
                    merged[field] = phase.get(field)
        
        # Merge lists with deduplication
        seen_tasks = set()
        for phase_name in ["situation", "mission", "execution", "sustainment", "c2"]:
            phase = phase_results.get(phase_name, {})
            for task in phase.get("key_tasks", []):
                task_clean = task.lower().strip()
                if task_clean and task_clean not in seen_tasks:
                    seen_tasks.add(task_clean)
                    merged["key_tasks"].append(task)
        
        seen_timelines = set()
        for phase_name in ["situation", "mission", "execution", "sustainment", "c2"]:
            phase = phase_results.get(phase_name, {})
            for timeline in phase.get("timelines", []):
                timeline_clean = timeline.lower().strip()
                if timeline_clean and timeline_clean not in seen_timelines:
                    seen_timelines.add(timeline_clean)
                    merged["timelines"].append(timeline)
        
        # Extract and deduplicate actor types and relation types
        actor_types = set()
        for actor in merged["actors"]:
            atype = actor.get("actor_type", "").lower().strip()
            if atype:
                actor_types.add(atype)
        merged["actor_types"] = sorted(list(actor_types))
        
        relation_types = set()
        for relation in merged["relations"]:
            rtype = relation.get("relation_type", "").lower().strip()
            if rtype:
                relation_types.add(rtype)
        merged["relation_types"] = sorted(list(relation_types))
        
        print(f"  ✓ Merged: {len(merged['sections'])} sections, {len(merged['actors'])} unique actors, {len(merged['relations'])} unique relations")
        print(f"  ✓ Key tasks: {len(merged['key_tasks'])}, Timelines: {len(merged['timelines'])}")
        
        return merged
    
    def _validate_completeness(self, extracted: dict) -> None:
        """Validate extraction completeness and warn if missing major sections."""
        print("\nValidation Summary:")
        
        section_headers = {s.get("header", "").lower() for s in extracted.get("sections", [])}
        
        expected_sections = {"situation", "mission", "execution", "sustainment", "command and signal"}
        found_sections = section_headers & expected_sections
        missing_sections = expected_sections - found_sections
        
        if missing_sections:
            print(f"  ⚠ Missing sections: {', '.join(sorted(missing_sections))}")
        else:
            print(f"  ✓ All major OPORD sections found")
        
        print(f"  ✓ Extracted title: {extracted['title']}")
        print(f"  ✓ Sections: {len(extracted['sections'])}")
        print(f"  ✓ Actors: {len(extracted['actors'])}")
        print(f"  ✓ Relations: {len(extracted['relations'])}")
        print(f"  ✓ Key Tasks: {len(extracted['key_tasks'])}")
        print(f"  ✓ Timelines: {len(extracted['timelines'])}")
        print(f"  ✓ Commander's Intent: {'Yes' if extracted['commanders_intent'] else 'No'}")
        print(f"  ✓ Concept of Operations: {'Yes' if extracted['concept_of_operations'] else 'No'}")
        print(f"  ✓ Scheme of Fires: {'Yes' if extracted['scheme_of_fires'] else 'No'}")
    
    def to_falkordb_queries(self, extracted_data: dict) -> list[str]:
        """Convert extracted data to FalkorDB Cypher queries."""
        queries = []
        
        print(f"\nGenerating Cypher queries from extracted data...")
        
        # Create document/OPORD node
        doc_title = self._escape(extracted_data.get("title", "unknown"))
        queries.append(f"MERGE (doc:Document {{title: '{doc_title}', type: 'OPORD'}})")
        
        # Create and link sections with their key_points as content
        sections = extracted_data.get("sections", [])
        for section in sections:
            if isinstance(section, dict):
                header = self._escape(section.get("header", "unknown"))
                key_points = section.get("key_points", [])
                content = self._escape(" | ".join(str(p) for p in key_points if p)[:1000])
                queries.append(
                    f"MERGE (s:Section {{title: '{header}'}}) "
                    f"SET s.content = '{content}' "
                    f"MERGE (doc:Document {{title: '{doc_title}'}}) "
                    f"MERGE (doc)-[:CONTAINS_SECTION]->(s)"
                )
        
        # Create commanders intent node
        commanders_intent = extracted_data.get("commanders_intent", "")
        if commanders_intent:
            intent_text = self._escape(commanders_intent[:500])
            queries.append(
                f"MERGE (ci:CommandersIntent {{content: '{intent_text}'}}) "
                f"MERGE (doc:Document {{title: '{doc_title}'}}) "
                f"MERGE (doc)-[:HAS_GUIDANCE]->(ci)"
            )
        
        # Create concept of operations node
        concept_of_ops = extracted_data.get("concept_of_operations", "")
        if concept_of_ops:
            coa_text = self._escape(concept_of_ops[:500])
            queries.append(
                f"MERGE (coa:ConceptOfOperations {{content: '{coa_text}'}}) "
                f"MERGE (doc:Document {{title: '{doc_title}'}}) "
                f"MERGE (doc)-[:HAS_COA]->(coa)"
            )
        
        # Create scheme of fires node
        scheme_of_fires = extracted_data.get("scheme_of_fires", "")
        if scheme_of_fires:
            fires_text = self._escape(scheme_of_fires[:500])
            queries.append(
                f"MERGE (sof:SchemeOfFires {{content: '{fires_text}'}}) "
                f"MERGE (doc:Document {{title: '{doc_title}'}}) "
                f"MERGE (doc)-[:HAS_FIRES]->(sof)"
            )
        
        # Create key task nodes
        for i, task in enumerate(extracted_data.get("key_tasks", [])):
            if task:
                task_text = self._escape(str(task)[:300])
                queries.append(
                    f"MERGE (kt:KeyTask {{content: '{task_text}'}}) "
                    f"MERGE (doc:Document {{title: '{doc_title}'}}) "
                    f"MERGE (doc)-[:HAS_KEY_TASK]->(kt)"
                )
        
        # Create timeline nodes
        for timeline_entry in extracted_data.get("timelines", []):
            if timeline_entry:
                tl_text = self._escape(str(timeline_entry)[:300])
                queries.append(
                    f"MERGE (tl:Timeline {{event: '{tl_text}'}}) "
                    f"MERGE (doc:Document {{title: '{doc_title}'}}) "
                    f"MERGE (doc)-[:HAS_TIMELINE]->(tl)"
                )
        
        # Build actor type and relation type nodes
        known_actor_types = {
            self._clean_text(actor_type)
            for actor_type in extracted_data.get("actor_types", [])
            if self._clean_text(actor_type)
        }
        
        # Build actor map and infer missing types
        actors_by_name = {}
        for actor in extracted_data.get("actors", []):
            raw_name = self._clean_text(actor.get("name", ""))
            raw_type = self._clean_text(actor.get("actor_type", ""))
            if not raw_name:
                continue

            if not raw_type:
                raw_type = self._infer_actor_type(raw_name, known_actor_types)
                if raw_type:
                    print(f"  ℹ Inferred actor type '{raw_type}' for '{raw_name}'")

            if raw_type:
                actors_by_name[raw_name] = raw_type
                known_actor_types.add(raw_type)

        # Keep only fully-specified relations
        valid_relations = []
        for relation in extracted_data.get("relations", []):
            actor_a = self._clean_text(relation.get("actor_a", ""))
            actor_b = self._clean_text(relation.get("actor_b", ""))
            relation_type = self._clean_text(relation.get("relation_type", ""))

            if not actor_a or not actor_b or not relation_type:
                continue

            if actor_a not in actors_by_name:
                inferred = self._infer_actor_type(actor_a, known_actor_types)
                if inferred:
                    actors_by_name[actor_a] = inferred
                    known_actor_types.add(inferred)
                    print(f"  ℹ Inferred actor type '{inferred}' for '{actor_a}' from relation")

            if actor_b not in actors_by_name:
                inferred = self._infer_actor_type(actor_b, known_actor_types)
                if inferred:
                    actors_by_name[actor_b] = inferred
                    known_actor_types.add(inferred)
                    print(f"  ℹ Inferred actor type '{inferred}' for '{actor_b}' from relation")

            if actor_a not in actors_by_name or actor_b not in actors_by_name:
                print(
                    f"  ⚠ Skipping relation with untyped actor(s): "
                    f"{actor_a} -> {actor_b}"
                )
                continue

            valid_relations.append({
                "actor_a": actor_a,
                "actor_b": actor_b,
                "relation_type": relation_type,
                "role_a": self._clean_text(relation.get("role_a", "")),
                "role_b": self._clean_text(relation.get("role_b", "")),
                "relation_biography": self._clean_text(relation.get("relation_biography", "")),
            })

        # Create nodes for ALL known actors (not just those in relations)
        all_actor_names = set(actors_by_name.keys())
        for relation in valid_relations:
            all_actor_names.add(relation["actor_a"])
            all_actor_names.add(relation["actor_b"])

        actor_types = {actors_by_name[name] for name in all_actor_names if name in actors_by_name}
        role_types = {
            relation[field]
            for relation in valid_relations
            for field in ("role_a", "role_b")
            if relation[field]
        }
        relation_types = {relation["relation_type"] for relation in valid_relations}

        for actor_type in sorted(actor_types):
            queries.append(f"MERGE (:ActorType {{name: '{self._escape(actor_type)}'}})") 

        for role_type in sorted(role_types):
            queries.append(f"MERGE (:RoleType {{name: '{self._escape(role_type)}'}})") 

        for relation_type in sorted(relation_types):
            queries.append(f"MERGE (:RelationType {{name: '{self._escape(relation_type)}'}})") 

        for actor_name in sorted(all_actor_names):
            actor_type = actors_by_name.get(actor_name, "unknown")
            queries.append(
                f"MERGE (a:Actor {{name: '{self._escape(actor_name)}'}}) "
                f"MERGE (at:ActorType {{name: '{self._escape(actor_type)}'}}) "
                f"MERGE (a)-[:HAS_TYPE]->(at) "
                f"MERGE (doc:Document {{title: '{doc_title}'}}) "
                f"MERGE (doc)-[:MENTIONS]->(a)"
            )

        relation_count = 0
        for relation in valid_relations:
            actor_a = self._escape(relation["actor_a"])
            actor_b = self._escape(relation["actor_b"])
            relation_type = self._escape(relation["relation_type"])
            role_a = self._escape(relation["role_a"])
            role_b = self._escape(relation["role_b"])
            biography = self._escape(relation["relation_biography"])

            relation_count += 1

            query_parts = [
                f"MATCH (a1:Actor {{name: '{actor_a}'}}), (a2:Actor {{name: '{actor_b}'}})",
                f"MERGE (rt:RelationType {{name: '{relation_type}'}})",
            ]

            rel_props = []
            if biography:
                rel_props.append(f"biography: '{biography}'")

            rel_props_str = ", ".join(rel_props) if rel_props else ""
            props = f" {{{rel_props_str}}}" if rel_props_str else ""

            query_parts.append(f"MERGE (r:Relation{props})")
            query_parts.append(f"MERGE (a1)-[:PARTICIPATES_IN]->(r)")
            query_parts.append(f"MERGE (r)-[:PARTICIPATES_IN]->(a2)")
            query_parts.append(f"MERGE (r)-[:HAS_TYPE]->(rt)")

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
        
        print(f"Generated {len(queries)} total queries ({relation_count} relations, {len(sections)} sections)")
        return queries

    def _clean_text(self, value: str) -> str:
        """Normalize extracted text fields and treat placeholders as empty."""
        cleaned = str(value).strip().lower()
        if cleaned in {"", "unknown", "none", "null", "n/a", "na", "unspecified"}:
            return ""
        return cleaned

    def _infer_actor_type(self, actor_name: str, known_actor_types: set[str]) -> str:
        """Infer actor type from actor name, preferring known schema terms when available."""
        name = self._clean_text(actor_name)
        if not name:
            return ""

        normalized = (
            name.replace("1 st", "1st")
            .replace("2 nd", "2nd")
            .replace("3 rd", "3rd")
            .replace("4 th", "4th")
            .replace("sqd", "squad")
            .replace("wpn", "weapon")
            .replace("eny", "enemy")
            .replace("obj", "objective")
        )

        def pick(preferred: str, aliases: list[str]) -> str:
            for candidate in known_actor_types:
                if candidate in aliases:
                    return candidate
            return preferred

        location_tokens = ["objective", "lz", "lzs", "range", "city", "town", "country", "province", "airfield", "bridge"]
        unit_tokens = ["squad", "battalion", "brigade", "ibct", "forces", "platoon", "company", "troop", "division", "regiment", "in"]
        organization_tokens = ["congress", "government", "ministry", "hq", "headquarters", "command"]
        equipment_tokens = ["gun", "weapon", "artillery", "launcher"]

        if any(token in normalized for token in location_tokens):
            return pick("location", ["location", "place", "terrain", "objective"])
        if any(token in normalized for token in unit_tokens):
            return pick("military_unit", ["military_unit", "unit", "force", "forces", "organization"])
        if any(token in normalized for token in organization_tokens):
            return pick("organization", ["organization", "institution", "government"])
        if any(token in normalized for token in equipment_tokens):
            return pick("equipment", ["equipment", "weapon", "asset"])

        if any(char.isdigit() for char in normalized):
            return pick("military_unit", ["military_unit", "unit", "force", "forces", "organization"])

        return ""
    
    def _empty_response(self) -> dict:
        """Return empty response structure."""
        return {
            "title": "unknown",
            "actor_types": [],
            "role_types": [],
            "relation_types": [],
            "actors": [],
            "relations": [],
            "sections": [],
            "commanders_intent": "",
            "concept_of_operations": "",
            "scheme_of_fires": "",
            "key_tasks": [],
            "timelines": []
        }

    def _sanitize_json_text(self, response_text: str) -> str:
        """Remove control characters that commonly break JSON parsing."""
        import re

        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if not json_match:
            return ""

        candidate = json_match.group()
        return re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', ' ', candidate)
    
    
    def _parse_comprehensive_response(self, response_text: str) -> dict:
        """Parse comprehensive OPORD extraction response."""
        import json as json_lib
        
        try:
            sanitized = self._sanitize_json_text(response_text)
            if not sanitized:
                print("No JSON found in response")
                return self._empty_response()
            
            data = json_lib.loads(sanitized, strict=False)
            
            sections = data.get("sections", [])
            
            # Build actors list
            actors = []
            actor_types = set()
            seen_names = set()
            
            for actor in data.get("actors", []):
                if isinstance(actor, dict):
                    name = str(actor.get("name", "")).lower().strip()
                    atype = str(actor.get("type", "")).lower().strip()
                    if name and name not in seen_names:
                        seen_names.add(name)
                        actors.append({"name": name, "actor_type": atype})
                        if atype:
                            actor_types.add(atype)
            
            # Extract relationships
            relations = []
            relation_types = set()
            
            for rel in data.get("relationships", []):
                if isinstance(rel, dict):
                    actor_a = str(rel.get("actor_a", "")).lower().strip()
                    actor_b = str(rel.get("actor_b", "")).lower().strip()
                    rtype = str(rel.get("type", "")).lower().strip()
                    context = str(rel.get("context", "")).lower().strip()
                    
                    if actor_a and actor_b and rtype:
                        relations.append({
                            "actor_a": actor_a,
                            "actor_b": actor_b,
                            "relation_type": rtype,
                            "role_a": "",
                            "role_b": "",
                            "relation_biography": context
                        })
                        relation_types.add(rtype)
            
            commanders_intent = str(data.get("commanders_intent", "")).lower().strip()
            concept_of_ops = str(data.get("concept_of_operations", "")).lower().strip()
            scheme_of_fires = str(data.get("scheme_of_fires", "")).lower().strip()
            key_tasks = [str(t).lower().strip() for t in data.get("key_tasks", []) if t]
            timelines = [str(t).lower().strip() for t in data.get("timelines", []) if t]
            
            result = {
                "title": str(data.get("title", "unknown")).lower().strip(),
                "actor_types": [str(t).lower().strip() for t in actor_types if t],
                "role_types": ["executor", "receiver", "target"],
                "relation_types": [str(t).lower().strip() for t in relation_types if t],
                "actors": actors,
                "relations": relations,
                "sections": sections,
                "commanders_intent": commanders_intent,
                "concept_of_operations": concept_of_ops,
                "scheme_of_fires": scheme_of_fires,
                "key_tasks": key_tasks,
                "timelines": timelines
            }
            
            print(f"✓ Extracted title: {result['title']}")
            print(f"✓ Sections: {len(sections)}")
            print(f"✓ Actors: {len(actors)}")
            print(f"✓ Relations: {len(relations)}")
            print(f"✓ Key Tasks: {len(key_tasks)}")
            print(f"✓ Timelines: {len(timelines)}")
            print(f"✓ Commander's Intent: {'Yes' if commanders_intent else 'No'}")
            print(f"✓ Scheme of Fires: {'Yes' if scheme_of_fires else 'No'}")
            
            return result
            
        except json_lib.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
        except Exception as e:
            print(f"Error parsing comprehensive response: {e}")
            import traceback
            traceback.print_exc()
        
        return self._empty_response()
    
    def _parse_lm_response(self, response_text: str) -> dict:
        """Parse LM response as JSON."""
        import json as json_lib
        
        # Try to extract JSON from response
        try:
            sanitized = self._sanitize_json_text(response_text)
            if sanitized:
                data = json_lib.loads(sanitized, strict=False)
                
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

