from loguru import logger as loguru_logger
from loguru._logger import Logger
import sys
import os
from pathlib import Path


class KarmaRanksLogger:
    def __init__(self):
        self.logger = loguru_logger
        self.logger.remove()
        self.logger.add(
            sys.stdout,
            level="INFO",
            colorize=True,
            enqueue=True
        )
        self.logger_dir = self._get_logger_dir()
        self.log_file = os.path.join(self.logger_dir, "karma_ranks.log")
        self.logger.add(
            sink=self.log_file,
            level="DEBUG",
            rotation="00:00",  # Rotate at midnight
            retention="3 days",  # Keep logs for 3 days
            colorize=True,
            enqueue=True,  # Thread-safe logging
            backtrace=True,  # Include traceback info
            diagnose=True,   # Include variables in traceback
        )
        
    
    def get_logger(self) -> Logger:
        return self.logger
    
    def _get_logger_dir(self)-> Path:
        base_dir = Path(__file__).parent.parent  # karma_track root directory
        logger_dir = base_dir / "logs"
        os.makedirs(logger_dir, exist_ok=True)
        return logger_dir


def setup_logger() -> Logger:
    # Create a configured logger instance
    logger: Logger = loguru_logger
    # Remove default handlers
    logger.remove()

    # Use absolute path for reliable log location
    base_dir = Path(__file__).parent.parent  # karma_track root directory
    log_dir = base_dir / "logs"
    os.makedirs(log_dir, exist_ok=True)

    time_format = "{time:YYYY-MM-DD HH:mm}"
    log_format = (
        f"{time_format} | {{level}} | {{file}}:{{function}}:{{line}} | {{message}}"
    )

    # Main logger
    logger_name = "karma_log"
    log_file = os.path.join(log_dir, f"{logger_name}.log")

 
    # Main logger for all operations
    logger.add(
        sink=log_file,
        level="DEBUG",
        rotation="00:00",  # Rotate at midnight
        retention="3 days",  # Keep logs for 7 days
        colorize=False,
        enqueue=True,  # Thread-safe logging
        backtrace=True,  # Include traceback info
        diagnose=True,   # Include variables in traceback
        format=log_format,
    )

    # Add stdout handler to journalctl
    logger.add(
        sink=sys.stdout,
        level="DEBUG",
        colorize=True,  
        enqueue=True,
        format=log_format,
    )

    return logger

# Create a single logger instance to be imported by other modules
logger = setup_logger()
