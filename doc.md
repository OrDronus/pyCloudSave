Remote options:
- Type
- Options

Local saves:
- Game name - name
- Root folder - root
- Filters - filters (optional)
- Game version - version (optional)
- Last sync - last_sync (auto)
- Last modified - last_modified (calculated)
- ID name - id_name (name in a dictionary)
 
Remote saves:
- Save name - name
- Root folder hint - root_hint (optional)
- Filters hint - filters_hint (optional)
- Game version - version (optional)
- Last upload - last_upload (auto)
- File size - size (calculated)


Commands:
- list
- show
- add/track
- edit SAVE_NAME
- remove/untrack SAVE_NAME
- load SAVE_NAME
- upload SAVE_NAME 
- sync SAVE_NAME
- remote
    - list
    - show
    - edit SAVE_NAME [options]
    - delete SAVE_NAME

Filter format:
"*" - any nuber of any symbols
"/" or "\" namepath separator (will be converted)
"!" as the first character - filter is inverted

Date format:
yy-mm-dd hh:mm:ss

Remote
upload_time

Local
upload_time
mod_time