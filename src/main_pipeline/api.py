import os
import json
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from main_pipeline.falkordb_client import FalkorDBClient

load_dotenv()


def _escape(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace("'", "\\'")


def _title_where_clause(title: Optional[str]) -> str:
    if not title:
        return ""
    return f"WHERE toLower(d.title) = '{_escape(title.lower())}'"


def _run_query(client: FalkorDBClient, query: str) -> list[list[Any]]:
    result = client.graph.query(query)
    return result.result_set if hasattr(result, "result_set") else []


def create_app() -> FastAPI:
    app = FastAPI(title="OPORD KnowledgeGraph API", version="2.0.0")

    cors_origins = os.getenv("API_CORS_ORIGINS", "*")
    origins = [o.strip() for o in cors_origins.split(",") if o.strip()]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    host = os.getenv("FALKORDB_HOST", "localhost")
    port = int(os.getenv("FALKORDB_PORT", 6379))
    graph = os.getenv("FALKORDB_GRAPH", "KnowledgeGraph")

    try:
        db_client = FalkorDBClient(host, port, graph)
    except Exception as exc:
        raise RuntimeError(f"Failed to connect to FalkorDB: {exc}") from exc

    @app.get("/health")
    def health() -> dict[str, Any]:
        try:
            db_client.graph.query("RETURN 1")
            return {"ok": True, "graph": graph}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"DB health check failed: {exc}") from exc

    # ==================== Phase-Based Endpoints ====================

    @app.get("/api/situation")
    def situation(title: Optional[str] = Query(default=None)) -> dict[str, Any]:
        """Get SITUATION phase: friendly/enemy disposition, terrain, weather."""
        where_parts = ["s.title IN ['Situation', 'Terrain', 'Weather']"]
        if title:
            where_parts.append(f"toLower(d.title) = '{_escape(title.lower())}'")
        where = "WHERE " + " AND ".join(where_parts)
        
        query = f"""
        MATCH (d:Document)-[:CONTAINS_SECTION]->(s:Section)
        {where}
        RETURN d.title, s.title, s.content
        ORDER BY s.title
        """
        rows = _run_query(db_client, query)
        return {
            "phase": "SITUATION",
            "count": len(rows),
            "items": [{"section": r[1], "content": r[2]} for r in rows],
        }

    @app.get("/api/mission")
    def mission(title: Optional[str] = Query(default=None)) -> dict[str, Any]:
        """Get MISSION phase: task organization, commander's intent."""
        where_parts = ["s.title IN ['Mission', 'Task Organization']"]
        if title:
            where_parts.append(f"toLower(d.title) = '{_escape(title.lower())}'")
        where = "WHERE " + " AND ".join(where_parts)
        
        query = f"""
        MATCH (d:Document)-[:CONTAINS_SECTION]->(s:Section)
        {where}
        RETURN d.title, s.title, s.content
        ORDER BY s.title
        """
        rows = _run_query(db_client, query)
        return {
            "phase": "MISSION",
            "count": len(rows),
            "items": [{"section": r[1], "content": r[2]} for r in rows],
        }

    @app.get("/api/execution")
    def execution(title: Optional[str] = Query(default=None)) -> dict[str, Any]:
        """Get EXECUTION phase: COA, scheme of fires, tasks, timelines."""
        where_parts = ["s.title = 'Concept of Operations'"]
        if title:
            where_parts.append(f"toLower(d.title) = '{_escape(title.lower())}'")
        where = "WHERE " + " AND ".join(where_parts)
        
        query = f"""
        MATCH (d:Document)-[:CONTAINS_SECTION]->(s:Section)
        {where}
        RETURN d.title, s.title, s.content
        """
        rows = _run_query(db_client, query)
        
        # Get key tasks and timelines
        title_val = title or "unknown"
        normalized_title = _escape(title_val.lower())
        
        key_task_rows = _run_query(
            db_client,
            f"""
            MATCH (d:Document)-[:HAS_KEY_TASK]->(kt:KeyTask)
            WHERE toLower(d.title) = '{normalized_title}'
            RETURN kt.content
            """,
        )
        
        timeline_rows = _run_query(
            db_client,
            f"""
            MATCH (d:Document)-[:HAS_TIMELINE]->(tl:Timeline)
            WHERE toLower(d.title) = '{normalized_title}'
            RETURN tl.event
            """,
        )
        
        scheme_fires_rows = _run_query(
            db_client,
            f"""
            MATCH (d:Document)-[:HAS_FIRES]->(f:SchemeOfFires)
            WHERE toLower(d.title) = '{normalized_title}'
            RETURN f.content
            """,
        )
        
        return {
            "phase": "EXECUTION",
            "concept_of_operations": [{"section": r[1], "content": r[2]} for r in rows],
            "scheme_of_fires": scheme_fires_rows[0][0] if scheme_fires_rows else "",
            "key_tasks": [r[0] for r in key_task_rows],
            "timelines": [r[0] for r in timeline_rows],
        }

    @app.get("/api/sustainment")
    def sustainment(title: Optional[str] = Query(default=None)) -> dict[str, Any]:
        """Get SUSTAINMENT phase: logistics, medical support."""
        where_parts = ["s.title = 'Sustainment'"]
        if title:
            where_parts.append(f"toLower(d.title) = '{_escape(title.lower())}'")
        where = "WHERE " + " AND ".join(where_parts)
        
        query = f"""
        MATCH (d:Document)-[:CONTAINS_SECTION]->(s:Section)
        {where}
        RETURN d.title, s.title, s.content
        """
        rows = _run_query(db_client, query)
        return {
            "phase": "SUSTAINMENT",
            "count": len(rows),
            "items": [{"section": r[1], "content": r[2]} for r in rows],
        }

    @app.get("/api/command-and-signal")
    def command_and_signal(title: Optional[str] = Query(default=None)) -> dict[str, Any]:
        """Get COMMAND AND SIGNAL phase: chain of command, communications."""
        where_parts = ["s.title = 'Command and Signal'"]
        if title:
            where_parts.append(f"toLower(d.title) = '{_escape(title.lower())}'")
        where = "WHERE " + " AND ".join(where_parts)
        
        query = f"""
        MATCH (d:Document)-[:CONTAINS_SECTION]->(s:Section)
        {where}
        RETURN d.title, s.title, s.content
        """
        rows = _run_query(db_client, query)
        return {
            "phase": "COMMAND AND SIGNAL",
            "count": len(rows),
            "items": [{"section": r[1], "content": r[2]} for r in rows],
        }

    # ==================== General Information Endpoints ====================

    @app.get("/api/sections")
    def sections(
        title: Optional[str] = Query(default=None),
        header: Optional[str] = Query(default=None),
    ) -> dict[str, Any]:
        """Get all sections of an OPORD, optionally filtered by header."""
        where_parts: list[str] = []
        if title:
            where_parts.append(f"toLower(d.title) = '{_escape(title.lower())}'")
        if header:
            where_parts.append(f"toLower(s.title) CONTAINS '{_escape(header.lower())}'")

        where = ""
        if where_parts:
            where = "WHERE " + " AND ".join(where_parts)

        query = f"""
        MATCH (d:Document)-[:CONTAINS_SECTION]->(s:Section)
        {where}
        RETURN d.title, s.title, s.content
        """
        rows = _run_query(db_client, query)
        return {
            "count": len(rows),
            "items": [{"document": r[0], "section": r[1], "content": r[2]} for r in rows],
        }

    @app.get("/api/actors")
    def actors(actor_type: Optional[str] = Query(default=None)) -> dict[str, Any]:
        """Get all actors, optionally filtered by type."""
        where = ""
        if actor_type:
            where = f"WHERE toLower(t.name) = '{_escape(actor_type.lower())}'"

        query = f"""
        MATCH (a:Actor)-[:HAS_TYPE]->(t:ActorType)
        {where}
        RETURN a.name, t.name
        """
        rows = _run_query(db_client, query)
        return {
            "count": len(rows),
            "items": [{"name": r[0], "type": r[1]} for r in rows],
        }

    @app.get("/api/key-tasks")
    def key_tasks(title: Optional[str] = Query(default=None)) -> dict[str, Any]:
        """Get key tasks from Execution phase."""
        where = _title_where_clause(title)
        
        query = f"""
        MATCH (d:Document)-[:HAS_KEY_TASK]->(kt:KeyTask)
        {where}
        RETURN d.title, kt.content
        """
        rows = _run_query(db_client, query)
        return {
            "count": len(rows),
            "items": [{"document": r[0], "task": r[1]} for r in rows],
        }

    @app.get("/api/timelines")
    def timelines(title: Optional[str] = Query(default=None)) -> dict[str, Any]:
        """Get timelines from Execution phase."""
        where = _title_where_clause(title)
        
        query = f"""
        MATCH (d:Document)-[:HAS_TIMELINE]->(tl:Timeline)
        {where}
        RETURN d.title, tl.event
        """
        rows = _run_query(db_client, query)
        return {
            "count": len(rows),
            "items": [{"document": r[0], "event": r[1]} for r in rows],
        }

    @app.get("/api/concept-of-operations")
    def concept_of_operations(title: Optional[str] = Query(default=None)) -> dict[str, Any]:
        """Get Concept of Operations from Execution phase."""
        where = _title_where_clause(title)
        query = f"""
        MATCH (d:Document)-[:HAS_COA]->(c:ConceptOfOperations)
        {where}
        RETURN d.title, c.content
        """
        rows = _run_query(db_client, query)
        return {
            "count": len(rows),
            "items": [{"document": r[0], "concept_of_operations": r[1]} for r in rows],
        }

    @app.get("/api/scheme-of-fires")
    def scheme_of_fires(title: Optional[str] = Query(default=None)) -> dict[str, Any]:
        """Get Scheme of Fires from Execution phase."""
        where = _title_where_clause(title)
        query = f"""
        MATCH (d:Document)-[:HAS_FIRES]->(f:SchemeOfFires)
        {where}
        RETURN d.title, f.content
        """
        rows = _run_query(db_client, query)
        return {
            "count": len(rows),
            "items": [{"document": r[0], "scheme_of_fires": r[1]} for r in rows],
        }

    @app.get("/api/enemy")
    def enemy(title: Optional[str] = Query(default=None)) -> dict[str, Any]:
        """Get enemy-related information from Situation phase."""
        where_parts: list[str] = ["toLower(s.title) IN ['situation', 'terrain', 'weather']"]
        if title:
            where_parts.append(f"toLower(d.title) = '{_escape(title.lower())}'")
        where = "WHERE " + " AND ".join(where_parts)
        section_query = f"""
        MATCH (d:Document)-[:CONTAINS_SECTION]->(s:Section)
        {where}
        RETURN d.title, s.title, s.content
        """
        rows = _run_query(db_client, section_query)
        return {
            "sections": [
                {"document": r[0], "section": r[1], "content": r[2]} for r in rows
            ],
        }

    # ==================== Complete OPORD Summary ====================

    @app.get("/api/opord-summary")
    def opord_summary(title: str = Query(...)) -> dict[str, Any]:
        """Get complete OPORD summary organized by 5 phases: Situation → Mission → Execution → Sustainment → C2."""
        normalized_title = _escape(title.lower())

        # Phase 1: SITUATION
        situation_rows = _run_query(
            db_client,
            f"""
            MATCH (d:Document)-[:CONTAINS_SECTION]->(s:Section)
            WHERE toLower(d.title) = '{normalized_title}'
              AND s.title IN ['Situation', 'Terrain', 'Weather']
            RETURN s.title, s.content
            ORDER BY s.title
            """,
        )

        # Phase 2: MISSION
        mission_rows = _run_query(
            db_client,
            f"""
            MATCH (d:Document)-[:CONTAINS_SECTION]->(s:Section)
            WHERE toLower(d.title) = '{normalized_title}'
              AND s.title IN ['Mission', 'Task Organization']
            RETURN s.title, s.content
            ORDER BY s.title
            """,
        )

        # Phase 3: EXECUTION
        coa_rows = _run_query(
            db_client,
            f"""
            MATCH (d:Document)-[:CONTAINS_SECTION]->(s:Section)
            WHERE toLower(d.title) = '{normalized_title}'
              AND s.title = 'Concept of Operations'
            RETURN s.content
            """,
        )

        fires_rows = _run_query(
            db_client,
            f"""
            MATCH (d:Document)-[:HAS_FIRES]->(f:SchemeOfFires)
            WHERE toLower(d.title) = '{normalized_title}'
            RETURN f.content
            """,
        )

        key_task_rows = _run_query(
            db_client,
            f"""
            MATCH (d:Document)-[:HAS_KEY_TASK]->(kt:KeyTask)
            WHERE toLower(d.title) = '{normalized_title}'
            RETURN kt.content
            """,
        )

        timeline_rows = _run_query(
            db_client,
            f"""
            MATCH (d:Document)-[:HAS_TIMELINE]->(tl:Timeline)
            WHERE toLower(d.title) = '{normalized_title}'
            RETURN tl.event
            """,
        )

        # Phase 4: SUSTAINMENT
        sustainment_rows = _run_query(
            db_client,
            f"""
            MATCH (d:Document)-[:CONTAINS_SECTION]->(s:Section)
            WHERE toLower(d.title) = '{normalized_title}'
              AND s.title = 'Sustainment'
            RETURN s.content
            """,
        )

        # Phase 5: COMMAND AND SIGNAL
        c2_rows = _run_query(
            db_client,
            f"""
            MATCH (d:Document)-[:CONTAINS_SECTION]->(s:Section)
            WHERE toLower(d.title) = '{normalized_title}'
              AND s.title = 'Command and Signal'
            RETURN s.content
            """,
        )

        # Get actors and relations
        actor_rows = _run_query(
            db_client,
            f"""
            MATCH (d:Document)-[:MENTIONS]->(a:Actor)-[:HAS_TYPE]->(t:ActorType)
            WHERE toLower(d.title) = '{normalized_title}'
            RETURN a.name, t.name
            """,
        )

        relation_rows = _run_query(
            db_client,
            f"""
            MATCH (d:Document)-[:CONTAINS_SECTION]->(s:Section)
            WHERE toLower(d.title) = '{normalized_title}'
              AND toLower(s.title) = 'relations'
            RETURN s.content
            """,
        )

        # Check if we have any data
        all_rows = situation_rows + mission_rows + coa_rows + fires_rows + key_task_rows + timeline_rows + sustainment_rows + c2_rows + actor_rows + relation_rows
        if not all_rows:
            raise HTTPException(status_code=404, detail=f"No OPORD data found for title '{title}'")

        return {
            "title": title,
            "phases": {
                "situation": {
                    "sections": [{"name": r[0], "content": r[1]} for r in situation_rows],
                },
                "mission": {
                    "sections": [{"name": r[0], "content": r[1]} for r in mission_rows],
                },
                "execution": {
                    "concept_of_operations": coa_rows[0][0] if coa_rows else "",
                    "scheme_of_fires": fires_rows[0][0] if fires_rows else "",
                    "key_tasks": [r[0] for r in key_task_rows],
                    "timelines": [r[0] for r in timeline_rows],
                },
                "sustainment": {
                    "content": sustainment_rows[0][0] if sustainment_rows else "",
                },
                "command_and_signal": {
                    "content": c2_rows[0][0] if c2_rows else "",
                },
            },
            "entities": {
                "actors": [{"name": r[0], "type": r[1]} for r in actor_rows],
                "relations": relation_rows[0][0] if relation_rows else "",
            },
        }

    return app


app = create_app()


def run() -> None:
    api_host = os.getenv("API_HOST", "0.0.0.0")
    api_port = int(os.getenv("API_PORT", "8000"))
    uvicorn.run("main_pipeline.api:app", host=api_host, port=api_port, reload=False)


if __name__ == "__main__":
    run()
