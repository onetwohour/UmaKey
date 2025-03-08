from pystray import MenuItem as item
import pystray
from PIL import Image
import os
import time
from threading import Thread
import ctypes
from ctypes import windll, byref
from modules import mapper, posinfo, update
import psutil
import tkinter as tk
from tkinter import messagebox

text = 'Run'
title = 'UmaKey'
enable = True
VERSION = "v1.2.6"

def is_process_running(process_name):
    for proc in psutil.process_iter(['name']):
        if proc.info['name'] == process_name:
            return True
    return False

def action() -> None:
    global text
    text = 'Run' if text == 'Stop' else 'Stop'
    Thread(target=auto_clicker.toggle, daemon=True).start()
    icon.update_menu()
    if text == "Stop":
        Thread(target=error_check, daemon=True).start()

def error_check() -> None:
    error = False
    while text == 'Stop' and not error:
        if auto_clicker.error_occurred():
            error = True
        time.sleep(0.1)
    if error:
        icon.notify(*auto_clicker.error.args, title="Error")
        exit()

def getInfo() -> None:
    global enable
    enable = not enable
    if text == 'Stop' and not enable:
        action()
    else:
        icon.update_menu()
    
    infowindow.toggle()

def alert(title="Warning", message="") -> None:
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    messagebox.showwarning(title, message)
    root.destroy()

def upgrade() -> None:
    message = "업데이트를 위해 프로그램이 재시작됩니다."
    alert(message=message)
    run_script(os.path.join(update_path, "update.exe"), f"{release['assets'][0]['browser_download_url']} {update_path} {' '.join(exclude_files)}")
    os._exit(0)

def run_script(cmd : str, args : str) -> None:
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
        alert("알림", f"새로운 업데이트 : {release['tag_name']}")
    update_path = os.path.join(os.getcwd(), "update")
    exclude_files = ('config.json',)
    auto_clicker = mapper.AutoClicker()
    infowindow = posinfo.Window()
    img = Image.open('./_internal/UmaKey.ico')
    menu = (item(VERSION, lambda x:x, enabled=False), item(lambda t : text, action, enabled=lambda e : enable),
            item('Inspector', getInfo), item('Update', upgrade, enabled=download), item('Exit', exit))
    icon = pystray.Icon(title, img, title, menu)
    action()
    icon.run()
