import sys
import shutil
import re
from pathlib import Path
import io
from typing import Any, Iterable
import unittest
import unittest.mock

from pyCloudSave import Application
from remote import FilebasedRemote, LocalFS

TEMP_FOLDER = Path(__file__).parent.joinpath("temp")
SAVE_FOLDER = TEMP_FOLDER.joinpath("save_folder")
REMOTE_FOLDER = TEMP_FOLDER.joinpath("remote")
LOCAL_REGISTRY = TEMP_FOLDER.joinpath("registry.json")

SAVE_STRUCTURE = {
    "data": {
        "settings.cfg": "Some settings",
        "keybinds.cfg": "Keybinds"
    },
    "save1.dat": "Save data 1",
    "save2.dat": "Save data 2"
}

class IntegrationTest(unittest.TestCase):
    def setUp(self):
        TEMP_FOLDER.mkdir(exist_ok=True)
        SAVE_FOLDER.mkdir()
        create_file_structure(SAVE_FOLDER, SAVE_STRUCTURE)
        REMOTE_FOLDER.mkdir()
        self.input_mock = InputMock()
        self.input_patcher = unittest.mock.patch('pyCloudSave.input', self.input_mock)
        self.input_patcher.start()
        self.output_io = io.StringIO()
        self.output_pathcher = unittest.mock.patch('pyCloudSave.sys.stdout', self.output_io)
        self.output_pathcher.start()

    def tearDown(self):
        shutil.rmtree(TEMP_FOLDER)
        self.output_pathcher.stop()
        self.input_patcher.stop()

    def invoke_command(self, command, inputs=None):
        remote = FilebasedRemote(LocalFS(REMOTE_FOLDER))
        app = Application(remote, LOCAL_REGISTRY)
        if inputs:
            self.input_mock.add_inputs(inputs)
        app.parse_args(split_args(command))
        return self.pop_output()

    def pop_output(self):
        result = self.output_io.getvalue()
        self.output_io.truncate(0)
        self.output_io.seek(0)
        return result

    def test_app(self):
        # Starting with an empty List
        output = self.invoke_command("list")
        self.assertEqual(output, "There are no currently tracked saves.\n")
        output = self.invoke_command("remote list")
        self.assertEqual(output, "There are no saves in a remote.\n")

        # Tracking a new save
        SAVE_NAME_1 = "Pascal's Wager"
        LOOKUP_NAME_1 = "wager"
        self.invoke_command(f'add {SAVE_NAME_1} -r "{SAVE_FOLDER}"')        
        output = self.invoke_command("list")
        self.assertIn(SAVE_NAME_1, output)
        self.assertEqual(count_lines(output), 3)

        # Checking saved data
        output = self.invoke_command(f"show {LOOKUP_NAME_1}")
        self.assertIn(SAVE_NAME_1, output)
        self.assertIn(str(SAVE_FOLDER), output)

        # Editing a save
        save_filters = "*dat, !*save1*"
        game_version = "1.23"
        self.invoke_command(f'edit {LOOKUP_NAME_1} -f "{save_filters}" -v "{game_version}"')
        output = self.invoke_command(f'show {LOOKUP_NAME_1}')
        self.assertIn(save_filters, output)
        self.assertIn(game_version, output)

        # Upload with sync
        self.invoke_command(f'sync {LOOKUP_NAME_1}')
        output = self.invoke_command(r'remote list')
        self.assertIn(SAVE_NAME_1, output)

        # Edit again with remote
        SAVE_NAME_2 = "F.E.A.R"
        LOOKUP_NAME_2 = "fear"
        NEW_GAME_VERSION = "2.6"
        self.input_mock.add_inputs(["yes all"])
        self.invoke_command(f'edit {LOOKUP_NAME_1} -n "{SAVE_NAME_2}" -v "{NEW_GAME_VERSION}"')
        output = self.invoke_command('list')
        self.assertNotIn(SAVE_NAME_1, output)
        output = self.invoke_command(f'show {LOOKUP_NAME_2}')
        self.assertIn(SAVE_NAME_2, output)
        self.assertIn(str(SAVE_FOLDER), output)
        self.assertIn(NEW_GAME_VERSION, output)
        output = self.invoke_command('remote list')
        self.assertNotIn(SAVE_NAME_1, output)
        output = self.invoke_command(f'remote show {LOOKUP_NAME_2}')
        self.assertIn(SAVE_NAME_2, output)
        self.assertIn(NEW_GAME_VERSION, output)

        # Delete local save files and load back
        clean_folder(SAVE_FOLDER)
        self.invoke_command(f"load {LOOKUP_NAME_2}")
        self.assertCountEqual(list_files(SAVE_FOLDER), ['save2.dat'])

        # Rename remote and try loading again (should get an error)
        SAVE_NAME_3 = "Doom Eternal"
        NEW_ROOT_HINT = "Games/Doom/saves"
        self.invoke_command(f'remote edit {LOOKUP_NAME_2} --name "{SAVE_NAME_3}" -r "{NEW_ROOT_HINT}"')
        output = self.invoke_command(f'remote show {SAVE_NAME_3}')
        self.assertIn(NEW_ROOT_HINT, output)
        output = self.invoke_command('remote list')
        self.assertNotIn(SAVE_NAME_2, output)
        self.assertIn(SAVE_NAME_3, output)
        output = self.invoke_command(f'load {SAVE_NAME_2}')
        self.assertEqual(f"Save {SAVE_NAME_2} is not present in remote\n", output)

        # Untrack local
        self.invoke_command(f"untrack {LOOKUP_NAME_2}")
        output = self.invoke_command("list")
        self.assertNotIn(SAVE_NAME_2, output)
        output = self.invoke_command('remote list')
        self.assertIn(SAVE_NAME_3, output)

        # Delete remote
        self.invoke_command(f"remote delete {SAVE_NAME_3}")
        output = self.invoke_command("remote list")
        self.assertNotIn(SAVE_NAME_3, output)

class InputMock():
    def __init__(self):
        self.queue = []

    def add_inputs(self, inputs: Iterable[str]):
        self.queue = list(reversed(inputs)) + self.queue
    
    def __call__(self, prompt='') -> Any:
        if not self.queue:
            value = ''
        else:
            value = self.queue.pop()
        print(f"{prompt}{value}")
        return value

def split_args(string):
    result = re.findall(r"\".*?\"|\'.*?\'|\S+", string)
    return [arg.strip('"') for arg in result]

def count_lines(string):
    return len(re.findall(r"^.*?\S+.*?$", string, flags=re.M))

def list_files(folder):
    p = Path(folder)
    result = []
    for file in p.glob("**/*"):
        if not file.is_file():
            continue
        result.append(str(file.relative_to(p)))
    return result

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