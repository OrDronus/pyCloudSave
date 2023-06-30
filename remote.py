import json
import shutil
from datetime import datetime
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

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

FOLDER_MIME_TYPE = 'application/vnd.google-apps.folder'

def parse_rfc3339(_str):
    return datetime.strptime(_str[:_str.find('.')], '%Y-%m-%dT%H:%M:%S')
  
class GDriveRemote(Remote):
    def __init__(self) -> None:
        self.drive = None
        self._registry = None

    def _init_drive(self):
        if self.drive is not None:
            return
        gauth = GoogleAuth()
        gauth.LocalWebserverAuth()
        self.drive = GoogleDrive(gauth)
        self.main_folder_id = self._get_or_create_file(
            f"title = 'pyCloudSave' and mimeType = '{FOLDER_MIME_TYPE}' and 'root' in parents and trashed = false",
            {'title': 'pyCloudSave', 'mimeType': FOLDER_MIME_TYPE}
        )['id']
        self.saves_folder_id = self._get_or_create_file(
            f"title = 'saves' and mimeType = '{FOLDER_MIME_TYPE}' and '{self.main_folder_id}' in parents and trashed = false",
            {'title': 'saves', 'mime_type': FOLDER_MIME_TYPE, 'parents': [{'id': self.main_folder_id}]}
        )['id']

    def get_registry(self) -> dict[str, dict[str, Any]]:
        if self._registry is not None:
            return self._registry
        self._init_drive()
        registry = {}
        hints = self._load_hints()
        files = self.drive.ListFile(
            {'q': f"'{self.saves_folder_id}' in parents and trashed = false"}
        ).GetList()
        for file in files:
            save = {
                'name': file['title'],
                'last_upload': parse_rfc3339(file['modifiedDate']),
                'size': int(file['fileSize'])
            }
            lower_name = file['title'].lower()
            for add_attr in ('root_hint', 'pattern_hint', 'ignore_hint'):
                if add_attr in hints.get(lower_name, {}):
                    save[add_attr] = hints[lower_name][add_attr]
            registry[lower_name] = save
        self._registry = registry
        return registry

    def upload_save(self, save_name, file_to_upload):
        self._init_drive()
        save_file = self._get_or_create_file(
            f"title = '{save_name}' and '{self.saves_folder_id}' in parents and trashed = false",
            {'title': save_name, 'parents': [{'id': self.saves_folder_id}]}
        )
        save_file.SetContentFile(file_to_upload)
        save_file.Upload()

    def load_save(self, save_name, output_file):
        self._init_drive()
        save_file = self._get_file(
            f"title = '{save_name}' and '{self.saves_folder_id}' in parents and trashed = false"
        )
        if save_file is None:
            raise KeyError(f"There is no save with a name {save_name} in remote.")
        save_file.GetContentFile(output_file)

    def delete_save(self, save_name):
        self._init_drive()
        save_file = self._get_file(
            f"title = '{save_name}' and '{self.saves_folder_id}' in parents and trashed = false"
        )
        if save_file is None:
            raise KeyError(f"There is no save with a name {save_name} in remote.")
        save_file.Delete()
        hints = self._load_hints()
        hints.pop(save_name.lower())
        self._save_hints(hints)

    def add_hints(self, save_name, hints: dict[str, str]):
        self._init_drive()
        all_hints = self._load_hints()
        all_hints[save_name.lower()] = hints
        self._save_hints(all_hints)

    def _load_hints(self):
        hints_file = self._get_file(
            f"title = 'hints.json' and '{self.main_folder_id}' in parents and trashed = false"
        )
        if hints_file:
            return json.loads(hints_file.GetContentString())
        else:
            return {}
        
    def _save_hints(self, hints):
        hints_file = self._get_or_create_file(
            f"title = 'hints.json' and '{self.main_folder_id}' in parents and trashed = false",
            {'title': 'hints.json', 'parents': [{'id': self.main_folder_id}]}
        )
        hints_file.SetContentString(json.dumps(hints))
        hints_file.Upload()

    def _get_file(self, query):
        results = self.drive.ListFile({'q': query}).GetList()
        if results:
            return results[0]
        else:
            return None

    def _get_or_create_file(self, query, metadata):
        file = self._get_file(query)
        if file is not None:
            return file
        else:
            new_file = self.drive.CreateFile(metadata)
            new_file.Upload()
            return new_file