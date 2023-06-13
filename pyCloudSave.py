import argparse
import sys
import json
from pathlib import Path

from remote import Remote, FSRemote
from local import Local

class AppException(Exception):
    pass

class Application:
    def __init__(self, remote: Remote, local_registry=None) -> None:
        self.remote = remote
        self.local = Local(local_registry)

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
                arg = rem[0]
                rem = rem[1:]
                command = command[arg]
        except KeyError:
            print(f"Unknown command: {arg}")
        else:
            command(' '.join(rem))

    def command_remote_list(self, save_name):
        print("This method is not yet implemented")

    def command_remote_show(self, save_name):
        print("This method is not yet implemented")

    def command_remote_edit(self, save_name):
        print("This method is not yet implemented")

    def command_remote_delete(self, save_name):
        print("This method is not yet implemented")

    def command_local_list(self, save_name):
        print("This method is not yet implemented")

    def command_local_add(self, _):
        print("Adding new save to registry")
        save_name = input("Enter save name: ").strip()
        root_folder = input("Enter root folder: ").strip()
        patterns = input(
            "Enter file patterns (comma separated). Leave blank for default (**\\*).: "
            ).strip()
        if not patterns:
            patterns = '**\\*'
        parameters = {
            'name': save_name,
            'root': root_folder,
            'patterns': patterns
        }
        self.local.add(save_name.lower(), parameters)

    def command_local_edit(self, save_name):
        print("This method is not yet implemented")

    def command_local_untrack(self, save_name):
        print("This method is not yet implemented")

    def command_load(self, save_name):
        print("This method is not yet implemented")

    def command_upload(self, save_name):
        print("This method is not yet implemented")

    def command_sync(self, save_name):
        print("This method is not yet implemented")
        
def main():
    app = Application(FSRemote(Path(__file__).parent))
    app.parse_args(sys.argv[1:])

if __name__ == "__main__":
    main()