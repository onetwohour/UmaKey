from pystray import MenuItem as item
import pystray
from PIL import Image
import os, time
from threading import Thread
import subprocess
import ctypes
from ctypes import windll, byref
from modules import mapper, posinfo, update

text = 'Run'
title = 'UmaKey'
enable = True
VERSION = "v0.0.52"

for file in ['input.exe', 'ghost.ico', 'warning.dll']:
    if not os.path.isfile(f'./_internal/{file}'):
        raise FileNotFoundError(f"File not exist : {os.path.join(os.getcwd(), '_internal', file)}")

def is_process_running(process_name):
    result = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {process_name}.exe"], capture_output=True, text=True)
    output = result.stdout
    return output.lower().count(process_name.lower()) > 1

def action():
    global text
    text = 'Run' if text == 'Stop' else 'Stop'
    Thread(target=auto_clicker.toggle, daemon=True).start()
    icon.update_menu()
    Thread(target=error_check, daemon=True).start()

def error_check():
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

def getInfo():
    global enable
    enable = not enable
    if text == 'Stop' and not enable:
        action()
    else:
        icon.update_menu()
    
    posinfo.toggle()

def run_script(cmd, args):
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

def exit():
    global auto_clicker, icon
    auto_clicker.__del__()
    if not enable:
        posinfo.toggle()
    icon.stop()
    del auto_clicker, icon
    os._exit(0)

if __name__ == '__main__':
    if is_process_running(title):
        os._exit(0)
    download, url = update.check_new_release("onetwohour", "UmaKey", VERSION)
    exclude_files = ['config.json', 'update.exe']
    if download:
        run_script("update.exe", f"{url} {' '.join(exclude_files)}")
        os._exit(0)
    global auto_clicker, icon
    auto_clicker = mapper.AutoClicker()
    img = Image.open('./_internal/ghost.ico')
    menu = (item(lambda t : text, action, enabled=lambda e : enable), item('Inspector', getInfo), item('Exit', exit))
    icon = pystray.Icon(title, img, title, menu)
    action()
    icon.run()
