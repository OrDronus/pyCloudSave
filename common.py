import re
from datetime import datetime

DATETIME_FORMAT = "%y-%m-%d %H:%M:%S.%f"

def json_default(obj):
    if isinstance(obj, datetime):
        return datetime.strftime(obj, DATETIME_FORMAT)
    raise TypeError

def normalize_name(name: str) -> str:
    return '_'.join(p.lower() for p in re.split(r"[\W_]+", name) if p)

def normalized_search(_dict: dict, name):
    parts = [p.lower() for p in re.split(r"[\W_]+", name) if p]
    exact_name = "_".join(parts)
    try:
        return [_dict[exact_name]]
    except KeyError:
        pass
    results = []
    regex = r".*".join(parts)
    for key, value in _dict.items():
        if re.search(regex, key):
            results.append(value)
    return results
