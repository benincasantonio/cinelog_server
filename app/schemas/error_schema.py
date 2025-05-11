from pydantic import BaseModel, Field


class ErrorSchema(BaseModel):
    """Schema for error response"""
    error_code_name: str = Field(..., description="Error code name")
    error_code: int = Field(..., description="Error code")
    error_message: str = Field(..., description="Error message")
    error_description: str = Field(..., description="Error description")