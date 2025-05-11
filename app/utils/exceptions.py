from app.schemas.error_schema import ErrorSchema

class AppException(Exception):
    """Base exception for application errors"""
    def __init__(self, error: ErrorSchema):
        self.error = error
        super().__init__(error.error_message)
    def __str__(self):
        return {self.error.error_code_name}
