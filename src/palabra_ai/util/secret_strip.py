import logging

logger = logging.getLogger(__name__)


def secret_strip(obj, show=2) -> str:
    """
    Returns a secret-stripped version of the given object.

    The function converts the input to a string and if its length is greater than twice the 'show'
    parameter, it returns a string composed of the first 'show' characters, three asterisks, and
    the last 'show' characters (e.g. "ab***cd" when show=2). Otherwise, or if the object is None or a boolean,
    it returns a string of asterisks.

    Parameters:
        obj: Any object to be converted to string.
        show (int): Number of characters to show from the start and the end (default is 2).

    Returns:
        str: The secret-stripped string.
    """
    # If the input is None or a boolean, return its original string representation.
    if obj is None or isinstance(obj, bool):
        logger.debug("Input is None or boolean; returning original value.")
        return str(obj)

    s = str(obj)
    # If the string is not longer than twice the show count, return asterisks.
    if len(s) <= show * 2:
        logger.debug(
            "String length (%d) is not greater than show*2 (%d); returning asterisks.",
            len(s),
            show * 2,
        )
        return "***"

    result = s[:show] + "***" + s[-show:]
    logger.debug("Secret stripped result: %s", result)
    return result
