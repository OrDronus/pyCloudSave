# from pydrive.auth import GoogleAuth
# from pydrive.drive import GoogleDrive

# gauth = GoogleAuth() 
# gauth.LocalWebserverAuth()      
# drive = GoogleDrive(gauth) 

# Parsing '2023-06-30T12:58:49.695Z'
import remote
from remote import FOLDER_MIME_TYPE

rem = remote.GDriveRemote()
rem._init_drive()
# print(rem._load_hints())
# rem._save_hints({'Name': 'Bobby'})
# print(rem._load_hints())
file = rem._get_file(
    f"title = 'pyCloudSave' and mimeType = '{FOLDER_MIME_TYPE}' and 'root' in parents and trashed = false"
)
if file:
    print(file['title'])
else:
    print('Nothing')