import tkinter as tk
import win32gui
from PIL import ImageGrab
from threading import Thread
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

    def setup(self) -> None:
        """
        Sets up the GUI window and initializes its components.

        :return: None
        """
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.window_handler = WindowHandler()

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
        self.x = self.root.winfo_pointerx()
        self.y = self.root.winfo_pointery()

        self.root.geometry(f"+{self.x+2}+{self.y+2}")
        self.root.after(8, self.update_position)

    def update(self) -> None:
        """
        Updates information based on the current state of the game window.

        :return: None
        """
        left, top, right, bottom = win32gui.GetWindowRect(self.window_handler.hwnd)
        game_window = right-left, bottom-top
        px, py = self.x - left, self.y - top
        px, py = max(min(px, game_window[0]), 0), max(min(py, game_window[1]), 0)
        x1, y1 = self.x - 1, self.y - 1
        x2, y2 = self.x + 1, self.y + 1
        screenshot = ImageGrab.grab(bbox=(x1, y1, x2, y2), all_screens=True)
        color = screenshot.getpixel((1, 1))
        self.text.config(text=f"{game_window[0]}x{game_window[1]}\n({px}, {py})\n{[*color]}")

    def update_text(self) -> None:
        """
        Updates the text content in the GUI periodically.

        :return: None
        """
        if not win32gui.IsWindow(self.window_handler.hwnd):
            self.window_handler.update()
            self.text.config(text="Game Closed.")
        else:
            Thread(target=self.update, daemon=True).start()

        self.text.after(500, self.update_text)

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
            self.root.destroy()
            del self.window_handler
            del self.root
        except:
            pass
        self.window_handler = self.root = None

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