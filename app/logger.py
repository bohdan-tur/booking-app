import logging.config
import os
from app.core.logging_config import LOGGING_CONFIG


os.makedirs("logs", exist_ok=True)


logging.config.dictConfig(LOGGING_CONFIG)


logger = logging.getLogger("app")