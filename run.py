from pystray import MenuItem as item
import pystray
from PIL import Image
import main, os
from threading import Thread
import subprocess

text = 'Run'
title = 'UmaKey'

def is_process_running(process_name):
    result = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {process_name}.exe"], capture_output=True, text=True)
    output = result.stdout
    return process_name.lower() in output.lower()

def action():
    global text
    text = 'Run' if text == 'Stop' else 'Stop'
    Thread(target=auto_clicker.toggle, daemon=True).start()
    icon.update_menu()

def exit():
    global auto_clicker, icon
    auto_clicker.__del__() # 명시적 삭제
    del auto_clicker
    icon.stop()
    del icon
    os._exit(0)

if __name__ == '__main__':
    if is_process_running(title):
        os._exit(0)
    global auto_clicker, icon
    auto_clicker = main.AutoClicker()
    img = Image.open('./_internal/icon_8.jpg')
    menu = (item(lambda t : text, action), item('Exit', exit))
    icon = pystray.Icon('Umamusume with keyboard', img, title, menu)
    action()
    icon.run()