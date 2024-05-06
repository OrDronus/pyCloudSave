import json
import shutil
from datetime import datetime
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Union
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
from pydrive.files import GoogleDriveFile

from common import AppError, SaveNotFoundError, MultipleSavesFoundError, normalize_name, json_default, DATETIME_FORMAT, normalized_search

REMOTE_REGISTRY_VERSION = "1.0"

class Remote(ABC):

    @abstractmethod
    def register_new_save(self, name, root_hint=None, filters_hint=None, version=None):
        pass

    @abstractmethod
    def edit_save(self, id_name, new_name=None, root_hint=None, filters_hint=None, version=None):
        pass

    @abstractmethod
    def upload_save(self, id_name, file_to_upload):
        pass

    @abstractmethod
    def load_save(self, id_name, output_file):
        pass

    @abstractmethod
    def delete_save(self, id_name):
        pass

    @abstractmethod
    def get_saves_list(self):
        pass

    @abstractmethod
    def find_save(self, search_name):
        pass
    
    @abstractmethod
    def get_save(self, id_name):
        pass

class RemoteFSError(Exception):
    pass

class FileDoesNotExistError(RemoteFSError):
    pass

class RemoteAccessError(RemoteFSError):
    pass

class RemoteFS(ABC):
    def load_json(self, filename) -> dict[str, Any]:
        pass

    def upload_json(self, filename, data):
        pass

    def load_file(self, filename, target):
        pass

    def upload_file(self, filename, source):
        pass

    def rename_file(self, filename, new_filename):
        pass

    def delete_file(self, filename):
        pass

REGISTRY_FILENAME = "registry.json"
class FilebasedRemote(Remote):
    def __init__(self, fs: RemoteFS):
        self.fs = fs
        self._registry = None
    
    def get_registry(self) -> dict[str, dict[str, Any]]:
        if self._registry is not None:
            return self._registry
        try:
            data = self.fs.load_json(REGISTRY_FILENAME)
            if data['version'] != REMOTE_REGISTRY_VERSION:
                raise ValueError(f"Remote registry version: {data['version']} is not supported.")
            registry = data['saves']
            for id_name, save in registry.items():
                save['last_upload'] = datetime.strptime(save['last_upload'], DATETIME_FORMAT)
                save['id_name'] = id_name
        except FileDoesNotExistError:
            registry = {}
        self._registry = registry
        return registry
    
    def register_new_save(self, name, root_hint=None, filters_hint=None, version=None):
        registry = self.get_registry()
        id_name = normalize_name(name)
        registry[id_name] = {
            'name': name,
            'root_hint': root_hint,
            'filters_hint': filters_hint,
            'version': version,
            'last_upload': None,
            'id_name': id_name
        }
        self._save_registry(registry)

    def edit_save(self, id_name, new_name=None, root_hint=None, filters_hint=None, version=None):
        registry = self.get_registry()
        save = registry[id_name]
        if root_hint:
            save['root_hint'] = root_hint
        if filters_hint:
            save['filters_hint'] = filters_hint
        if version:
            save['version'] = version
        if new_name:
            new_id_name = normalize_name(new_name)
            save['name'] = new_name
            if id_name != new_id_name:
                save['id_name'] = new_id_name
                registry[new_id_name] = save
                del registry[id_name]
                self.fs.rename_file(self._get_filesave_name(id_name), self._get_filesave_name (new_id_name))
        self._save_registry(registry)

    def load_save(self, id_name, output_file):
        try:
            self.fs.load_file(self._get_filesave_name(id_name), output_file)
        except FileDoesNotExistError:
            raise KeyError(f"Save {id_name} is not present in remote.") from None

    def upload_save(self, id_name, file_to_upload, _datetime):
        registry = self.get_registry()
        save = registry[id_name]
        self.fs.upload_file(self._get_filesave_name(id_name), file_to_upload)
        save['last_upload'] = _datetime
        save['size'] = Path(file_to_upload).stat().st_size
        self._save_registry(registry)

    def delete_save(self, id_name):
        registry = self.get_registry()
        del registry[id_name]
        self.fs.delete_file(self._get_filesave_name(id_name))
        self._save_registry(registry)

    def _save_registry(self, changed_registry):
        self._registry = changed_registry
        data = {'version': REMOTE_REGISTRY_VERSION, 'saves': changed_registry}
        self.fs.upload_json(REGISTRY_FILENAME, data)

    def _get_filesave_name(self, id_name):
        return f"{id_name}.zip"

    def get_saves_list(self):
        return list(self.get_registry().values())

    def get_save(self, id_name):
        return self.get_registry().get(id_name)

    def find_save(self, search_name):
        registry = self.get_registry()
        results = normalized_search(registry.keys(), search_name)
        if not results:
            raise SaveNotFoundError(search_name)
        if len(results) > 1:
            raise MultipleSavesFoundError(search_name, [registry[s]['name'] for s in results])
        return registry[results[0]]

class LocalFS(RemoteFS):
    def __init__(self, root_folder):
        self.root_folder = Path(root_folder)
        self.root_folder.mkdir(exist_ok=True)
    
    def load_json(self, filename) -> dict[str, Any]:
        file = self.root_folder.joinpath(filename)
        if not file.is_file():
            raise FileDoesNotExistError()
        with open(file, "r") as fio:
            return json.load(fio)

    def upload_json(self, filename, data):
        with open(self.root_folder.joinpath(filename), "w") as fio:
            return json.dump(data, fio, default=json_default)

    def load_file(self, filename, target):
        file = self.root_folder.joinpath(filename)
        if not file.is_file():
            raise FileDoesNotExistError()
        shutil.copy(file, target)

    def upload_file(self, filename, source):
        shutil.copy(source, self.root_folder.joinpath(filename))

    def rename_file(self, filename, new_filename):
        self.root_folder.joinpath(filename).rename(self.root_folder.joinpath(new_filename))

    def delete_file(self, filename):
        self.root_folder.joinpath(filename).unlink()

FOLDER_MIME_TYPE = 'application/vnd.google-apps.folder'

class GDriveFS(RemoteFS):
    def __init__(self, root_folder, settings_file='settings.yaml') -> None:
        self.root_folder = root_folder
        self.root_folder_id = None
        self.drive = None
        self._registry = None

    def _init_drive(self):
        if self.drive is not None:
            return
        gauth = GoogleAuth()
        gauth.LocalWebserverAuth()
        self.drive = GoogleDrive(gauth)
        self.root_folder_id = self._get_or_create_file({'title': self.root_folder, 'mimeType': FOLDER_MIME_TYPE})['id']

    def load_json(self, filename) -> dict[str, Any]:
        self._init_drive()
        file = self._get_file({'title': filename}, self.root_folder_id)
        return json.loads(file.GetContentString())

    def upload_json(self, filename, data):
        self._init_drive()
        file = self._get_or_create_file({'title': filename}, self.root_folder_id)
        file.SetContentString(json.dumps(data, default=json_default))
        file.Upload()

    def load_file(self, filename, target):
        self._init_drive()
        save_file = self._get_file({'title': filename}, self.root_folder_id)
        save_file.GetContentFile(target)

    def upload_file(self, filename, source):
        self._init_drive()
        save_file = self._get_or_create_file({'title': filename}, self.root_folder_id)
        save_file.SetContentFile(source)
        save_file.Upload()

    def rename_file(self, filename, new_filename):
        file = self._get_file({'title': filename}, self.root_folder_id)
        file['title'] = new_filename
        file.Upload()

    def delete_file(self, filename):
        self._init_drive()
        file = self._get_file({'title': filename}, self.root_folder_id)
        file.Delete()
    
    def _get_file(self, metadata: dict[str, str], parent_id=None) -> GoogleDriveFile:
        clauses = ["trashed = false"]
        for name, value in metadata.items():
            clauses.append(f"{name} = '{value}'")
        if parent_id:
            clauses.append(f"'{parent_id}' in parents")
        else:
            clauses.append("'root' in parents")
        query = " and ".join(clauses)
        results = self.drive.ListFile({'q': query}).GetList()
        if not results:
            raise FileDoesNotExistError()
        return results[0]

    def _get_or_create_file(self, metadata, parent_id=None):
        try:
            return self._get_file(metadata, parent_id)
        except FileDoesNotExistError:
            pass
        if parent_id:
            metadata['parents'] = [{'id': parent_id}]
        new_file = self.drive.CreateFile(metadata)
        new_file.Upload()
        return new_file