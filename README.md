# JakeAI Production Deployment Package

## Folder Structure
- app/routers/telemetry.py -> Search Honeypot & unmet queries tracker
- app/routers/robotics.py  -> 22-DoF Tendon Grasp Solver
- static/.well-known/agent-card.json -> Agent discovery manifest
- static/llms.txt -> Crawler discovery manifest
- mcp/server.py -> FastMCP distribution server
- main_patch.py -> Snippet to register routes in your main.py

## How to Deploy to GitHub & Railway
1. Extract these files into your local repository root.
2. In your terminal run:
   git add .
   git commit -m "feat: add search honeypot, grasp solver, and mcp manifests"
   git push origin main
3. Railway will automatically detect the commit and redeploy jakeaiofficial.com.
