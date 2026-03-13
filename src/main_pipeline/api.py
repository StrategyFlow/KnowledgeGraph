import os
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
    app = FastAPI(title="KnowledgeGraph API", version="0.1.0")

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

    @app.get("/api/commanders-guidance")
    def commanders_guidance(title: Optional[str] = Query(default=None)) -> dict[str, Any]:
        where = _title_where_clause(title)
        query = f"""
        MATCH (d:Document)-[:HAS_GUIDANCE]->(ci:CommandersIntent)
        {where}
        RETURN d.title, ci.content
        """
        rows = _run_query(db_client, query)
        return {
            "count": len(rows),
            "items": [{"document": r[0], "guidance": r[1]} for r in rows],
        }

    @app.get("/api/enemy")
    def enemy(title: Optional[str] = Query(default=None)) -> dict[str, Any]:
        where_parts: list[str] = ["toLower(s.title) CONTAINS 'enemy'"]
        if title:
            where_parts.append(f"toLower(d.title) = '{_escape(title.lower())}'")
        where = "WHERE " + " AND ".join(where_parts)
        section_query = f"""
        MATCH (d:Document)-[:CONTAINS_SECTION]->(s:Section)
        {where}
        RETURN d.title, s.title, s.content
        """
        actor_query = f"""
        MATCH (a:Actor)-[:HAS_TYPE]->(t:ActorType)
        WHERE toLower(t.name) CONTAINS 'enemy'
        RETURN a.name, t.name
        """
        section_rows = _run_query(db_client, section_query)
        actor_rows = _run_query(db_client, actor_query)
        return {
            "sections": [
                {"document": r[0], "section": r[1], "content": r[2]} for r in section_rows
            ],
            "enemy_actors": [{"name": r[0], "type": r[1]} for r in actor_rows],
        }

    @app.get("/api/key-tasks")
    def key_tasks(title: Optional[str] = Query(default=None)) -> dict[str, Any]:
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

    @app.get("/api/sections")
    def sections(
        title: Optional[str] = Query(default=None),
        header: Optional[str] = Query(default=None),
    ) -> dict[str, Any]:
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

    @app.get("/api/opord-summary")
    def opord_summary(title: str = Query(...)) -> dict[str, Any]:
        normalized_title = _escape(title.lower())

        guidance_rows = _run_query(
            db_client,
            f"""
            MATCH (d:Document)-[:HAS_GUIDANCE]->(ci:CommandersIntent)
            WHERE toLower(d.title) = '{normalized_title}'
            RETURN ci.content
            """,
        )

        coa_rows = _run_query(
            db_client,
            f"""
            MATCH (d:Document)-[:HAS_COA]->(c:ConceptOfOperations)
            WHERE toLower(d.title) = '{normalized_title}'
            RETURN c.content
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

        section_rows = _run_query(
            db_client,
            f"""
            MATCH (d:Document)-[:CONTAINS_SECTION]->(s:Section)
            WHERE toLower(d.title) = '{normalized_title}'
            RETURN s.title, s.content
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

        enemy_rows = _run_query(
            db_client,
            f"""
            MATCH (d:Document)-[:CONTAINS_SECTION]->(s:Section)
            WHERE toLower(d.title) = '{normalized_title}'
              AND toLower(s.title) CONTAINS 'enemy'
            RETURN s.content
            """,
        )

        actor_rows = _run_query(
            db_client,
            f"""
            MATCH (d:Document)-[:MENTIONS]->(a:Actor)-[:HAS_TYPE]->(t:ActorType)
            WHERE toLower(d.title) = '{normalized_title}'
            RETURN a.name, t.name
            """,
        )

        if not (guidance_rows or section_rows or key_task_rows or timeline_rows or actor_rows):
            raise HTTPException(status_code=404, detail=f"No OPORD data found for title '{title}'")

        return {
            "title": title,
            "commanders_guidance": guidance_rows[0][0] if guidance_rows else "",
            "concept_of_operations": coa_rows[0][0] if coa_rows else "",
            "scheme_of_fires": fires_rows[0][0] if fires_rows else "",
            "enemy": enemy_rows[0][0] if enemy_rows else "",
            "key_tasks": [r[0] for r in key_task_rows],
            "timelines": [r[0] for r in timeline_rows],
            "sections": [{"section": r[0], "content": r[1]} for r in section_rows],
            "actors": [{"name": r[0], "type": r[1]} for r in actor_rows],
        }

    @app.get("/api/actors")
    def actors(actor_type: Optional[str] = Query(default=None)) -> dict[str, Any]:
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

    return app


app = create_app()


def run() -> None:
    api_host = os.getenv("API_HOST", "0.0.0.0")
    api_port = int(os.getenv("API_PORT", "8000"))
    uvicorn.run("main_pipeline.api:app", host=api_host, port=api_port, reload=False)
