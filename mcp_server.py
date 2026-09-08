import os
import requests
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("JakeAI-Robotics")
BASE_URL = os.getenv("JAKEAI_BASE_URL", "https://jakeaiofficial.com")

@mcp.tool()
def calculate_grasp(mass_kg: float, fragility: float, friction: float) -> str:
    """Calculates robotic grasp impedance and tendon tensions for a 22-DoF hand."""
    url = f"{BASE_URL}/v1/robotics/grasp-impedance-solver"
    payload = {
        "degrees_of_freedom": 22,
        "object_mass_kg": mass_kg,
        "object_fragility_index": fragility,
        "friction_coefficient": friction,
        "target_acceleration_mps2": 9.81
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        return f"Error calling JakeAI solver: {str(e)}"

if __name__ == "__main__":
    mcp.run()
