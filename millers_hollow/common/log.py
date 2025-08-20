from datetime import datetime

start = datetime.now()


def log(text: str, end='\n'):
    with open(
        f'log/{start.strftime("%y-%m-%d %H:%M:%S")}.txt', 'a', encoding='utf-8'
    ) as f:
        f.write(text)
        f.write(end)
