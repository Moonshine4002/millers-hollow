import logging
from datetime import datetime
from pathlib import Path


def setup() -> logging.Logger:
    start = datetime.now().astimezone()
    path = Path(f'log/{start:%y-%m-%d_%H-%M-%S}.log')
    path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger('millers_hollow')
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S',
    )
    file_handler = logging.FileHandler(path, encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger


logger = setup()
