import logging


def setup_logging(level: int = logging.INFO) -> None:
    """Configure application-wide logging.

    Call once at startup (e.g. in the app lifespan or main entry point)
    to ensure consistent log formatting across all modules.
    """
    logging.basicConfig(level=level)
