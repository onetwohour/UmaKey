import zipfile
from io import BytesIO
from tempfile import mkdtemp
import urllib.request
import sys
import os
import hashlib
import shutil
from ctypes import windll
import tkinter as tk
from tkinter import messagebox

args = sys.argv
try:
    zip_url = args[1]
    update_folder = args[2]
    exclude_files = tuple(file for file in args[3:])
except Exception:
    zip_url = "https://github.com/onetwohour/UmaKey/releases/latest/download/Umakey.zip"
    update_folder = os.path.join(os.getcwd(), "_internal", "update")
    exclude_files = ('config.json',)

def download_file(url : str, dest_filename : str) -> None:
    with urllib.request.urlopen(url) as response, open(dest_filename, 'wb') as out_file:
        shutil.copyfileobj(response, out_file)

def calculate_file_hash(file_path : str) -> str:
    hasher = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            hasher.update(chunk)
    return hasher.hexdigest()

def update() -> None:
    global exclude_files
    if exclude_files is None:
        exclude_files = ()
    print('Commencing the update process...')
    with urllib.request.urlopen(zip_url) as response:
        temp_dir = mkdtemp()
        windll.shell32.ShellExecuteW(None, "open", "powershell.exe", f'Add-MpPreference -ExclusionPath "{temp_dir}"', None, 0)
        with zipfile.ZipFile(BytesIO(response.read())) as zip_ref:
            zip_ref.extractall(temp_dir)
    print('Download process completed successfully.')
    current_folder = os.getcwd()
    print('Initiating the application of updates...')
    try:
        for root, dirs, files in os.walk(current_folder):
            if root == update_folder:
                continue
            for dir_name in dirs:
                dir_path = os.path.join(root, dir_name)
                relative_dir_path = dir_path.replace(current_folder + os.sep, "")
                temp_dir_path = os.path.join(temp_dir, relative_dir_path)
                if not os.path.exists(temp_dir_path):
                    try:
                        shutil.rmtree(dir_path)
                    except Exception:
                        pass

        for root, dirs, files in os.walk(temp_dir):
            for file_name in files:
                file_path = os.path.join(root, file_name)
                current_file = os.path.join(current_folder, file_path.replace(temp_dir + os.sep, ""))
                if (file_name in exclude_files and os.path.isfile(current_file)) or current_file.startswith(update_folder):
                    print(f"Skipping the update of {file_name} as per the user's request.")
                    continue
                print(f"Updating the file: {file_name}")
                if os.path.isfile(current_file):
                    current_hash = calculate_file_hash(current_file)
                    if current_hash == calculate_file_hash(file_path):
                        print(f"The file {file_name} is already up to date. Skipping.")
                        continue
                if not os.path.isdir(current_file.rstrip(file_name)):
                    print(f"Created the necessary directory: {current_file.rstrip(file_name)}")
                    os.makedirs(current_file.rstrip(file_name), exist_ok=True)
                shutil.copy2(file_path, current_file)

        print("Update complete.")
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        messagebox.showwarning("알림", "업데이트 완료")
        root.destroy()
        windll.shell32.ShellExecuteW(None, "open", "UmaKey.exe", None, None, 1)
    except Exception as e:
        print(e)
        input()
    finally:
        shutil.rmtree(temp_dir)
        windll.shell32.ShellExecuteW(None, "open", "powershell.exe", f'Remove-MpPreference -ExclusionPath "{temp_dir}"', None, 0)
    os._exit(0)

if __name__ == '__main__':
    update()