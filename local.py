import json
from pathlib import Path
from itertools import chain
from datetime import datetime
from collections.abc import Iterator
from zipfile import ZipFile

class Local:
    def __init__(self, registry_file=None) -> None:
        if registry_file is None:
            registry_file = Path(__file__).parent.joinpath("registry.json")
        self.registry_file = registry_file
        self.registry = self._load_registry()
    
    def _load_registry(self):
        if not self.registry_file.exists():
            return {}
        with open(self.registry_file) as fio:
            return json.load(fio)
    
    def _save_registry(self):
        with open(self.registry_file, 'w') as fio:
            json.dump(self.registry, fio)
    
    def get_saves_list(self):
        return [dict(save) for save in self.registry.values()]

    def get_save(self, save_name):
        return dict(self.registry[save_name])

    def add(self, name, root_folder, file_patterns=None):
        key = name.lower()
        if key in self.registry:
            raise KeyError(f"There is already a seve with the name {key}")
        self.registry[key] = {
            'name': name,
            'root': root_folder,
            'patterns': file_patterns or "**/*",
            'last_sync': ''
        }
        self._save_registry()

    def edit(self, name, parameters):
        self.registry[name].update(parameters)
        new_name = parameters.get('name', name).lower()
        if new_name != name:
            self.registry[new_name] = self.registry[name]
            del self.registry[name]
        self._save_registry()

    def untrack(self, name):
        del self.registry[name]
        self._save_registry()
    
    def get_last_mod_time(self, name):
        latest_ts = 0
        for file in self._get_save_files(name):
            mtime_ts = file.stat().st_mtime
            if mtime_ts > latest_ts:
                latest_ts = mtime_ts
        return datetime.fromtimestamp(latest_ts).strftime('%y-%m-%d %H:%M:%S')

    def _get_save_files(self, name) -> Iterator[Path]:
        save = self.registry[name]
        patterns = save['patterns'].split(',')
        root = Path(save['root'])
        return chain(*(filter(Path.is_file, root.glob(pattern)) for pattern in patterns))

    def pack_save_files(self, save_name, filepath):
        root = self.get_save(save_name)['root']
        with ZipFile(filepath, 'w') as zf:
            for file in self._get_save_files(save_name):
                zf.write(file, file.relative_to(root))

    def unpack_save_files(self, save_name, filepath):
        root = self.get_save(save_name)['root']
        with ZipFile(filepath, 'r') as zf:
            zf.extractall(root)

    def stamp_synced(self, save_name):
        self.registry[save_name]['last_sync'] = datetime.now().strftime('%y-%m-%d %H:%M:%S')
        self._save_registry()
