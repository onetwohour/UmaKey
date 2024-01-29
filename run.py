from pystray import MenuItem as item
import pystray
from PIL import Image
import main, os
from threading import Thread

text = 'Run'

def action():
    global text
    text = 'Run' if text == 'Stop' else 'Stop'
    Thread(target=auto_clicker.toggle, daemon=True).start()
    icon.update_menu()

def exit():
    global auto_clicker, icon
    del auto_clicker
    icon.stop()
    del icon
    os._exit(0)

if __name__ == '__main__':
    global auto_clicker, icon
    auto_clicker = main.AutoClicker()
    img = Image.open('icon_8.jpg')
    menu = (item(lambda t : text, action), item('Exit', exit))
    icon = pystray.Icon('Umamusume with keyboard', img, 'UmaKey', menu)
    action()
    icon.run()