import json
import re
import os.path
from pathlib import Path
from itertools import chain
from datetime import datetime
from collections.abc import Iterator
from zipfile import ZipFile

from common import DATETIME_FORMAT, json_default, normalize_name

class Local:
    def __init__(self, registry_file=None) -> None:
        if registry_file is None:
            registry_file = Path(__file__).parent.joinpath("registry.json")
        self.registry_file = registry_file
        self._load_registry()
    
    def _load_registry(self):
        if not self.registry_file.exists():
            self._registry = {}
            return
        with open(self.registry_file) as fio:
            self._registry = json.load(fio)
        for save in self._registry.values():
            if 'last_sync' in save:
                save['last_sync'] = datetime.strptime(save['last_sync'], DATETIME_FORMAT)
            save['last_modification'] = self._get_last_mod_time(save) 
    
    def _save_registry(self):
        with open(self.registry_file, 'w') as fio:
            json.dump(self._registry, fio, indent=4, default=json_default)

    def get_registry(self):
        return self._registry

    def track(self, name, root, filters=None, version=None, ):
        normalized_name = normalize_name(name)
        if normalized_name in self._registry:
            raise KeyError(f"Save with the name {name} is already tracked.")
        save = {
            'name': name,
            'root': root,
            'filters': filters or "",
            'version': version
        }
        save['last_modification'] = self._get_last_mod_time(save)
        self._registry[normalized_name] = save
        self._save_registry()

    def edit(self, save_name, parameters):
        self._registry[save_name].update(parameters)
        new_name = parameters.get('name', save_name).lower()
        if new_name != save_name:
            self._registry[new_name] = self._registry[save_name]
            del self._registry[save_name]
        self._save_registry()

    def untrack(self, name):
        del self._registry[name]
        self._save_registry()

    def _get_last_mod_time(self, save):
        latest_ts = 0
        for file in self._get_save_files(save):
            mtime_ts = file.stat().st_mtime
            if mtime_ts > latest_ts:
                latest_ts = mtime_ts
        if latest_ts == 0:
            return None
        return datetime.fromtimestamp(latest_ts)

    def _get_save_files(self, save):
        include = []
        ignore = []
        for _filter in (f for f in re.split(r"\s*\,\s*", save['filters']) if f):
            if _filter.startswith('!'):
                _filter = _filter[1:]
                neg = True
            _filter = os.path.join(*re.split(r"\\|/", _filter))
            _filter = ".*?".join(re.escape(s) for s in _filter.split('*'))
            if neg:
                ignore.append(_filter)
            else:
                include.append(_filter)
        root = Path(save['root'])
        for file in root.glob('**/*'):
            if not file.is_file():
                continue
            relative_name = str(file.relative_to(root))
            if not all(re.fullmatch(f, relative_name) for f in include):
                continue
            if any(re.fullmatch(f, relative_name) for f in ignore):
                continue
            yield file

    def pack_save_files(self, save_name, output_file):
        save = self._registry[save_name]
        with ZipFile(output_file, 'w') as zf:
            for file in self._get_save_files(save):
                zf.write(file, file.relative_to(save['root']))

    def unpack_save_files(self, save_name, filepath):
        save = self._registry[save_name]
        with ZipFile(filepath, 'r') as zf:
            zf.extractall(save['root'])
