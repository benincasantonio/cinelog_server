from app.schemas.error_schema import ErrorSchema


class ErrorCodes:

    INVALID_EMAIL_OR_PASSWORD = ErrorSchema(
        error_code_name="INVALID_EMAIL_OR_PASSWORD",
        error_code=401,
        error_message="Invalid email or password",
        error_description="The email or password provided is incorrect."
    )

    HANDLE_ALREADY_TAKEN = ErrorSchema(
        error_code_name="HANDLE_ALREADY_TAKEN",
        error_code=409,
        error_message="Handle already taken",
        error_description="The handle provided is already in use by another user."
    )

    ERROR_CREATING_USER = ErrorSchema(
        error_code_name="ERROR_CREATING_USER",
        error_code=500,
        error_message="Error creating user",
        error_description="An error occurred while creating the user."
    )