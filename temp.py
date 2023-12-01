import argparse

parser = argparse.ArgumentParser()
subparsers = parser.add_subparsers(required=True)
list_parser = subparsers.add_parser('list')
list_parser.set_defaults(command='list')
sync_parser = subparsers.add_parser('sync')
sync_parser.add_argument('name', nargs='+')
sync_parser.add_argument('--new_name', '-n', '--name')
sync_parser.add_argument('-a', '--all')
args = parser.parse_args()
print(args)
print('new_name' in args)
args.new_name = "bobby"
print(args)