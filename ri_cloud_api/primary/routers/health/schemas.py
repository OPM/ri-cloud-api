from pydantic import BaseModel

class HealthCheckResponse(BaseModel):
    """Response model for health check endpoint"""
    status: str = "alive"
   