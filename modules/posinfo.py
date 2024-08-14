import tkinter as tk
import win32gui
from PIL import ImageGrab
from concurrent.futures import ThreadPoolExecutor
from modules import settingLoad
from ctypes import windll
user32 = windll.user32
user32.SetProcessDPIAware()

class WindowHandler:
    def __init__(self) -> None:
        self.hwnd = 0
        self.update()
    
    def update(self) -> None:
        """
        Updates the hwnd attribute by finding the window handle.
        """
        self.hwnd = win32gui.FindWindow(None, settingLoad.window_title)

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

    def setup(self) -> None:
        """
        Sets up the GUI window and initializes its components.

        :return: None
        """
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.window_handler = WindowHandler()
        self.executor = ThreadPoolExecutor(max_workers=1)

        self.root.geometry("140x70")
        self.root.config(background="white")
        self.root.attributes('-topmost', True)

        self.text = tk.Label(self.root, text="", font=("Arial", 10), bg="white", fg="black")
        self.text.pack(fill=tk.BOTH, expand=True)

        settingLoad.load_json()

    def update_position(self) -> None:
        """
        Updates the position of the GUI window to follow the mouse cursor.

        :return: None
        """
        if not self.run:
            return
        
        try:
            self.x = self.root.winfo_pointerx()
            self.y = self.root.winfo_pointery()
        except:
            self.x, self.y = 0, 0
        
        if self.root is not None and self.run:
            self.root.geometry(f"+{self.x+2}+{self.y+2}")
            self.update_id = self.root.after(8, self.update_position)

    def update(self) -> None:
        """
        Updates information based on the current state of the game window.

        :return: None
        """
        try:
            left, top, right, bottom = win32gui.GetWindowRect(self.window_handler.hwnd)
            game_window = right-left, bottom-top
            px, py = self.x - left, self.y - top
            px, py = max(min(px, game_window[0]), 0), max(min(py, game_window[1]), 0)
            x1, y1 = self.x - 1, self.y - 1
            x2, y2 = self.x + 1, self.y + 1
            screenshot = ImageGrab.grab(bbox=(x1, y1, x2, y2), all_screens=True)
            color = screenshot.getpixel((1, 1))
            text = f"{game_window[0]}x{game_window[1]}\n({px}, {py})\n{[*color]}"
            if self.text is not None:
                self.text.config(text=text)
        except:
            pass

    def update_text(self) -> None:
        """
        Updates the text content in the GUI periodically.

        :return: None
        """
        if not self.run:
            return
        
        if not win32gui.IsWindow(self.window_handler.hwnd):
            self.window_handler.update()
            self.text.config(text="Game Closed.")
        elif self.run:
            self.executor.submit(self.update)

        if self.text is not None and self.run:
            self.update_text_id = self.root.after(500, self.update_text)

    def main(self) -> None:
        """
        Starts the main event loop of the GUI application.
        
        :return: None
        """
        self.setup()
        self.update_position()
        self.update_text()

        self.root.mainloop()
    
    def exit(self) -> None:
        """
        Destroys the root window and cleans up resources associated with it.
        
        :return: None
        """
        try:
            self.executor.shutdown(wait=False, cancel_futures=True)
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
        """
        Toggles the state of a class attribute 'run' between True and False,
        and calls either the 'main' method or the 'exit' method accordingly.
        
        :return: None
        """
        self.run = not self.run

        if self.run:
            self.main()
        else:
            self.exit()

if __name__ == '__main__':
    window = Window()
    window.toggle()