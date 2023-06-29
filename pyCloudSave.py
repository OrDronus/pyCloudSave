import sys
import json
import shutil
from pathlib import Path
from tabulate import tabulate
from datetime import datetime, timedelta

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
                'hints': self.command_remote_hints,
                'delete': self.command_remote_delete
            },
            'list': self.command_list,
            'track': self.command_track,
            'untrack': self.command_untrack,
            'edit': self.command_edit,
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

    def command_remote_list(self, _):
        remote_registry = self.remote.get_registry()
        headers = ['Save name', 'Last upload', 'Size']
        data = [
            [s['name'], s['last_upload'], size_to_str(s['size'])]
            for s in remote_registry.values()
        ]
        print(tabulate(data, headers, tablefmt='github'))

    def command_remote_show(self, save_name):
        remote_registry = self.remote.get_registry()
        save = remote_registry[save_name]
        for name, val in save.items():
            print(f"{name.replace('_', ' ').title()}: {val}")

    def command_remote_hints(self, save_name):
        print("This method is not yet implemented")

    def command_remote_delete(self, save_name):
        self.remote.delete_save(save_name)
        print(f"Save {save_name} succesfully deleted.")

    def command_list(self, _):
        headers = ['Save name', 'Last modification', 'Last sync', 'Remote last upload', 'Remote size']
        local_registry = self.local.registry
        remote_registry = self.remote.get_registry()
        data = []
        for ls in local_registry.values():
            rs = remote_registry.get(ls['name'].lower(), {})
            data.append([
                ls['name'], ls['last_modification'], ls.get('last_sync'),
                rs.get('last_upload', ''), size_to_str(rs['size']) if rs else ''
            ])
        print(tabulate(data, headers, tablefmt='github'))

    def command_track(self, _):
        print("Adding new save to registry")
        save_name = input("Enter save name: ").strip()
        root_folder = input("Enter root folder: ").strip()
        patterns = input(
            "Enter one or several comma separated file patterns (optional): "
            ).strip()
        ignore = input(
            "Enter one or several comma separated ignore rules (optional): "
            ).strip()
        self.local.track(save_name, root_folder, patterns, ignore)

    def command_edit(self, save_name):
        print("This method is not yet implemented")
        return
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

    def command_untrack(self, save_name):
        # Check for existence and ask user for confirmation
        self.local.untrack(save_name)

    def command_load(self, save_name):
        print(f"Loading save {save_name}...")
        local_save = self.local.registry[save_name]
        tmp_file = self.temp_folder.joinpath(save_name)
        self.remote.load_save(local_save['name'], tmp_file)
        self.local.unpack_save_files(save_name, tmp_file)
        self.local.edit(save_name, {'last_sync': datetime.now()})
        tmp_file.unlink()
        print(f"Save {save_name} loaded.")

    def command_upload(self, save_name):
        print(f"Uploading save {save_name}...")
        local_save = self.local.registry[save_name]
        remote_registry = self.remote.get_registry()
        tmp_file = self.temp_folder.joinpath(save_name)
        self.local.pack_save_files(save_name, tmp_file)
        self.remote.upload_save(local_save['name'], tmp_file)
        self.local.edit(save_name, {'last_sync': datetime.now()+timedelta(seconds=1)})
        tmp_file.unlink()
        if save_name not in remote_registry:
            hints = {'root_hint': local_save['root']}
            if local_save.get('patterns'):
                hints['patterns_hint']: local_save['patterns']
            if local_save.get('ignore'):
                hints['ignore_hints']: local_save['ignore']
            self.remote.add_hints(save_name, hints)
        print(f"Save {save_name} uploaded.")

    def command_sync(self, save_name):
        if save_name == 'all':
            for save in self.local.registry.values():
                self.command_sync(save['name'].lower())
            return
        local_save = self.local.registry[save_name]
        remote_save = self.remote.get_registry().get(save_name)
        remote_updated = (
            remote_save is not None and 
            (not local_save.get('last_sync') or remote_save['last_upload'] > local_save['last_sync'])
        )
        local_updated = (
            local_save.get('last_modification') and
            (not local_save.get('last_sync') or local_save['last_modification'] > local_save['last_sync'])
        )
        if remote_updated and local_updated:
            print(f"Warning, save files for {save_name} are out of sync, some data can be lost, please load or upload explicitly.")
            data =[[local_save['last_modification'], local_save.get('last_sync'), remote_save['last_upload']]]
            headers=['Local modification', 'Last synced', 'Remote uploaded']
            print(tabulate(data, headers, tablefmt='github'))
        elif local_updated:
            self.command_upload(save_name)
        elif remote_updated:
            self.command_load(save_name)

def create_remote(options):
    if options['type'] == 'localfs':
        return FSRemote(options['folder'])
    else:
        raise ValueError("Remote is incorrect")
    
def size_to_str(size):
    prefixes = ['b', 'Kb', 'Mb', 'Gb']
    for prefix in prefixes:
        if size < 1024:
            return f"{size:.1f} {prefix}"
        size /= 1024
    return f"{size:.1f} Tb"

def main():
    with open('remote_options.json') as fio:
        remote_options = json.load(fio)
    remote = create_remote(remote_options)
    app = Application(remote)
    app.parse_args(sys.argv[1:])

if __name__ == "__main__":
    main()