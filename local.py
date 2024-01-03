import json
import re
import os.path
from pathlib import Path
from itertools import chain
from datetime import datetime
from collections.abc import Iterator
from zipfile import ZipFile

from common import DATETIME_FORMAT, AppError, json_default, normalize_name, normalized_search

LOCAL_REGISTRY_VERSION = "1.0"

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
            data = json.load(fio)
        if data['version'] != LOCAL_REGISTRY_VERSION:
            raise ValueError(f"Local registry version: {data['version']} is not supported.")
        registry = data['saves']
        for id_name, save in registry.items():
            if save['last_sync']:
                save['last_sync'] = datetime.strptime(save['last_sync'], DATETIME_FORMAT)
            save['last_modification'] = self._get_last_mod_time(save)
            save['id_name'] = id_name
        self._registry = registry

    def _save_registry(self):
        data = {'version': LOCAL_REGISTRY_VERSION}
        registry = {}
        for id_name, save in self._registry.items():
            save_data = {k: v for k, v in save.items() if k in ('name', 'root', 'filters', 'version')}
            save_data['last_sync'] = datetime.strftime(save['last_sync'], DATETIME_FORMAT) if save['last_sync'] else None
            registry[id_name] = save_data
        data['saves'] = registry
        with open(self.registry_file, 'w') as fio:
            json.dump(data, fio, indent=4, default=json_default)

    def get_registry(self):
        return self._registry

    def track(self, name, root, filters=None, version=None):
        id_name = normalize_name(name)
        if id_name in self._registry:
            raise KeyError(f"Save with the name {name} is already tracked.")
        save = {
            'name': name,
            'root': root,
            'filters': filters or "",
            'version': version,
            'last_sync': None,
            'id_name': id_name
        }
        save['last_modification'] = self._get_last_mod_time(save)
        self._registry[id_name] = save
        self._save_registry()

    def edit(self, save_name, new_name=None, root=None, filters=None, version=None, last_sync=None):
        save = self._registry[save_name]
        if root:
            save['root'] = root
        if filters:
            save['filters'] = filters
        if version:
            save['version'] = version
        if last_sync:
            save['last_sync'] = last_sync
        if new_name:
            save['name'] = new_name
            new_id_name = normalize_name(new_name)
            if new_id_name != save_name:
                save['id_name'] = new_id_name
                self._registry[new_id_name] = save
                del self._registry[save_name]
        self._save_registry()

    def untrack(self, name):
        del self._registry[name]
        self._save_registry()

    def get_saves_list(self):
        return list(self._registry.values())
    
    def get_save(self, id_name):
        return self._registry.get(id_name)
    
    def find_save(self, search_name):
        results = normalized_search(self._registry.keys(), search_name)
        if not results:
            raise AppError(f"No local saves matching {search_name}.")
        if len(results) > 1:
            raise AppError(f"More than one local save matches {search_name}: {', '.join(self._registry[s]['name'] for s in results)}.")
        return self._registry[results[0]]

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
            neg = False
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
