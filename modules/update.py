import urllib.request
import json

def check_new_release(repo_owner, repo_name, current_version):
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases/latest"
    try:
        with urllib.request.urlopen(url) as response:
            latest_release = json.loads(response.read())
            latest_version = latest_release['tag_name']
            if latest_version != current_version:
                return True, latest_release
            return False, None
    except Exception as e:
        print(f"Failed to fetch latest release: {e}")
        return False, None

if __name__ == '__main__':
    check_new_release("onetwohour", "UmaKey", "0.0.0")