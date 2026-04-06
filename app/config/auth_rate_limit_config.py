from limits import parse

LOGIN_ACCOUNT_RATE_LIMIT_SCOPE = "auth:login:account"
FORGOT_PASSWORD_ACCOUNT_RATE_LIMIT_SCOPE = (  # nosec B105
    "auth:forgot-password:account"
)
RESET_PASSWORD_ACCOUNT_RATE_LIMIT_SCOPE = (  # nosec B105
    "auth:reset-password:account"
)

LOGIN_FAILED_ACCOUNT_LIMIT_ITEM = parse("5/15minute")
FORGOT_PASSWORD_ACCOUNT_LIMIT_ITEM = parse("5/30minute")
RESET_PASSWORD_ACCOUNT_LIMIT_ITEM = parse("10/hour")
