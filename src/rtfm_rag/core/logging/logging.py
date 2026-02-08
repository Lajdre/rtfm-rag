import pathlib
import json
import logging.config
import atexit

logger = logging.getLogger("__name__")


def setup_logging():
  config_file = pathlib.Path("./logging_config.json")
  with open(config_file) as f:
    config = json.load(f)

  logging.config.dictConfig(config)
  queue_handler = logging.getHandlerByName("queue_handler")
  if queue_handler is not None:
    queue_handler.listener.start()
    atexit.register(queue_handler.listener.stop)
