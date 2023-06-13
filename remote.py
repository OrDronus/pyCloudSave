import json
import shutil
from abc import ABC, abstractmethod
from pathlib import Path

class Remote(ABC):
    @abstractmethod
    def create_save(self, name, parameters):
        pass

    @abstractmethod
    def edit_save(self, name, parameters):
        pass

    @abstractmethod
    def delete_save(self, name):
        pass

    @abstractmethod
    def get_saves(self) -> dict:
        pass

    @abstractmethod
    def load_save(self, name, output_folder):
        pass

    @abstractmethod
    def upload_save(self, name, filepath):
        pass

class FSRemote(Remote):
    def __init__(self, folder) -> None:
        self.root = Path(folder)
        self.reg_file = self.root.joinpath('registry.json')

    def _load_reg(self):
        with open(self.reg_file) as fio:
            return json.load(fio)

    def _save_reg(self, reg):
        with open(self.reg_file, 'w') as fio:
            return json.dump(reg, fio)
    
    def create_save(self, name, parameters):
        reg = self._load_reg()
        key = name.lower()
        if key in reg:
            raise ValueError('Remote already has a save with that name')
        reg[key] = dict(parameters)
        reg[key]['name'] = name
        self._save_reg(reg)

    def edit_save(self, name, parameters):
        reg = self._load_reg()
        reg[name].update(parameters)
        self._save_reg(reg)

    def delete_save(self, name):
        reg = self._load_reg()
        del reg[name]
        self._save_reg(reg)

    def get_saves(self) -> dict:
        return self._load_reg()

    def load_save(self, name, output_folder):
        remote_path = self.root.joinpath(f'{name}.zip')
        return shutil.copy(remote_path, output_folder)

    def upload_save(self, name, filepath):
        remote_path = self.root.joinpath(f'{name}.zip')
        shutil.copy(filepath, remote_path)
