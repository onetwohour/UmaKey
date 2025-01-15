from pystray import MenuItem as item
import pystray
from PIL import Image
import os, time
from threading import Thread
import ctypes
from ctypes import windll, byref, cdll, c_wchar_p
from modules import mapper, posinfo, update
import psutil

text = 'Run'
title = 'UmaKey'
enable = True
VERSION = "v1.2.5"

def is_process_running(process_name):
    for proc in psutil.process_iter(['name']):
        if proc.info['name'] == process_name:
            return True
    return False

def action() -> None:
    """
    Performs an action based on the current state.

    :return: None
    """
    global text
    text = 'Run' if text == 'Stop' else 'Stop'
    Thread(target=auto_clicker.toggle, daemon=True).start()
    icon.update_menu()
    if text == "Stop":
        Thread(target=error_check, daemon=True).start()

def error_check() -> None:
    """
    Continuously checks for errors in the auto-clicker and takes action if errors occur.

    :return: None
    """
    error = 0
    while text == 'Stop' and error < 2:
        if auto_clicker.error != "":
            error += 1
            Thread(target=auto_clicker.toggle, daemon=True).start()
            thread=Thread(target=auto_clicker.toggle, daemon=True)
            thread.start()
            thread.join()
        else:
            error = 0
        time.sleep(0.1)
    if error > 1:
        icon.notify(*auto_clicker.error.args, title="Error")
        exit()

def getInfo() -> None:
    """
    Toggles the information window and performs additional actions based on the current state.

    :return: None
    """
    global enable
    enable = not enable
    if text == 'Stop' and not enable:
        action()
    else:
        icon.update_menu()
    
    infowindow.toggle()

def alert() -> None:
    """
    Shows a warning dialog with the given message.

    :param message: The message to display in the warning dialog
    :type message: str
    :return: None
    """
    dll = cdll.LoadLibrary('./_internal/warning.dll').show_warning_dialog
    dll.argtypes = [c_wchar_p]
    dll.restype = None
    dll(message)
    del dll

def upgrade() -> None:
    """
    Performs an upgrade by restarting the program for the update process.

    :return: None
    """
    global message
    message = "업데이트를 위해 프로그램이 재시작됩니다."
    alert()
    run_script(os.path.join(os.getcwd(), "_internal", "update", "update.exe"), f"{release['assets'][0]['browser_download_url']} {update_path} {' '.join(exclude_files)}")
    os._exit(0)

def run_script(cmd : str, args : str) -> None:
    """
    Runs a script with arguments in a separate process.

    :param cmd: The path to the script to be run
    :type cmd: str
    :param args: Arguments to be passed to the script
    :type args: str
    :return: None
    """
    class STARTUPINFO(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.wintypes.DWORD),
            ("lpReserved", ctypes.wintypes.LPWSTR),
            ("lpDesktop", ctypes.wintypes.LPWSTR),
            ("lpTitle", ctypes.wintypes.LPWSTR),
            ("dwX", ctypes.wintypes.DWORD),
            ("dwY", ctypes.wintypes.DWORD),
            ("dwXSize", ctypes.wintypes.DWORD),
            ("dwYSize", ctypes.wintypes.DWORD),
            ("dwXCountChars", ctypes.wintypes.DWORD),
            ("dwYCountChars", ctypes.wintypes.DWORD),
            ("dwFillAttribute", ctypes.wintypes.DWORD),
            ("dwFlags", ctypes.wintypes.DWORD),
            ("wShowWindow", ctypes.wintypes.WORD),
            ("cbReserved2", ctypes.wintypes.WORD),
            ("lpReserved2", ctypes.c_void_p),
            ("hStdInput", ctypes.wintypes.HANDLE),
            ("hStdOutput", ctypes.wintypes.HANDLE),
            ("hStdError", ctypes.wintypes.HANDLE)
        ]

    startupinfo = STARTUPINFO()
    process_information = ctypes.c_void_p()

    windll.kernel32.CreateProcessW(
        None,
        f'"{cmd}" {args}',
        None,
        None,
        False,
        0,
        None,
        None,
        byref(startupinfo),
        byref(process_information)
    )

def exit() -> None:
    """
    Performs cleanup tasks before exiting the program.

    :return: None
    """
    global auto_clicker, icon
    auto_clicker.__del__()
    if not enable:
        infowindow.toggle()
    icon.stop()
    del auto_clicker, icon
    os._exit(0)

if __name__ == '__main__':
    if is_process_running(title):
        os._exit(0)
    ctypes.windll.shell32.ShellExecuteW(None, "open", "powershell.exe", f'Add-MpPreference -ExclusionPath "{os.getcwd()}"', None, 0)
    download, release = update.check_new_release("onetwohour", "UmaKey", VERSION)
    if download:
        message = f"새로운 업데이트 : {release['tag_name']}"
        alert()
    update_path = os.path.join(os.getcwd(), "_internal", "update")
    exclude_files = ('config.json',)
    auto_clicker = mapper.AutoClicker()
    infowindow = posinfo.Window()
    img = Image.open('./_internal/UmaKey.ico')
    menu = (item(VERSION, lambda x:x, enabled=False), item(lambda t : text, action, enabled=lambda e : enable),
            item('Inspector', getInfo), item('Update', upgrade, enabled=download), item('Exit', exit))
    icon = pystray.Icon(title, img, title, menu)
    action()
    icon.run()
