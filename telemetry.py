import sqlite3
from fastapi import APIRouter, Request, BackgroundTasks
from pydantic import BaseModel
from datetime import datetime, timezone

router = APIRouter(prefix="/api/v1/products", tags=["telemetry"])

DB_PATH = "telemetry.db"

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS unmet_queries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_text TEXT,
                client_ip TEXT,
                user_agent TEXT,
                timestamp DATETIME,
                matched_count INTEGER
            )
        """)

init_db()

class SearchRequest(BaseModel):
    query: str

def log_unmet_query(query: str, ip: str, ua: str, count: int):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO unmet_queries (query_text, client_ip, user_agent, timestamp, matched_count) VALUES (?, ?, ?, ?, ?)",
            (query, ip, ua, datetime.now(timezone.utc), count)
        )

@router.post("/search")
async def search_products(request: SearchRequest, fastapi_req: Request, background_tasks: BackgroundTasks):
    catalog = ["robotic arm", "tendon sensor", "mcp server", "impedance controller", "grasp solver"]
    query_text = request.query.lower().strip()
    matches = [item for item in catalog if query_text in item]
    match_count = len(matches)
    
    client_ip = fastapi_req.client.host if fastapi_req.client else "unknown"
    user_agent = fastapi_req.headers.get("user-agent", "unknown")
    
    background_tasks.add_task(log_unmet_query, query_text, client_ip, user_agent, match_count)
    
    return {
        "results": matches,
        "count": match_count,
        "status": "success" if match_count > 0 else "no_results_logged"
    }
