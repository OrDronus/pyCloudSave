import json
import re
from pathlib import Path
from itertools import chain
from datetime import datetime
from collections.abc import Iterator
from zipfile import ZipFile

DATETIME_FORMAT = "%y-%m-%d %H:%M:%S.%f"

class Local:
    def __init__(self, registry_file=None) -> None:
        if registry_file is None:
            registry_file = Path(__file__).parent.joinpath("registry.json")
        self.registry_file = registry_file
        self._load_registry()
    
    def _load_registry(self):
        if not self.registry_file.exists():
            self.registry = {}
        with open(self.registry_file) as fio:
            self.registry = load_block_file(fio)
        for save in self.registry.values():
            save['last_modification'] = self._get_last_mod_time(save) 
    
    def _save_registry(self):
        with open(self.registry_file, 'w') as fio:
            save_block_file(fio, self.registry)

    def track(self, name, root, patterns='', ignore=''):
        lower_name = name.lower()
        if lower_name in self.registry:
            raise KeyError(f"Save with the name {name} is already tracked.")
        save = {
            'name': name,
            'root': root,
        }
        if patterns:
            save['patterns'] = patterns
        if ignore:
            save['ignore'] = ignore
        self.registry[lower_name] = save
        self._save_registry()

    def edit(self, save_name, parameters):
        self.registry[save_name].update(parameters)
        new_name = parameters.get('name', save_name).lower()
        if new_name != save_name:
            self.registry[new_name] = self.registry[save_name]
            del self.registry[save_name]
        self._save_registry()

    def untrack(self, name):
        del self.registry[name]
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
        patterns = save.get('patterns', '**/*').split(',')
        ignore_regexes = [
            '.*'.join(re.escape(sp) for sp in p.split('*'))
            for p in save.get('ignore', '').split(',')
        ]
        root = Path(save['root'])
        for file in chain(*(root.glob(pattern) for pattern in patterns)):
            if (file.is_file() and
                not any(re.search(str(file.relative_to(root)), r) for r in ignore_regexes)):
                yield file

    def pack_save_files(self, save_name, output_file):
        save = self.registry[save_name]
        with ZipFile(output_file, 'w') as zf:
            for file in self._get_save_files(save):
                zf.write(file, file.relative_to(save['root']))

    def unpack_save_files(self, save_name, filepath):
        save = self.registry[save_name]
        with ZipFile(filepath, 'r') as zf:
            zf.extractall(save['root'])

def load_block_file(fio):
    all_saves = {}
    current_save = None
    for line in fio:
        line = line.strip()

        # Comment or blank
        if line.startswith('#') or not line:
            continue

        # Start Block
        match = re.match(r"\[(.+)\]", line)
        if match:
            name = match.group(1).strip()
            current_save = {'name': name}
            all_saves[name.lower()] = current_save
            continue

        # Block Field
        match = re.match(r"(.+?)\s*\:\s*(.+)", line)
        if match:
            if current_save is None:
                raise ValueError("Incorrect file format. Trying to add fields without a block.")
            attr_name = '_'.join(match.group(1).lower().split())
            value = match.group(2)
            if attr_name == 'last_sync':
                current_save[attr_name] = datetime.strptime(value, DATETIME_FORMAT)
            else:
                current_save[attr_name] = value
            continue

        # Error
        raise ValueError(f"Incorrect fromat: {line}")
    return all_saves

def save_block_file(fio, saves):
    for save in saves.values():
        fio.write(f"[{save['name']}]\n")
        for attr_name, value in save.items():
            if attr_name in ('name', 'last_modification'):
                continue
            if attr_name == 'last_sync':
                value = datetime.strftime(value, DATETIME_FORMAT)
            fio.write(f"{attr_name.replace('_', ' ').title()}: {value}\n")
        fio.write("\n")