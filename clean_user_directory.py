"""
Clean User directory

Some clients usually have a lot of custom modules/submodules that they are not using. 
This make hard to debug their custom modules.

To make it easy, run the database without modules and it will show the missing dependencies.
You can just copy and paste the array inside folders_to_find set.

This will create a new folder only with the important folders.

Created by: VMAC
"""

import os
import shutil

# search directory
base_path = './<user directory>'

# new directory with the cleaned data
new_dir = os.path.abspath('./<new directory>')
os.makedirs(new_dir, exist_ok=True)

folders_to_find = set(['Missing App list'])
found_folders = {}

# search
for root, dirs, files in os.walk(base_path):
    for d in dirs:
        if d in folders_to_find:
            abs_path = os.path.abspath(os.path.join(root, d))
            found_folders[d] = abs_path

# Move found directories
for folder_name, folder_path in found_folders.items():
    dest_path = os.path.join(new_dir, folder_name)
    if not os.path.exists(dest_path):
        print(f"Moving {folder_name} to {dest_path}")
        shutil.move(folder_path, dest_path)
    else:
        print(f"Skipping {folder_name}: already exists at destination.")
