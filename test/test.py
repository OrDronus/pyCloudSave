import sys
import shutil
from pathlib import Path
from io import StringIO
from unittest.mock import patch

import pyCloudSave
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
        with patch("pyCloudSave.sys.stdin", self.stdin):
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
        self.stdin = StringIO()

    def perform_test(self):
        remote = FSRemote(self.remote_folder)
        app = pyCloudSave.Application(remote, self.local_registry)

        # Empty List
        print("> list")
        app.command_list()
        print()
        print("> remote list")
        app.command_remote_list()
        print()

        # Track save
        print(f"> track\n> {SAVE_NAME}\n> {self.save_folder}\n>\n>\n")
        self.stdin.write(f"{SAVE_NAME}\n{self.save_folder}\n\n\n")
        self.stdin.seek(0)
        app.command_track()
        print("> list")
        app.command_list()
        print()

        # Upload with sync
        print(f"> sync{LOOKUP_NAME}")
        app.command_sync(LOOKUP_NAME)
        app.command_list()
        print("File Tree:")
        print_ftree(self.temp_folder)
        print()

        # Delete local
        print("Deleting local files")
        clean_folder(self.save_folder)
        print("File Tree:")
        print_ftree(self.temp_folder)
        print()

        # Load back
        print(f"> sync {LOOKUP_NAME}")
        app.command_sync(LOOKUP_NAME)
        print("File Tree:")
        print_ftree(self.temp_folder)
        print()

        # Untrack local
        print(f"> untrack{LOOKUP_NAME}")
        app.command_untrack(LOOKUP_NAME)
        print("> list")
        app.command_list()
        print("> remote list")
        app.command_remote_list()
        print()

        # Delete remote
        print(f"> remote delete {LOOKUP_NAME}")
        app.command_remote_delete(LOOKUP_NAME)
        print("> remote list")
        app.command_remote_list()

    def clean_up(self):
        shutil.rmtree(self.temp_folder)

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