import sys
import shutil
import re
import json
from pathlib import Path
import io
from typing import Any, Iterable
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
import unittest
import unittest.mock

from pyCloudSave import Application
from remote import FilebasedRemote, LocalFS, GDriveFS, FOLDER_MIME_TYPE, FileDoesNotExistError

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

class AppTest(unittest.TestCase):
    saves = {
        'Grim Dawn': {
            'save_folder': TEMP_FOLDER.joinpath('Grim Dawn')
        },
        'Shadows of Loathing': {
            'save_folder': TEMP_FOLDER.joinpath('Shadows')
        }
    }
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

        # Untrack local
        self.invoke_command(f"untrack {LOOKUP_NAME_2}")
        output = self.invoke_command("list")
        self.assertNotIn(SAVE_NAME_2, output)
        output = self.invoke_command('remote list')
        self.assertIn(SAVE_NAME_2, output)

        # Copy remote back into local
        self.invoke_command(f"track -c {LOOKUP_NAME_2}")
        output = self.invoke_command(f"show {LOOKUP_NAME_2}")
        self.assertIn(SAVE_NAME_2, output)
        self.assertIn(str(SAVE_FOLDER), output)

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

        # Delete remote
        self.invoke_command(f"remote delete {SAVE_NAME_3}")
        output = self.invoke_command("remote list")
        self.assertNotIn(SAVE_NAME_3, output)

class GDriveFSTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.local_temp_folder = Path(__file__).parent.joinpath("temp")
        cls.local_temp_folder.mkdir(exist_ok=True)
        temp_folder_name = 'pyCloudSave_temp'
        gauth = GoogleAuth()
        gauth.LocalWebserverAuth()
        cls.drive = GoogleDrive(gauth)
        cls.remote_temp_folder = cls.drive.CreateFile({'title': temp_folder_name, 'mimeType': FOLDER_MIME_TYPE})
        cls.remote_temp_folder.Upload()
        cls.gDriveFS = GDriveFS(temp_folder_name)
    
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.local_temp_folder)
        cls.remote_temp_folder.Delete()

    def tearDown(self):
        clean_folder(self.local_temp_folder)
        for file in self.drive.ListFile({'q': f"'{self.remote_temp_folder['id']}' in parents"}).GetList():
            file.Delete()
        
    def testUploadJsonLoadFile(self):
        test_data = {'1 1': 2, '3 3': '4', '5 5': None, '6 6': False}
        filename = 'test_file1.json'
        local_file = self.local_temp_folder.joinpath(filename)
        self.gDriveFS.upload_json(filename, test_data)
        self.gDriveFS.load_file(filename, str(local_file))
        with open(local_file) as fio:
            result = json.load(fio)
        self.assertEqual(test_data, result)

    def testUploadFileLoadJson(self):
        test_data = {'1 1': 2, '3 3': '4', '5 5': None, '6 6': False}
        filename = 'test_file2.json'
        local_file = self.local_temp_folder.joinpath(filename)
        with open(local_file, 'w') as fio:
            json.dump(test_data, fio)
        self.gDriveFS.upload_file(filename, str(local_file))
        result = self.gDriveFS.load_json(filename)
        self.assertEqual(test_data, result)

    def testRenameFile(self):
        filename = 'test_file3.json'
        local_file = self.local_temp_folder.joinpath(filename)
        local_target = self.local_temp_folder.joinpath('test_file3_target.json')
        test_data = 'Foo Bar'
        local_file.write_text(test_data)
        self.gDriveFS.upload_file(filename, str(local_file))
        new_filename = 'test_file3_renamed.json'
        self.gDriveFS.rename_file(filename, new_filename)
        with self.assertRaises(FileDoesNotExistError):
            self.gDriveFS.load_file(filename, local_target)
        self.gDriveFS.load_file(new_filename, local_target)
        result = local_target.read_text()
        self.assertEqual(test_data, result)

    def testDeleteFile(self):
        filename = 'test_file4.json'
        local_file = self.local_temp_folder.joinpath(filename)
        local_file.write_text("Foo Bar")
        self.gDriveFS.upload_file(filename, local_file)
        self.gDriveFS.delete_file(filename)
        with self.assertRaises(FileDoesNotExistError):
            self.gDriveFS.load_file(filename, local_file)
        

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

def clean_gdrive_folder(folder_id: str, drive: GoogleDrive):
    for file in drive.ListFile({'q': f"'{folder_id}' in parents and trashed = false"}).GetList():
        if file['mimeType'] == FOLDER_MIME_TYPE:
            clean_gdrive_folder(file['id'], drive)
        file.Delete()