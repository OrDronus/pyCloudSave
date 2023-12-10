"Main module handles argment parsing and ties everything together"

import argparse
import json
import sys
from datetime import MINYEAR, datetime, timedelta
from numbers import Real
from pathlib import Path
from typing import Any, Union

from tabulate import tabulate

from common import normalize_name, normalized_search
from local import Local
from remote import FSRemote, GDriveRemote, Remote

DATETIME_PRINT_FORMAT = "%d.%m.%y %H:%M:%S"
MIN_DATE = datetime(MINYEAR, 1, 1)
YES, NO, YESALL, NOALL = 1, 2, 3, 4

def datetime_to_str(obj: Union[datetime, Any], default='-'):
    if not isinstance(obj, datetime):
        return default
    return datetime.strftime(obj, DATETIME_PRINT_FORMAT)

def size_to_str(obj: Union[Real, Any], default='-'):
    if not isinstance(obj, Real):
        return default
    prefixes = ['b', 'Kb', 'Mb', 'Gb']
    for prefix in prefixes:
        if obj < 1024:
            return f"{obj:.1f} {prefix}"
        obj /= 1024
    return f"{obj:.1f} Tb"

def find_save(registry: dict, name: str) -> tuple[str, dict]:
    results = normalized_search(registry.keys(), name)
    if not results:
        raise AppError(f"No saves matching {name}.")
    if len(results) > 1:
        raise AppError(f"More than one save matches {name}: {', '.join(registry[s]['name'] for s in results)}.")
    return results[0], registry[results[0]]

class AppError(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message
        
class Application:
    def __init__(self, remote: Remote, local_registry=None):
        self.remote = remote
        self.local = Local(local_registry)
        self.temp_folder = Path(__file__).parent.joinpath('temp')
        self.temp_folder.mkdir(exist_ok=True)

    def parse_args(self, argv):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(required=True)

        name_parser = argparse.ArgumentParser(add_help=False)
        name_parser.add_argument('name', nargs='+')

        list_parser = subparsers.add_parser('list')
        list_parser.set_defaults(command=self.command_list)

        show_parser = subparsers.add_parser('show', parents=[name_parser])
        show_parser.set_defaults(command=self.command_show)

        track_parser = subparsers.add_parser('track', aliases=['add'], parents=[name_parser])
        track_parser.add_argument('--root', '-r', required=True)
        track_parser.add_argument('--filters', '-f')
        track_parser.add_argument('--version', '-v')
        track_parser.set_defaults(command=self.command_track)

        edit_parser = subparsers.add_parser('edit', parents=[name_parser])
        edit_parser.add_argument('--new_name', '--name', '-n')
        edit_parser.add_argument('--root', '-r')
        edit_parser.add_argument('--filters', '-f')
        edit_parser.add_argument('--version', '-v')
        edit_parser.set_defaults(command=self.command_edit)

        untrack_parser = subparsers.add_parser('untrack', aliases=['remove'], parents=[name_parser])
        untrack_parser.set_defaults(command=self.command_untrack)

        load_parser = subparsers.add_parser('load', parents=[name_parser])
        load_parser.set_defaults(command=self.command_load)

        upload_parser = subparsers.add_parser('upload', parents=[name_parser])
        upload_parser.set_defaults(command=self.command_upload)

        sync_parser = subparsers.add_parser('sync', parents=[name_parser])
        sync_parser.set_defaults(command=self.command_sync)

        remote_parser = subparsers.add_parser('remote')
        remote_subparsers = remote_parser.add_subparsers(required=True)

        remote_list_parser = remote_subparsers.add_parser('list')
        remote_list_parser.set_defaults(command=self.command_remote_list)

        remote_show_parser = remote_subparsers.add_parser('show', parents=[name_parser])
        remote_show_parser.set_defaults(command=self.command_remote_show)

        remote_edit_parser = remote_subparsers.add_parser('edit', parents=[name_parser])
        remote_edit_parser.add_argument('--new_name', '--name', '-n')
        remote_edit_parser.add_argument('--version', '-v')
        remote_edit_parser.add_argument('--root', '-r')
        remote_edit_parser.add_argument('--filters', '-f')
        remote_edit_parser.set_defaults(command=self.command_remote_edit)

        remote_delete_parser = remote_subparsers.add_parser('delete', parents=[name_parser])
        remote_delete_parser.set_defaults(command=self.command_remote_delete)

        args = parser.parse_args(argv)
        if 'name' in args:
            if len(args.name) > 1:
                args.name = ' '.join(args.name)
            else:
                args.name = args.name[0]
        try:
            args.command(args)
        except AppError as err:
            print(err.message)

    def command_list(self, _):
        local_registry = self.local.get_registry()
        if not local_registry:
            print("There are no currently tracked saves.")
            return
        remote_registry = self.remote.get_registry()
        headers = ['Save name', 'Last modification', 'Last sync', 'Remote last upload', 'Remote size']
        data = []
        for ls in local_registry.values():
            rs = remote_registry.get(normalize_name(ls['name']), {})
            data.append([
                ls['name'],
                datetime_to_str(ls.get('last_modification')),
                datetime_to_str(ls.get('last_sync')),
                datetime_to_str(rs.get('last_upload')),
                size_to_str(rs.get('size'))
            ])
        print(tabulate(data, headers, tablefmt='github'))

    def command_show(self, args):
        save_name, save = find_save(self.local.get_registry(), args.name)
        print(f"Game name: {save['name']}")
        if save['version']:
            print(f"Game version: {save['version']}")
        print(f"Root folder: {save['root']}")
        if save['filters']:
            print(f"Filters: {save['filters']}")
        print(f"Last modification: {datetime_to_str(save['last_modification'])}")
        print(f"Last sync: {datetime_to_str(save['last_sync'])}")
        remote_save = self.remote.get_registry().get(save_name)
        if not remote_save:
            return
        print(f"Remote last upload: {remote_save['last_upload']}")
        print(f"Remote size: {size_to_str(remote_save['size'])}")

    def command_track(self, args):
        print(f"Adding new save to registry: {args.name}")
        self.local.track(args.name, args.root, args.filters, args.version)
    
    def command_edit(self, args):
        save_name, local_save = find_save(self.local.get_registry(), args.name)
        self.local.edit(save_name, args.new_name, args.root, args.filters, args.version)
        remote_save = self.remote.get_registry().get(save_name)
        if not remote_save:
            return
        asker = YesNoAsker()
        remote_args = {}
        if args.new_name and asker.ask("Do you want to update game's name in remote as well?"):
            remote_args['new_name'] = args.new_name
        if args.root and asker.ask("Do you want to update root hint in remote as well?"):
            remote_args['root_hint'] = args.root
        if args.filters and asker.ask("Do you want to update filters hint in remote as well?"):
            remote_args['filters_hint'] = args.filters
        if args.version and remote_save['last_upload'] == local_save['last_sync'] and asker.ask("Do you want to update game version in remote as well?"):
            remote_args['version'] = args.version
        if remote_args:
            self.remote.edit_save(save_name, **remote_args)

    def command_untrack(self, args):
        # Check for existence and ask user for confirmation
        save_name, save = find_save(self.local.get_registry(), args.name)
        self.local.untrack(save_name)
        print(f"Save {save['name']} successfully deleted.")

    def command_upload(self, args):
        save_name, _ = find_save(self.local.get_registry(), args.name)
        self._upload(save_name)

    def command_load(self, args):
        save_name, _ = find_save(self.local.get_registry(), args.name)
        self._load(save_name)

    def command_sync(self, args):
        if args.name in ('--all', '-a'):
            for save_name in self.local.get_registry().keys():
                self._sync(save_name)
        else:
            save_name, _ = find_save(self.local.get_registry(), args.name)
            self._sync(save_name)

    def _sync(self, save_name):
        local_save = self.local.get_registry()[save_name]
        remote_save = self.remote.get_registry().get(save_name)
        remote_last_upload = remote_save['last_upload'] if (remote_save and remote_save['last_upload']) else MIN_DATE
        local_last_sync = local_save['last_sync'] or MIN_DATE
        local_last_modification = local_save['last_modification'] or MIN_DATE
        remote_updated = remote_last_upload > local_last_sync
        local_updated = local_last_modification > local_last_sync
        if remote_updated and local_updated:
            print(f"Warning, save files for {save_name} are out of sync, some data can be lost, please load or upload explicitly.")
            data =[[
                datetime_to_str(local_save['last_modification']),
                datetime_to_str(local_save.get('last_sync')),
                datetime_to_str(remote_save['last_upload'])
            ]]
            headers=['Local modification', 'Last synced', 'Remote last upload']
            print(tabulate(data, headers, tablefmt='github'))
        elif local_updated:
            self._upload(save_name)
        elif remote_updated:
            self._load(save_name)

    def _upload(self, save_name):
        local_save = self.local.get_registry()[save_name]
        print(f"Uploading save {local_save['name']}...")
        remote_registry = self.remote.get_registry()
        if save_name not in remote_registry:
            self.remote.register_new_save(local_save['name'], local_save['root'], local_save['filters'], local_save['version'])
        tmp_file = self.temp_folder.joinpath(save_name)
        self.local.pack_save_files(save_name, tmp_file)
        _datetime = datetime.now()
        self.remote.upload_save(save_name, tmp_file, _datetime)
        self.local.edit(save_name, last_sync=_datetime)
        tmp_file.unlink()
        print(f"Save {local_save['name']} uploaded.")

    def _load(self, save_name):
        local_save = self.local.get_registry()[save_name]
        print(f"Loading save {local_save['name']}...")
        tmp_file = self.temp_folder.joinpath(save_name)
        self.remote.load_save(save_name, tmp_file)
        self.local.unpack_save_files(save_name, tmp_file)
        self.local.edit(save_name, last_sync=datetime.now())
        tmp_file.unlink()
        print(f"Save {local_save['name']} loaded.")

    def command_remote_list(self, _):
        remote_registry = self.remote.get_registry()
        if not remote_registry:
            raise AppError("There are no saves in a remote.")
        headers = ['Save name', 'Last upload', 'Size']
        data = [
            [s['name'], datetime_to_str(s['last_upload']), size_to_str(s['size'])]
            for s in remote_registry.values()
        ]
        print(tabulate(data, headers, tablefmt='github'))

    def command_remote_show(self, args):
        _, save = find_save(self.remote.get_registry(), args.name)
        for name, val in save.items():
            print(f"{name.replace('_', ' ').title()}: {val}")

    def command_remote_edit(self, args):
        print("This method is not yet implemented.")

    def command_remote_delete(self, args):
        save_name, save = find_save(self.remote.get_registry(), args.name)
        self.remote.delete_save(save_name)
        print(f"Save {save['name']} succesfully deleted.")

class YesNoAsker:
    def __init__(self):
        self.yes_all = False
        self.no_all = False
    
    def ask(self, message=None):
        if self.yes_all:
            return True
        if self.no_all:
            return False
        if message:
            print(message)
        while True:
            res = input("yes/no/yes all/no all: ").lower()
            if res in ('y', 'yes'):
                return True
            elif res in ('n', 'no'):
                return False
            elif res in ('ya', 'yesall', 'yes all'):
                self.yes_all = True
                return True
            elif res in ('na', 'noall', 'no all'):
                self.no_all = True
                return False


def create_remote(options):
    if options['type'] == 'localfs':
        return FSRemote(options['folder'])
    elif options['type'] == 'gdrive':
        return GDriveRemote()
    else:
        raise ValueError("Remote is incorrect")

def yes_no_all_dialog():
    while True:
        res = input("yes/no/yes all/no all: ").lower()
        if res in ('y', 'yes'):
            return YES
        elif res in ('n', 'no'):
            return NO
        elif res in ('ya', 'yesall', 'yes all'):
            return YESALL
        elif res in ('na', 'noall', 'no all'):
            return NOALL

def main():
    with open('remote_options.json') as fio:
        remote_options = json.load(fio)
    remote = create_remote(remote_options)
    app = Application(remote)
    app.parse_args(sys.argv[1:])

if __name__ == "__main__":
    main()