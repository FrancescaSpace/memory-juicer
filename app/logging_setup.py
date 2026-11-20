import logging
import sys


def setup_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    if getattr(root, "_mj_configured", False):
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s", datefmt="%H:%M:%S"
        )
    )
    root.addHandler(handler)
    root.setLevel(level)
    root._mj_configured = True
    for noisy in ("httpx", "httpcore", "dashscope"):
        logging.getLogger(noisy).setLevel(logging.WARNING)