import atexit
import json
import logging.config
import pathlib
from logging.handlers import QueueHandler, QueueListener
from typing import cast

logger = logging.getLogger("__name__")


def setup_logging():
  config_file = pathlib.Path("./logging_config.json")
  with open(config_file) as f:
    config = json.load(f)
  logging.config.dictConfig(config)

  queue_handler = logging.getHandlerByName("queue_handler")

  if isinstance(queue_handler, QueueHandler):
    listener = cast(QueueListener | None, getattr(queue_handler, "listener", None))
    if listener is not None:
      listener.start()
      atexit.register(listener.stop)
