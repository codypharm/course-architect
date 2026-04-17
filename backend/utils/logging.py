import logging

# Severity level colors
_LEVEL_COLORS = {
    logging.DEBUG:    "\033[90m",       # grey
    logging.INFO:     "\033[92m",       # bright green
    logging.WARNING:  "\033[93m",       # bright yellow
    logging.ERROR:    "\033[91m",       # bright red
    logging.CRITICAL: "\033[1;91m",     # bold bright red
}

# Agent name color palette — assigned by hashing the logger name
_NAME_PALETTE = [
    "\033[34m",   # blue          → rag.ingest
    "\033[35m",   # magenta       → agents.preprocessor
    "\033[36m",   # cyan          → agents.validation
    "\033[32m",   # green         → rag.retrieval
    "\033[33m",   # yellow        → rag.store
    "\033[94m",   # bright blue   → graph.*
    "\033[95m",   # bright magenta
    "\033[96m",   # bright cyan
]

_RESET = "\033[0m"
_BOLD  = "\033[1m"


def _name_color(name: str) -> str:
    return _NAME_PALETTE[hash(name) % len(_NAME_PALETTE)]


class _ColorFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        level_color = _LEVEL_COLORS.get(record.levelno, "")
        name_color  = _name_color(record.name)

        level  = f"{level_color}{_BOLD}{record.levelname:<8}{_RESET}"
        name   = f"{name_color}{record.name}{_RESET}"
        msg    = f"{level_color}{record.getMessage()}{_RESET}"

        return f"{level} {name} — {msg}"


_configured: set[str] = set()


def get_logger(name: str) -> logging.Logger:
    """Return a colored logger for the given module name.

    Usage (replace standard logging.getLogger calls):
        from utils.logging import get_logger
        logger = get_logger(__name__)
    """
    logger = logging.getLogger(name)
    if name not in _configured:
        logger.setLevel(logging.DEBUG)
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(_ColorFormatter())
            logger.addHandler(handler)
            logger.propagate = False
        _configured.add(name)
    return logger
