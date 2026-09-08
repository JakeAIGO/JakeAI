# Add these imports and routes to your main.py:
from fastapi.responses import FileResponse
import os
from app.routers import telemetry, robotics

app.include_router(telemetry.router)
app.include_router(robotics.router)

@app.get("/.well-known/agent-card.json")
async def get_agent_card():
    path = os.path.join("static", ".well-known", "agent-card.json")
    return FileResponse(path, media_type="application/json")

@app.get("/llms.txt")
async def get_llms_txt():
    path = os.path.join("static", "llms.txt")
    return FileResponse(path, media_type="text/plain")
