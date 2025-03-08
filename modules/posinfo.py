import tkinter as tk
import win32gui
from PIL import ImageGrab
from threading import Thread
from threading import Event
from modules import settingLoad
from ctypes import windll
user32 = windll.user32
user32.SetProcessDPIAware()

class WindowHandler:
    def __init__(self) -> None:
        self.hwnd = 0
        self.update()
    
    def update(self) -> None:
        self.hwnd = win32gui.FindWindow(None, settingLoad.window_title)

    def get_window_position(self):
        left, top, right, bottom = win32gui.GetClientRect(self.hwnd)
        width, height = right - left, bottom - top
        left, top = map(sum, zip((left, top), win32gui.ClientToScreen(self.hwnd, (0, 0))))
        return left, top, left + width, top + height
    
class Window():
    def __init__(self) -> None:
        self.root = None
        self.window_handler = None
        self.run = False
        self.update_id = None
        self.update_text_id = None
        self.x = 0
        self.y = 0
        self.executor = None
        self.event = Event()

    def setup(self) -> None:
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.window_handler = WindowHandler()

        self.root.geometry("140x70")
        self.root.config(background="white")
        self.root.attributes('-topmost', True)

        self.text = tk.Label(self.root, text="", font=("Arial", 10), bg="white", fg="black")
        self.text.pack(fill=tk.BOTH, expand=True)

        settingLoad.load_json()

        self.event.clear()

    def update_position(self) -> None:
        if not self.run:
            return
        
        try:
            self.x = self.root.winfo_pointerx()
            self.y = self.root.winfo_pointery()
        except Exception:
            self.x, self.y = 0, 0
        
        if self.root is not None and self.run:
            self.root.geometry(f"+{self.x+2}+{self.y+2}")
            self.update_id = self.root.after(8, self.update_position)

    def update(self) -> None:
        def work():
            try:
                left, top, right, bottom = self.window_handler.get_window_position()
                game_window = right-left, bottom-top
                px, py = self.x - left, self.y - top
                px, py = max(min(px, game_window[0]), 0), max(min(py, game_window[1]), 0)
                x1, y1 = self.x - 1, self.y - 1
                x2, y2 = self.x + 1, self.y + 1
                screenshot = ImageGrab.grab(bbox=(x1, y1, x2, y2), all_screens=True)
                color = screenshot.getpixel((1, 1))
                text = f"{game_window[0]}x{game_window[1]}\n({px}, {py})\n{[*color]}"
                if self.text is not None and self.run:
                    self.text.config(text=text)
            except Exception:
                pass
        
        work()
        self.event.clear()

    def update_text(self) -> None:
        if not self.run:
            return
        
        if not win32gui.IsWindow(self.window_handler.hwnd):
            self.window_handler.update()
            self.text.config(text="Game Closed.")
        elif self.run and not self.event.is_set():
            self.event.set()
            Thread(target=self.update).run()

        if self.text is not None and self.run:
            self.update_text_id = self.root.after(500, self.update_text)

    def main(self) -> None:
        self.setup()
        self.update_position()
        self.update_text()

        self.root.mainloop()
    
    def exit(self) -> None:
        try:
            while self.event.is_set():
                pass
            self.event.set()

            if self.update_id is not None:
                self.root.after_cancel(self.update_id)
                self.update_id = None
            if self.update_text_id is not None:
                self.root.after_cancel(self.update_text_id)
                self.update_text_id = None
            self.root.destroy()
        finally:
            self.window_handler = None
            self.root = None
            self.text = None
            self.executor = None

    def toggle(self) -> None:
        self.run = not self.run
        self.main() if self.run else self.exit()

if __name__ == '__main__':
    window = Window()
    window.toggle()