import json
from pathlib import Path


class Localization:
    def __init__(self, language: str = 'zh_CN') -> None:
        self.language = language
        self.texts: dict[str, str] = {}
        self.load(language)

    def load(self, language: str) -> None:
        self.language = language
        self.texts.clear()
        path = Path(__file__).parent / 'locales' / f'{language}.json'
        with path.open(encoding='utf-8') as f:
            self.texts = json.load(f)

    def get(self, key: str, **kwargs: object) -> str:
        text = self.texts.get(key)
        if text is None:
            raise KeyError(f'missing localization key: {key}')
        return text.format(**kwargs)


i18n = Localization()
tr = i18n.get
