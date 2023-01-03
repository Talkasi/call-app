import logging
import os

# NOTE: following must be initialized before using!
# Call `init()` for that.

# IMPORTANT: as other modules are going to use logger,
# it must be initialized _before_ any other module using it.
root_logger = None


def init():
    global root_logger

    level = logging.DEBUG if os.getenv("DEBUG") else logging.INFO
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    formatter = logging.Formatter(
        '%(asctime)s %(levelname)s [%(name)s] %(message)s')

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(stream_handler)
