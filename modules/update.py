import urllib.request
import json, os
from ctypes import cdll, c_wchar_p

def check_new_release(repo_owner, repo_name, current_version):
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases/latest"
    try:
        with urllib.request.urlopen(url) as response:
            data = response.read()
            latest_release = json.loads(data)
            latest_version = latest_release['tag_name']
            if latest_version != current_version:
                if not os.path.isfile('./_internal/warning.dll'):
                    raise FileNotFoundError(f"File not exist : {os.path.join(os.getcwd(), '_internal', 'warning.dll')}")
                dll = cdll.LoadLibrary(os.path.join(os.getcwd(), '_internal', 'warning.dll')).show_warning_dialog
                dll.argtypes = [c_wchar_p]
                dll.restype = None
                dll(f"새로운 업데이트 : {latest_version}")
                del dll
    except Exception as e:
        print(f"Failed to fetch latest release: {e}")

if __name__ == '__main__':
    check_new_release("onetwohour", "UmaKey", "0.0.0")