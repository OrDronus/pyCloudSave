Local data (saved in home folder):
- Remote options
    - Type
    - Location
- Tracked saves
    - Save name (name)
    - Last upload (last_upload)
    - Root folder (root)
    - File globs (patterns)

Remote data:
- Save name (name)
- Last upload (last_upload)
- File glob hint (pattern_hint) (optional)
- Root folder hint (root_hint) (optional)

Commands:
- remote
    - list
    - show SAVE_NAME
    - edit SAVE_NAME
    - delete SAVE_NAME
- local
    - list
    - add
    - edit SAVE_NAME
    - untrack SAVE_NAME
- load SAVE_NAME
- upload SAVE_NAME 
- sync SAVE_NAME

Date format:
yyyy-mm-dd hh-mm-ss.microseconds