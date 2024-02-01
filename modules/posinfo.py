import tkinter as tk
import win32gui
from PIL import ImageGrab
from threading import Thread
from ctypes import windll
user32 = windll.user32
user32.SetProcessDPIAware()

window_title = 'umamusume'
run = False

class WindowHandler:
    def __init__(self):
        self.hwnd = 0
        self.update()
    
    def update(self):
        self.hwnd = win32gui.FindWindow(None, window_title)


def update_position():
    global x, y
    x = root.winfo_pointerx()
    y = root.winfo_pointery()

    root.geometry(f"+{x+2}+{y+2}")
    root.after(8, update_position)

def update(text):
    left, top, right, bottom = win32gui.GetWindowRect(window_handler.hwnd)
    game_window = right-left, bottom-top
    px, py = x - left, y - top
    px, py = max(min(px, game_window[0]), 0), max(min(py, game_window[1]), 0)
    x1, y1 = x - 1, y - 1
    x2, y2 = x + 1, y + 1
    screenshot = ImageGrab.grab(bbox=(x1, y1, x2, y2), all_screens=True)
    color = screenshot.getpixel((1, 1))
    text.config(text=f"{game_window[0]}x{game_window[1]}\n({px}, {py})\n{[*color]}")

def update_text(text):
    if not win32gui.IsWindow(window_handler.hwnd):
        window_handler.update()
        text.config(text="Game Closed.")
    else:
        Thread(target=update, args=(text,), daemon=True).start()

    text.after(500, update_text, text)

def main():
    global root, window_handler
    root = tk.Tk()
    root.overrideredirect(True)
    window_handler = WindowHandler()

    root.geometry("140x70")
    root.config(background="white")
    root.attributes('-topmost', True)

    text = tk.Label(root, text="", font=("Arial", 10), bg="white", fg="black")
    text.pack(fill=tk.BOTH, expand=True)

    update_position()
    update_text(text)

    root.mainloop()

def toggle():
    global run, root, window_handler
    run = not run

    if run:
        main()
    else:
        root.destroy()
        del root, window_handler

if __name__ == '__main__':
    main()