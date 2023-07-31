import json
import shutil
from datetime import datetime
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

from common import normalize_name, json_default, DATETIME_FORMAT

class Remote(ABC):
    @abstractmethod
    def get_registry(self) -> dict[str, dict[str, Any]]:
        pass

    @abstractmethod
    def register_new_save(self, save_name):
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
    def add_hints(self, save_name, pattern_hint='', root_hint=''):
        pass


class FSRemote(Remote):
    def __init__(self, folder) -> None:
        self.main_folder = Path(folder)
        self.registry_file = Path(folder).joinpath('registry.json')
        self._registry = None

    def get_registry(self) -> dict[str, dict[str, Any]]:
        if self._registry is None:
            if self.registry_file.exists():
                with open(self.registry_file) as fio:
                    self._registry = json.load(fio)
                for save in self._registry.values():
                    save['last_upload'] = datetime.strptime(save['last_upload'], DATETIME_FORMAT)
            else:
                self._registry = {}
        return self._registry
    
    def register_new_save(self, save_name):
        registry = self.get_registry()
        registry[normalize_name(save_name)] = {'name': save_name}
        self._save_registry(registry)
    
    def upload_save(self, save_name, file_to_upload):
        registry = self.get_registry()
        save = registry[save_name]
        remote_path = self.main_folder.joinpath(f"{save_name}.zip")
        shutil.copy(file_to_upload, remote_path)
        save['last_upload'] = datetime.now()
        save['size'] = Path(file_to_upload).stat().st_size
        self._save_registry(registry)

    def load_save(self, save_name, output_file):
        remote_path = self.main_folder.joinpath(f"{save_name}.zip")
        if not remote_path.is_file():
            raise KeyError(f"Save {save_name} is not present in remote.")
        shutil.copy(remote_path, output_file)

    def delete_save(self, save_name):
        registry = self.get_registry()
        del registry[save_name]
        remote_path = self.main_folder.joinpath(f"{save_name}.zip")
        remote_path.unlink()
        self._save_registry(registry)

    def add_hints(self, save_name, pattern_hint='', root_hint=''):
        registry = self.get_registry()
        save = registry[save_name]
        save['pattern_hint'] = pattern_hint
        save['root_hint'] = root_hint
        self._save_registry(registry)

    def _save_registry(self, changed_registry):
        self._registry = changed_registry
        with open(self.registry_file, 'w') as fio:
            return json.dump(changed_registry, fio, default=json_default)

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