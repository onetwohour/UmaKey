import urllib.request
import json

def check_new_release(repo_owner : str, repo_name : str, current_version : str) -> tuple[bool, str|None]:
    """
    Check the latest release of a given GitHub repository.

    :param repo_owner: GitHub username of the repository owner
    :type repo_owner: str
    :param repo_name: Name of the repository to check
    :type repo_name: str
    :param current_version: Current version in use
    :type current_version: str
    :return: Tuple indicating whether the latest release differs from the current version and the latest release info (if different)
    :rtype: tuple[bool, str|None]
    """
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