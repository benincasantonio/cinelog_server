from app.schemas.error_schema import ErrorSchema


class ErrorCodes:
    # Authentication Errors
    HANDLE_ALREADY_TAKEN = ErrorSchema(
        error_code_name="HANDLE_ALREADY_TAKEN",
        error_code=409,
        error_message="Handle already taken",
        error_description="The handle provided is already in use by another user.",
    )

    EMAIL_ALREADY_EXISTS = ErrorSchema(
        error_code_name="EMAIL_ALREADY_EXISTS",
        error_code=409,
        error_message="Email already exists",
        error_description="The email provided is already in use by another user.",
    )

    ERROR_CREATING_USER = ErrorSchema(
        error_code_name="ERROR_CREATING_USER",
        error_code=500,
        error_message="Error creating user",
        error_description="An error occurred while creating the user.",
    )

    USER_NOT_FOUND = ErrorSchema(
        error_code_name="USER_NOT_FOUND",
        error_code=404,
        error_message="User not found",
        error_description="The requested user was not found.",
    )

    INVALID_CREDENTIALS = ErrorSchema(
        error_code_name="INVALID_CREDENTIALS",
        error_code=401,
        error_message="Invalid credentials",
        error_description="The email or password provided is incorrect.",
    )

    # Movie Errors

    MOVIE_NOT_FOUND = ErrorSchema(
        error_code_name="MOVIE_NOT_FOUND",
        error_code=404,
        error_message="Movie not found",
        error_description="The requested movie was not found.",
    )

    MOVIE_ALREADY_EXISTS = ErrorSchema(
        error_code_name="MOVIE_ALREADY_EXISTS",
        error_code=409,
        error_message="Movie already exists",
        error_description="The movie already exists in the database.",
    )

    # Log Not Found Error
    LOG_NOT_FOUND = ErrorSchema(
        error_code_name="LOG_NOT_FOUND",
        error_code=404,
        error_message="Log not found",
        error_description="The requested log entry was not found.",
    )
