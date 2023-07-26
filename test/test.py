import sys
import shutil
from pathlib import Path
from io import StringIO
from typing import Any
from unittest.mock import patch

from pyCloudSave import Application
from remote import FSRemote

SAVE_NAME = "Pascal's Wager"
LOOKUP_NAME = "pascal's wager"
SAVE_STRUCTURE = {
    "data": {
        "settings.cfg": "Some settings",
        "keybinds.cfg": "Keybinds"
    },
    "save1.dat": "Save data 1",
    "save2.dat": "Save data 2"
}

class TestSuite():
    def test(self):
        self.set_up()
        err = None
        with patch("pyCloudSave.input", self.input_mock):
            try:
                self.perform_test()
            except Exception as e:
                err = e
        self.clean_up()
        if err is not None:
            raise err

    def set_up(self):
        self.temp_folder = Path(__file__).parent.joinpath("temp")
        self.temp_folder.mkdir(exist_ok=True)
        self.save_folder = self.temp_folder.joinpath(SAVE_NAME)
        self.save_folder.mkdir()
        create_file_structure(self.save_folder, SAVE_STRUCTURE)
        self.remote_folder = self.temp_folder.joinpath("remote")
        self.remote_folder.mkdir()
        self.local_registry = self.temp_folder.joinpath("registry.json")
        self.input_mock = InputMock()

    def invoke_command(self, command, inputs=None):
        remote = FSRemote(self.remote_folder)
        app = Application(remote, self.local_registry)
        print(f"> {command}")
        if inputs:
            self.input_mock.add_inputs(inputs)
        app.parse_args(command.split())

    def print_file_tree(self):
        print("File Tree:")
        print_ftree(self.temp_folder)

    def perform_test(self):
        # Empty List
        self.invoke_command("list")
        self.invoke_command("remote list")
        print()

        # Track save
        self.input_mock.add_inputs([SAVE_NAME, str(self.save_folder)])
        self.invoke_command("track")
        self.invoke_command("list")
        print()

        # Upload with sync
        self.invoke_command(f"sync {LOOKUP_NAME}")
        self.invoke_command("list")
        self.print_file_tree()
        print()

        # Delete local save files
        print("Deleting local files")
        clean_folder(self.save_folder)
        self.print_file_tree()
        print()

        # Load back
        self.invoke_command("sync all")
        self.print_file_tree()
        print()

        # Untrack local
        self.invoke_command(f"untrack {SAVE_NAME}")
        self.invoke_command("list")
        self.invoke_command("remote list")
        print()

        # Delete remote
        self.invoke_command(f"remote delete {LOOKUP_NAME}")
        self.invoke_command("remote list")

    def clean_up(self):
        shutil.rmtree(self.temp_folder)

class InputMock():
    def __init__(self):
        self.queue = []

    def add_inputs(self, inputs):
        self.queue = list(reversed(inputs)) + self.queue
    
    def __call__(self, prompt='') -> Any:
        if not self.queue:
            value = ''
        else:
            value = self.queue.pop()
        print(f"{prompt}{value}")
        return value

def print_ftree(folder_path, indent=0):
    p = Path(folder_path)
    for file in p.iterdir():
        print(" "*indent, file.name, sep="")
        if file.is_dir():
            print_ftree(file, indent+2)

def create_file_structure(folder, structure):
    for name, value in structure.items():
        new_file = Path(folder).joinpath(name)
        if isinstance(value, dict):
            new_file.mkdir()
            create_file_structure(new_file, value)
        else:
            new_file.write_text(value)

def clean_folder(folder):
    for file in Path(folder).iterdir():
        if file.is_dir():
            clean_folder(file)
            file.rmdir()
        else:
            file.unlink()

if __name__ == "__main__":
    TestSuite().test()