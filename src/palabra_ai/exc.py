class PalabraException(Exception):
    pass


class ConfigurationError(PalabraException):
    """Raised when there is a configuration error."""

    pass


class InvalidCredentialsError(PalabraException):  # TODO
    """Raised when credentials are invalid or missing."""

    pass


class NotSufficientFundsError(PalabraException):  # TODO
    """Raised when there are not enough funds to perform an operation."""

    pass
