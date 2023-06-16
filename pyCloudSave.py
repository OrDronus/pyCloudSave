import sys
import shutil
from pathlib import Path
from tabulate import tabulate

from remote import Remote, FSRemote
from local import Local

class AppException(Exception):
    pass

class Application:
    def __init__(self, remote: Remote, local_registry=None) -> None:
        self.remote = remote
        self.local = Local(local_registry)
        self.temp_folder = Path(__file__).parent.joinpath('temp')
        self.temp_folder.mkdir(exist_ok=True)

    def parse_args(self, argv):
        commands = {
            'remote': {
                'list': self.command_remote_list,
                'show': self.command_remote_show,
                'edit': self.command_remote_edit,
                'delete': self.command_remote_delete
            },
            'local': {
                'list': self.command_local_list,
                'add': self.command_local_add,
                'edit': self.command_local_edit,
                'untrack': self.command_local_untrack
            },
            'load': self.command_load,
            'upload': self.command_upload,
            'sync': self.command_sync
        }
        try:
            arg = argv[0].lower()
            rem = argv[1:]
            command = commands[arg]
            if isinstance(command, dict):
                arg = rem[0].lower()
                rem = rem[1:]
                command = command[arg]
        except KeyError:
            print(f"Unknown command: {arg}")
        else:
            command(' '.join(rem).lower())

    def command_remote_list(self, save_name):
        print("This method is not yet implemented")

    def command_remote_show(self, save_name):
        print("This method is not yet implemented")

    def command_remote_edit(self, save_name):
        print("This method is not yet implemented")

    def command_remote_delete(self, save_name):
        print("This method is not yet implemented")

    def command_local_list(self, save_name):
        headers = ['Save name', 'Last modification', 'Last sync']
        data = [
            [save['name'], self.local.get_last_mod_time(save['name'].lower()), save['last_sync']]
            for save in self.local.get_saves_list()
        ]
        print(tabulate(data, headers, tablefmt='github'))

    def command_local_add(self, _):
        print("Adding new save to registry")
        save_name = input("Enter save name: ").strip()
        root_folder = input("Enter root folder: ").strip()
        patterns = input(
            "Enter file patterns (comma separated). Leave blank for default (**/*).: "
            ).strip()
        self.local.add(save_name, root_folder, patterns)

    def command_local_edit(self, save_name):
        save = self.local.registry[save_name]
        new_parameters = {}
        print("Editing save. You can leave any field blank to keep a value unchanged.")
        save_name = input(f"Save name: {save['name']}\nNew value: ").strip()
        if save_name:
            new_parameters['name'] = save_name
        root_folder = input(f"Root folder: {save['root']}\nNew value: ").strip()
        if root_folder:
            new_parameters['root'] = root_folder
        patterns = input(
            f"File patterns: {save['patterns']} (Default: **\\*)\nNew value: "
            ).strip()
        if patterns:
            new_parameters['patterns'] = patterns
        self.remote.edit_save(save_name, new_parameters)

    def command_local_untrack(self, save_name):
        # Check for existence and ask user for confirmation
        self.local.untrack(save_name)

    def command_load(self, save_name):
        print(f"Loading save {save_name}...")
        tmp_file = self.temp_folder.joinpath(save_name)
        self.remote.load_save(save_name, tmp_file)
        self.local.unpack_save_files(save_name, tmp_file)
        self.local.stamp_synced(save_name)
        tmp_file.unlink()
        print(f"Save {save_name} loaded.")

    def command_upload(self, save_name):
        print(f"Uploading save {save_name}...")
        local_save = self.local.get_save(save_name)
        remote_saves = self.remote.get_saves()
        if save_name not in remote_saves:
            self.remote.create_save(local_save['name'], local_save['root'], local_save['patterns'])
        tmp_file = self.temp_folder.joinpath(save_name)
        self.local.pack_save_files(save_name, tmp_file)
        self.remote.upload_save(save_name, tmp_file)
        self.local.stamp_synced(save_name)
        tmp_file.unlink()
        print(f"Save {save_name} uploaded.")

    def command_sync(self, save_name):
        if save_name == 'all':
            for save in self.local.get_saves_list():
                self.command_sync(save['name'].lower())
            return
        local_modification = self.local.get_last_mod_time(save_name)
        local_sync = self.local.get_save(save_name)['last_sync']
        try:
            remote_upload = self.remote.get_saves()[save_name]['last_upload']
        except KeyError:
            remote_upload = ''
        remote_updated = remote_upload > local_sync
        local_updated = local_modification > local_sync
        if remote_updated and local_updated:
            print(f"Warning, save files for {save_name} are out of sync, some data can be lost, please load or upload explicitly.")
            print(tabulate(
                [local_modification, local_sync, remote_upload],
                headers=['Local modification', 'Last synced', 'Remote uploaded']
            ))
        elif local_updated:
            self.command_upload(save_name)
        elif remote_updated:
            self.command_load(save_name)

def main():
    remote_folder = Path(__file__).parent.joinpath('remote')
    remote_folder.mkdir(exist_ok=True)
    app = Application(FSRemote(remote_folder))
    app.parse_args(sys.argv[1:])

if __name__ == "__main__":
    main()