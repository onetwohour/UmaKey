import zipfile
from io import BytesIO
from tempfile import mkdtemp
import urllib.request
import sys, os
import hashlib
import shutil
from ctypes import cdll, c_wchar_p, windll

args = sys.argv
zip_url = args[1]
exclude_files = [*args[2:]]

def download_file(url, dest_filename):
    with urllib.request.urlopen(url) as response, open(dest_filename, 'wb') as out_file:
        shutil.copyfileobj(response, out_file)

def calculate_file_hash(file_path):
    hasher = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            hasher.update(chunk)
    return hasher.hexdigest()

def update():
    global exclude_files
    if exclude_files is None:
        exclude_files = []
    print('Commencing the update process...')
    with urllib.request.urlopen(zip_url) as response:
        temp_dir = mkdtemp()
        with zipfile.ZipFile(BytesIO(response.read())) as zip_ref:
            zip_ref.extractall(temp_dir)
    print('Download process completed successfully.')
    current_folder = os.getcwd()
    print('Initiating the application of updates...')
    try:
        for root, _, files in os.walk(temp_dir):
            for file_name in files:
                file_path = os.path.join(root, file_name)
                current_file = os.path.join(current_folder, file_path.replace(temp_dir + '\\', ""))
                if file_name in exclude_files and os.path.isfile(current_file):
                    print(f"Skipping the update of {file_name} as per the user's request.")
                    continue
                print(f"Updating the file: {file_name}")
                if os.path.isfile(current_file):
                    current_hash = calculate_file_hash(current_file)
                    if current_hash == calculate_file_hash(file_path):
                        continue
                if not os.path.isdir(current_file.rstrip(file_name)):
                    os.makedirs(current_file.rstrip(file_name), exist_ok=True)
                shutil.copy2(file_path, current_file)

        print("Update complete.")
        file_name = os.path.join(os.getcwd(), '_internal', 'warning.dll')
        dll = cdll.LoadLibrary(file_name).show_warning_dialog
        dll.argtypes = [c_wchar_p]
        dll.restype = None
        dll("업데이트 완료")
        del dll
    except Exception as e:
        print(e)
        input()
        return
    shutil.rmtree(temp_dir)
    windll.shell32.ShellExecuteW(None, "open", "UmaKey.exe", None, None, 1)
    os._exit(0)

if __name__ == '__main__':
    update()