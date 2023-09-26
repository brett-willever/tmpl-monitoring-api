import time
import logging
from logging.config import dictConfig
from datetime import datetime
from typing import List, Dict, Any, Awaitable, Union, Set
from fastapi import HTTPException

logging_config = {
    "version": 1,
    "disable_existing_loggers": True,
    "formatters": {
        "verbose": {
            "format": "{asctime} {levelname} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "uvicorn": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "sqlalchemy": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        "sqlalchemy.engine.Engine": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        "monitoring_api": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

dictConfig(logging_config)
logger = logging.getLogger("monitoring_api")

__all__ = [
    HTTPException,
    datetime,
    time,
    List,
    Dict,
    Any,
    Awaitable,
    Union,
    Set,
]
