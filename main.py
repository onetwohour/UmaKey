from pystray import MenuItem as item
import pystray
from PIL import Image
import os, time
from threading import Thread
import subprocess
from modules import mapper, posinfo

text = 'Run'
title = 'UmaKey'
enable = True

for file in ['input.exe', 'icon_8.jpg']:
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
    global auto_clicker, icon
    auto_clicker = mapper.AutoClicker()
    img = Image.open('./_internal/icon_8.jpg')
    menu = (item(lambda t : text, action, enabled=lambda e : enable), item('Inspector', getInfo), item('Exit', exit))
    icon = pystray.Icon(title, img, title, menu)
    action()
    icon.run()
