from datetime import datetime
from pathlib import Path

start = datetime.now()
path = Path(f'log/{start.strftime("%y-%m-%d %H-%M-%S")}.txt')
path.parent.mkdir(parents=True, exist_ok=True)

def log(text: str, end='\n'):
    with path.open('a', encoding='utf-8') as f:
        f.write(text)
        f.write(end)
