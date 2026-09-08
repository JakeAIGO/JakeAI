# JakeAI Flat Deployment Package

All files in this package are located in a SINGLE flat directory (zero subfolders) for easy upload through the GitHub mobile web interface:

- `main.py` — Complete, fully wired JakeAI backend (includes telemetry, robotics solver, and discovery manifests).
- `telemetry.py` — Search Honeypot & unmet queries tracker.
- `robotics.py` — 22-DoF Tendon Grasp & Impedance Solver.
- `mcp_server.py` — FastMCP server for Claude Desktop / Cursor.
- `agent_card.json` — Machine agent discovery manifest.
- `llms.txt` — AI crawler documentation manifest.

### Uploading via GitHub Mobile Web UI:
1. In your GitHub repository, tap **Add file** -> **Upload files**.
2. Tap **Choose your files**.
3. Select the files directly from this folder.
4. Tap **Commit changes**.
