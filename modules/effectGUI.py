import tkinter as tk
import win32api

class RippleEffectManager:
    def __init__(self, canvas):
        self.canvas = canvas
        self.effects = []

    def add(self, x, y):
        effect = RippleEffect(self.canvas, x, y)
        self.effects.append(effect)
        effect.animate(self.effects, self)

    def remove(self, effect):
        if effect in self.effects:
            self.effects.remove(effect)
        if not self.effects:
            self.canvas.delete("all")
            RippleWindow.get_instance().hide()
            
class RippleEffect:
    def __init__(self, canvas, x, y):
        self.canvas = canvas
        self.radius = 0
        self.max_radius = 25
        self.ring = None
        self.x = x
        self.y = y

    def animate(self, effects, manager):
        if self.radius > self.max_radius:
            if self.ring:
                self.canvas.delete(self.ring)
            manager.remove(self)
            return

        if self.ring:
            self.canvas.delete(self.ring)

        r = int(128 + self.radius * 5)
        g = int(136 + self.radius * 3)
        b = int(255)
        r, g = min(255, r), min(255, g)
        color = f'#{r:02x}{g:02x}{b:02x}'

        width = max(1, 5 - self.radius * 0.15)

        self.ring = self.canvas.create_oval(
            self.x - self.radius, self.y - self.radius,
            self.x + self.radius, self.y + self.radius,
            outline=color,
            width=width
        )
        self.radius += 1.5
        self.canvas.after(10, lambda: self.animate(effects, manager))

class RippleWindow:
    _instance = None

    def __init__(self):
        self.root = tk.Tk()
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", "pink")
        self.root.overrideredirect(True)

        self.width = 75
        self.height = 75

        self.root.geometry(f"{self.width}x{self.height}+0+0")

        self.canvas = tk.Canvas(self.root, width=self.width, height=self.height, bg="pink", highlightthickness=0)
        self.canvas.pack()
        self.manager = RippleEffectManager(self.canvas)

    def _track_mouse(self):
        if not self.manager.effects:
            return
        x, y = win32api.GetCursorPos()
        x -= self.width // 2
        y -= self.height // 2
        self.root.geometry(f"{self.width}x{self.height}+{x}+{y}")
        self.root.after(5, self._track_mouse)

    def show(self):
        try:
            self.root.deiconify()
        except:
            return
        cx, cy = self.width // 2, self.height // 2
        self.manager.add(cx, cy)
        self._track_mouse()

    def hide(self):
        try:
            self.root.withdraw()
        except:
            pass

    def start(self):
        self.root.mainloop()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = RippleWindow()
        return cls._instance
