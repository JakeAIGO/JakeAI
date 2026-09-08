import time
from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/v1/robotics", tags=["robotics"])

class GraspRequest(BaseModel):
    degrees_of_freedom: int = Field(22, ge=1)
    object_mass_kg: float = Field(..., gt=0.0, description="Object mass in kg")
    object_fragility_index: float = Field(..., ge=0.0, le=1.0, description="0.0 rigid to 1.0 fragile")
    friction_coefficient: float = Field(..., gt=0.0, le=2.0, description="Friction coefficient mu > 0")
    target_acceleration_mps2: float = Field(9.81, ge=0.0)

class GraspResponse(BaseModel):
    status: str
    required_normal_force_newtons: float
    tendon_cable_tensions_newtons: list[float]
    joint_torque_limits_nm: float
    compliance_margin: float
    slip_risk_factor: float
    execution_latency_ms: float

@router.post("/grasp-impedance-solver", response_model=GraspResponse)
async def solve_grasp(req: GraspRequest):
    t0 = time.perf_counter()
    num_fingers = 5
    gravity = 9.81
    total_accel = req.target_acceleration_mps2 + gravity
    
    safety_factor = 1.5 + (req.object_fragility_index * 2.0)
    required_force = (req.object_mass_kg * total_accel) / (req.friction_coefficient * num_fingers)
    required_force *= safety_factor
    
    tendon_tensions = [(required_force / 2.0) * (1.0 + (i * 0.05)) for i in range(num_fingers)]
    torque_limit = required_force * 0.1
    compliance = 1.0 - req.object_fragility_index
    slip_risk = max(0.0, 1.0 - (req.friction_coefficient * 2.0))
    
    latency = round((time.perf_counter() - t0) * 1000.0, 3)
    
    return GraspResponse(
        status="optimized",
        required_normal_force_newtons=round(required_force, 3),
        tendon_cable_tensions_newtons=[round(t, 3) for t in tendon_tensions],
        joint_torque_limits_nm=round(torque_limit, 3),
        compliance_margin=round(compliance, 3),
        slip_risk_factor=round(slip_risk, 3),
        execution_latency_ms=latency
    )
