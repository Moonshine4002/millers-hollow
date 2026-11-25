import logging
from datetime import datetime
from pathlib import Path


class Logger:
    def __init__(self) -> None:
        self.logger = logging.getLogger('millers_hollow')  # temp
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False
        self.formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] %(message)s',
            datefmt='%H:%M:%S',
        )
        self.handler: logging.FileHandler | None = None
        self.restart()

    def restart(self) -> None:
        self.close()
        self.start = datetime.now().astimezone()
        self.path = Path(f'log/{self.start:%y-%m-%d_%H-%M-%S}.log')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handler = logging.FileHandler(self.path, encoding='utf-8', delay=True)
        self.handler.setFormatter(self.formatter)
        self.logger.addHandler(self.handler)

    def close(self) -> None:
        if self.handler is not None:
            self.logger.removeHandler(self.handler)
            self.handler.close()
            self.handler = None
