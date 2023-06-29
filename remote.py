import json
import shutil
from datetime import datetime
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

class Remote(ABC):
    @abstractmethod
    def get_registry(self) -> dict[str, dict[str, Any]]:
        pass

    @abstractmethod
    def upload_save(self, save_name, file_to_upload):
        pass

    @abstractmethod
    def load_save(self, save_name, output_file):
        pass

    @abstractmethod
    def delete_save(self, save_name):
        pass

    @abstractmethod
    def add_hints(self, save_name, hints: dict[str, str]):
        pass


class FSRemote(Remote):
    def __init__(self, folder) -> None:
        self.saves_folder = Path(folder).joinpath('saves')
        self.saves_folder.mkdir(exist_ok=True, parents=True)
        self.hints_file = Path(folder).joinpath('hints.json')

    def _get_existing_saves(self):
        return {file.name.lower(): file for file in self.saves_folder.iterdir() if file.is_file()}

    def get_registry(self) -> dict[str, dict[str, Any]]:
        saves = {}
        hints = self._load_hints()
        for lower_name, file in self._get_existing_saves().items():
            stat = file.stat()
            save = {
                'name': file.name,
                'last_upload': datetime.fromtimestamp(stat.st_mtime),
                'size': stat.st_size
            }
            for add_attr in ('root_hint', 'pattern_hint', 'ignore_hint'):
                if add_attr in hints.get(lower_name, {}):
                    save[add_attr] = hints[lower_name][add_attr]
            saves[lower_name] = save
        return saves
    
    def upload_save(self, save_name, file_to_upload):
        existing_save = self._get_existing_saves().get(save_name.lower())
        remote_path = existing_save or self.saves_folder.joinpath(save_name)
        shutil.copy(file_to_upload, remote_path)

    def load_save(self, save_name, output_file):
        existing_save = self._get_existing_saves()[save_name.lower()]
        shutil.copy(existing_save, output_file)

    def delete_save(self, save_name):
        lower_name = save_name.lower()
        existing_save = self._get_existing_saves()[lower_name]
        existing_save.unlink()
        hints = self._load_hints()
        hints.pop(lower_name)
        self._save_hints(hints)

    def add_hints(self, save_name, hints: dict[str, str]):
        all_hints = self._load_hints()
        all_hints[save_name.lower()] = hints
        self._save_hints(all_hints)

    def _load_hints(self):
        if not self.hints_file.exists():
            return {}
        with open(self.hints_file, 'r') as fio:
            return json.load(fio)
        
    def _save_hints(self, hints):
        with open(self.hints_file, 'w') as fio:
            return json.dump(hints, fio)