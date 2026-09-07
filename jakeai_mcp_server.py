#!/usr/bin/env python3
"""
JakeAI Model Context Protocol (MCP) Server
Allows autonomous agents in Claude Desktop, Cursor, and LangChain/CrewAI 
to discover and execute JakeAI pre-deployment audits directly via JSON-RPC.
"""

import sys
import json
import urllib.request
import urllib.error

AUDIT_ENDPOINT = "https://www.jakeaiofficial.com/api/v1/tools/multi-model-audit"
READABILITY_ENDPOINT = "https://www.jakeaiofficial.com/api/v1/tools/audit-agent-card"

TOOLS = [
    {
        "name": "jakeai_multi_model_audit",
        "description": "Performs an automated dual-frontier model audit (Claude 3.5 Sonnet for architecture & legal risk + Perplexity Sonar-Pro for market benchmarks). Returns explicit Go/No-Go verdict.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The proposed code diff, API schema, product manifest, or site terms to audit."
                },
                "domain": {
                    "type": "string",
                    "description": "The target domain being updated (e.g. 'jakeaiofficial.com')."
                }
            },
            "required": ["content"]
        }
    },
    {
        "name": "jakeai_readability_audit",
        "description": "Tests any web domain for /llms.txt compliance, MCP tool discoverability, and AI crawler readability score.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": "The domain URL to test (e.g. 'https://www.jakeaiofficial.com')."
                }
            },
            "required": ["domain"]
        }
    }
]

def handle_rpc_request(request):
    req_id = request.get("id")
    method = request.get("method")
    params = request.get("params", {})

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}

    elif method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if tool_name == "jakeai_multi_model_audit":
            content = arguments.get("content", "")
            domain = arguments.get("domain", "jakeaiofficial.com")
            payload = json.dumps({"content": content, "domain": domain}).encode("utf-8")
            req = urllib.request.Request(AUDIT_ENDPOINT, data=payload, headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=45) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "content": [{"type": "text", "text": json.dumps(data, indent=2)}]
                        }
                    }
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32603, "message": str(e)}
                }

        elif tool_name == "jakeai_readability_audit":
            domain = arguments.get("domain", "")
            payload = json.dumps({"domain": domain}).encode("utf-8")
            req = urllib.request.Request(READABILITY_ENDPOINT, data=payload, headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "content": [{"type": "text", "text": json.dumps(data, indent=2)}]
                        }
                    }
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32603, "message": str(e)}
                }

    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": "Method not found"}}

def main():
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            req = json.loads(line)
            res = handle_rpc_request(req)
            sys.stdout.write(json.dumps(res) + "\n")
            sys.stdout.flush()
        except Exception as e:
            sys.stderr.write(f"RPC Error: {str(e)}\n")

if __name__ == "__main__":
    main()
