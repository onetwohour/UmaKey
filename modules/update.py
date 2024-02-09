import urllib.request
import json
import os
from ctypes import cdll, c_wchar_p

def check_new_release(repo_owner, repo_name, current_version):
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases/latest"
    try:
        with urllib.request.urlopen(url) as response:
            latest_release = json.loads(response.read())
            latest_version = latest_release['tag_name']
            if latest_version != current_version:
                file_name = os.path.join(os.getcwd(), '_internal', 'warning.dll')
                if os.path.isfile('./_internal/warning.dll'):
                    dll = cdll.LoadLibrary(file_name).show_warning_dialog
                    dll.argtypes = [c_wchar_p]
                    dll.restype = None
                    dll(f"새로운 업데이트 : {latest_version}\n업데이트를 위해 프로그램이 재시작됩니다.")
                    del dll
                return True, latest_release['assets'][0]['browser_download_url']
            return False, None
    except Exception as e:
        print(f"Failed to fetch latest release: {e}")
        return False, None

if __name__ == '__main__':
    check_new_release("onetwohour", "UmaKey", "0.0.0")