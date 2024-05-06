import re
from datetime import datetime

DATETIME_FORMAT = "%y-%m-%d %H:%M:%S.%f"

def json_default(obj):
    if isinstance(obj, datetime):
        return datetime.strftime(obj, DATETIME_FORMAT)
    raise TypeError

def normalized_split(name: str) -> str:
    for part in re.split(r"[\s_]+", name):
        if part == "&":
            part = "and"
        part = re.sub(r"\W", "", part.lower())
        if part:
            yield part

def normalize_name(name: str) -> str:
    return '_'.join(normalized_split(name))

def normalized_search(keys, name):
    parts = list(normalized_split(name))
    exact_name = "_".join(parts)
    if exact_name in keys:
        return [exact_name]
    results = []
    regex = r".*?".join(parts)
    for key in keys:
        if re.search(regex, key):
            results.append(key)
    return results

class AppError(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:
        return self.message

class SaveNotFoundError(AppError):
    def __init__(self, search_name):
        self.search_name = search_name
        super().__init__(f"No saves matching {self.search_name}.")

class MultipleSavesFoundError(AppError):
    def __init__(self, search_name, save_names):
        self.search_name = search_name
        self.save_names = save_names
        super().__init__(f"More than one save matches {self.search_name}: {self.save_names[0]}, {self.save_names[1]}{'.' if len(self.save_names) == 2 else '...'}")
