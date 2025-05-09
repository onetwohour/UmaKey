from dataclasses import dataclass
import tkinter as tk
from tkinter import messagebox
import win32gui
import win32con
import win32api
import win32ui
import win32com.client
import pythoncom
import numpy as np
import time
import re
import psutil
import win32process
import cv2
from .effectGUI import RippleWindow
from threading import Thread
from modules import settingLoad
import ctypes
from ctypes import windll
import ctypes.wintypes
user32 = windll.user32
user32.SetProcessDPIAware()
kernel32 = windll.kernel32

HOOKPROC = ctypes.WINFUNCTYPE(ctypes.wintypes.LPARAM, ctypes.c_int, ctypes.wintypes.WPARAM, ctypes.POINTER(ctypes.wintypes.LPARAM))

TARGET_PROCESS = 'umamusume.exe'

@dataclass
class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", ctypes.wintypes.DWORD),
        ("scanCode", ctypes.wintypes.DWORD),
        ("flags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.wintypes.ULONG)
    ]

class WindowHandler:
    def __init__(self) -> None:
        self.hwnd = 0

    def is_window_foreground(self) -> bool:
        return self.hwnd == win32gui.GetForegroundWindow()

    def find_process_by_name(self, process_name : str) -> None|int:
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'] == process_name:
                return proc.info['pid']
        return None

    def update(self) -> None:
        self.hwnd = win32gui.FindWindow(None, settingLoad.window_title)
        if not self.hwnd:
            return
        process = self.find_process_by_name(TARGET_PROCESS)
        if process is None:
            self.hwnd = 0
            return

        if win32process.GetWindowThreadProcessId(self.hwnd)[0] == process:
            return

        def callback(hwnd : int, _) -> None:
            if win32gui.IsWindowVisible(hwnd) and settingLoad.window_title == win32gui.GetWindowText(hwnd):
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                if pid == process:
                    self.hwnd = hwnd
                    return
        win32gui.EnumWindows(callback, None)

    def activate_window(self) -> bool:
        try:
            time.sleep(0.25)
            if win32gui.IsIconic(self.hwnd):
                win32gui.ShowWindow(self.hwnd, win32con.SW_RESTORE)
            else:
                pythoncom.CoInitialize()
                shell = win32com.client.Dispatch("WScript.Shell")
                shell.SendKeys('%')
                win32gui.SetForegroundWindow(self.hwnd)
            return True
        except Exception:
            return False
        
    def get_window_position(self) -> tuple[int, int, int, int]:
        left, top, right, bottom = win32gui.GetClientRect(self.hwnd)
        width, height = right - left, bottom - top
        left, top = map(sum, zip((left, top), win32gui.ClientToScreen(self.hwnd, (0, 0))))
        return left, top, left + width, top + height

class ColorFinder:
    def __init__(self, hwnd=0) -> None:
        self.hwnd = hwnd

    def capture_screen(self):
        left, top, right, bottom = win32gui.GetClientRect(self.hwnd)
        width, height = right - left, bottom - top
        max_height = height // 5
        offset = 20

        hwindc = win32gui.GetWindowDC(self.hwnd)
        srcdc = win32ui.CreateDCFromHandle(hwindc)
        memdc = srcdc.CreateCompatibleDC()
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(srcdc, width, height)
        memdc.SelectObject(bitmap)
        user32.PrintWindow(self.hwnd, memdc.GetSafeHdc(), 3)

        bmpinfo = bitmap.GetInfo()
        bmpstr = bitmap.GetBitmapBits(True)
        img = np.frombuffer(bmpstr, dtype=np.uint8)
        img.shape = (bmpinfo['bmHeight'], bmpinfo['bmWidth'], 4)
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)
        cropped_img = img[max_height:, offset:width-offset]

        srcdc.DeleteDC()
        memdc.DeleteDC()
        win32gui.ReleaseDC(self.hwnd, hwindc)
        win32gui.DeleteObject(bitmap.GetHandle())

        return cropped_img, max_height, offset

    def find_color(self, target_color: list[int, int, int], tolerance: int) -> tuple[None, None] | tuple[int, int] | tuple[bool, bool]:
        image, offset_h, offset_w = self.capture_screen()
        left, top = win32gui.ClientToScreen(self.hwnd, (0, 0))
        left += offset_w
        top += offset_h

        lower_bound = np.array([max(0, c - tolerance) for c in target_color], dtype=np.uint8)
        upper_bound = np.array([min(255, c + tolerance) for c in target_color], dtype=np.uint8)

        mask = cv2.inRange(image, lower_bound, upper_bound)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return False, False

        largest_contour = max(contours, key=cv2.contourArea)
        M = cv2.moments(largest_contour)
        if M["m00"] == 0:
            return False, False

        cx = int(M["m10"] / M["m00"]) + left
        cy = int(M["m01"] / M["m00"]) + top

        return cx, cy

class KeyboardHook:
    def __init__(self, callback=None):
        self.hooked = None
        self.hook_thread = None
        self.callback = callback
        self.running = False
        self.WH_KEYBOARD_LL = 13
        self.WM_KEYDOWN = 0x0100
        self.WM_KEYUP = 0x0101
        self.HOOKPROC = HOOKPROC(self._keyboard_proc)
        self.lock = False
        self.task = None

    def _keyboard_proc(self, nCode, wParam, lParam):
        if nCode >= 0:
            if wParam == self.WM_KEYDOWN:
                key_info = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                vk_code = key_info.vkCode
                extra_info = key_info.dwExtraInfo
                
                if self.callback and extra_info == 0:
                    if not self.lock:
                        self.lock = True
                        self.task = Thread(target=self.callback, args=(vk_code,), daemon=True)
                        self.task.start()
                    return 1
        
        return user32.CallNextHookEx(self.hooked, nCode, wParam, lParam)

    def start(self):
        if self.hooked:
            return

        self.running = True
        self.hook_thread = Thread(target=self._hook_loop, daemon=True)
        self.hook_thread.start()

    def _hook_loop(self):
        hMod = None
        
        self.hooked = user32.SetWindowsHookExW(
            self.WH_KEYBOARD_LL, self.HOOKPROC,
            hMod, 0
        )

        if not self.hooked:
            print(f"SetWindowsHookExW 실패: {ctypes.GetLastError()}")
            return
        
        self._message_loop()

    def _message_loop(self):
        msg = ctypes.wintypes.MSG()

        while self.running:
            if user32.PeekMessageW(ctypes.byref(msg), 0, 0, 0, 1):
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))

            time.sleep(0.01)

    def stop(self):
        if self.hooked:
            user32.UnhookWindowsHookEx(self.hooked)
            self.hooked = None
        self.running = False

    def register_callback(self, func=None):
        def wrapper(*args):
            func(*args)
            self.lock = False
        self.callback = wrapper if func is not None else func

class AutoClicker:
    def __init__(self, tolerance : float = 10) -> None:
        self.window_handler = WindowHandler()
        self.color_finder = ColorFinder()
        self.tolerance = tolerance
        self.key_mapping_index = 0
        self.key_mapping = None
        self.__state = 0
        self.thread = None
        self.keyboard_hook = KeyboardHook()
        self.error = None
        Thread(target=lambda: RippleWindow.get_instance().start(), daemon=True).start()

    @staticmethod
    def exception_handler(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                instance = args[0]
                if isinstance(instance, AutoClicker):
                    instance.destroy()
                    instance.__state = -1
                    instance.error = e
                return None
        return wrapper

    def is_run(self):
        return self.__state > 0

    @exception_handler
    def run(self) -> None:
        if self.is_run():
            return
        self.__state = 1
        
        self.keyboard_hook.start()

        self.thread = Thread(target=self.monitor)
        self.thread.start()

    def disable(self):
        self.keyboard_hook.register_callback(None)

    def enable(self):
        self.keyboard_hook.register_callback(self.on_keyboard_event)

    @exception_handler
    def monitor(self):
        while self.is_run():
            if not self.window_handler.hwnd or not win32gui.IsWindow(self.window_handler.hwnd):
                self.disable()
                time.sleep(0.5)
                self.window_handler.update()
                continue

            if self.__state == 1:
                if not self.window_handler.activate_window():
                    self.disable()
                    time.sleep(0.5)
                    continue
                Thread(target=self.screen_size_detect, daemon=True).start()
                self.enable()
                self.__state = 2

            elif self.__state == 2:
                if not self.window_handler.is_window_foreground():
                    self.disable()
                else:
                    self.enable()
                time.sleep(0.5)
                
    @exception_handler
    def screen_size_detect(self) -> None:
        delay = time.time()
        timeout = 15
        while self.is_run() and time.time() - delay < 10:
            time.sleep(0.1)
        
        while self.is_run() and time.time() - delay < timeout and win32gui.IsWindow(self.window_handler.hwnd) and self.error is None:
            left, top, right, bottom = self.window_handler.get_window_position()
            if win32gui.IsIconic(self.window_handler.hwnd):
                timeout += 0.1
            elif abs(((bottom - top) / (right - left)) / (settingLoad.ratio[1] / settingLoad.ratio[0]) - 1) > 0.1:
                self.show_warning_dialog("게임 화면 비율이 다릅니다.")
                break
            time.sleep(0.1)

    def show_warning_dialog(self, message : str) -> None:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        messagebox.showwarning("Warning", message)
        root.destroy()

    def ring_effect(self):
        RippleWindow.get_instance().show()

    def decode(self, text : str) -> list:
        keys = []
        tokens = re.findall(r'\[.*?\]|\(.*?\)|\d+|\b\w+\s[\d.]+\b|\w+', settingLoad.load[text])
        for token in tokens:
            if token.startswith('('):
                if len(keys) > 0 and str(keys[-1]).startswith('drag') and keys[-1].count('(') < 2:
                    keys[-1] += ' ' + str(tuple(map(int, token[1:-1].split(','))))
                else:
                    keys.append(tuple(map(int, token[1:-1].split(','))))
            elif token.startswith('['):
                keys.append([int(x) for x in token[1:-1].split(',')])
            elif token.isdigit():
                keys.append(settingLoad.key_to_byte[token])
            elif re.match(r'\b\w+\s[\d.]+\b', token):
                keys.append(token)
            elif settingLoad.key_mapping[self.key_mapping].get(token) is not None:
                keys.append(settingLoad.key_mapping[self.key_mapping][token])
            else:
                keys.append(token) 
        return keys

    @exception_handler
    def on_keyboard_event(self, vk: int) -> bool:
        key = settingLoad.byte_to_key.get(vk)
        if key == settingLoad.key_mapping.get("switch"):
            key = "switch"
        else:
            key = settingLoad.key_mapping[self.key_mapping].get(key)
        if key is None or not self.window_handler.is_window_foreground():
            self.press_key(vk)
            return False
        if isinstance(key, str) and settingLoad.load.get(key) is not None:
            keys = self.decode(key)  
        else:
            keys = (key,)

        for key in keys:
            self.macro(key)
        return True 
            
    def press_key(self, code : int) -> None:
        control_pressed = win32api.GetKeyState(win32con.VK_CONTROL) < 0
        shift_pressed = win32api.GetKeyState(win32con.VK_SHIFT) < 0
        if control_pressed:
            win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_EXTENDEDKEY, 3000)
        if shift_pressed:
            win32api.keybd_event(win32con.VK_SHIFT, 0, win32con.KEYEVENTF_EXTENDEDKEY, 3000)
        win32api.keybd_event(code, 0, 0, 3000)
        if control_pressed:
            win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_EXTENDEDKEY | win32con.KEYEVENTF_KEYUP, 3000)
        if shift_pressed:
            win32api.keybd_event(win32con.VK_SHIFT, 0, win32con.KEYEVENTF_EXTENDEDKEY | win32con.KEYEVENTF_KEYUP, 3000)

    def click(self, x : int, y : int) -> None:
        ctypes.windll.user32.SetCursorPos(x, y)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

    def drag(self, pos : str) -> None:
        (x1, y1), (x2, y2) = (tuple(map(int, match)) for match in re.findall(r'\((\w+), (\w+)\)', pos))
        left, top, right, bottom = self.window_handler.get_window_position()
        
        if (x1, y1) == (-1, -1):
            x1, y1 = win32api.GetCursorPos()
            if not (left + 20 <= x1 <= right - 20 and top + 60 <= y1 <= bottom - 20):
                return
        if (x2, y2) == (-1, -1):
            x2, y2 = win32api.GetCursorPos()
            if not (left + 20 <= x2 <= right - 20 and top + 60 <= y2 <= bottom - 20):
                return

        width = right - left
        height = bottom - top

        x1 = int(x1 * (width / settingLoad.ratio[0]) + left)
        y1 = int(y1 * (height / settingLoad.ratio[1]) + top)
        x2 = int(x2 * (width / settingLoad.ratio[0]) + left)
        y2 = int(y2 * (height / settingLoad.ratio[1]) + top)
        left, top, right, bottom = left + 20, top + 60, right - 20, bottom - 20

        x1, y1 = max(left, min(x1, right)), max(top, min(y1, bottom))
        x2, y2 = max(left, min(x2, right)), max(top, min(y2, bottom))
        distance = min(max(abs(x1 - x2) / 20, abs(y1 - y2) / 20, 1), 40)
        
        if (x1, y1) == (x2, y2):
            self.click(x1, y1)
            return

        ctypes.windll.user32.SetCursorPos(x1, y1)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.01)
        dx, dy = (x2 - x1) / distance, (y2 - y1) / distance
        for _ in range(int(distance)):
            x1 += dx
            y1 += dy
            ctypes.windll.user32.SetCursorPos(int(x1), int(y1))
            time.sleep(0.015)
        ctypes.windll.user32.SetCursorPos(x2, y2)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

    def macro(self, key) -> None:
        if isinstance(key, list): # 색깔
            self.color_finder.hwnd = self.window_handler.hwnd
            cx, cy = self.color_finder.find_color(key, self.tolerance)
            if cx is not None and cy is not None:
                if cx or cy:
                    self.click(cx, cy)
        elif isinstance(key, tuple): # 좌표
            left, top, right, bottom = self.window_handler.get_window_position()
            if key == (-1, -1):
                x, y = win32api.GetCursorPos()
                if not (left + 20 <= x <= right - 20 and top + 60 <= y <= bottom - 20):
                    return
            else:
                x, y = int(key[0] * (right - left) / settingLoad.ratio[0] + left), int(key[1] * (bottom - top) / settingLoad.ratio[1] + top)
                left, top, right, bottom = left + 20, top + 60, right - 20, bottom - 20
                x, y = max(left, min(x, right)), max(top, min(y, bottom))
            self.click(x, y)
        elif isinstance(key, str):
            if key.startswith(('sleep', 'drag')):
                command, value = key.split(maxsplit=1)
                try:
                    if command == 'sleep': # 딜레이
                        time.sleep(float(value))
                    elif command == 'drag':
                        self.drag(value)
                except Exception:
                    return
            elif key == 'switch': # 프리셋 변환
                self.key_mapping_index = (self.key_mapping_index + 1) % len(settingLoad.key_mapping.keys())
                self.key_mapping = list(settingLoad.key_mapping.keys())[self.key_mapping_index]
                self.ring_effect()
                if self.key_mapping == 'switch':
                    self.key_mapping_index = (self.key_mapping_index + 1) % len(settingLoad.key_mapping.keys())
                    self.key_mapping = list(settingLoad.key_mapping.keys())[self.key_mapping_index]
            elif settingLoad.key_to_byte.get(key) is not None: # 단순 매핑
                self.keyboard(settingLoad.key_to_byte[key]) 
        elif settingLoad.load.get(key) is not None: # 이중 매크로
            for text in self.decode(key):
                self.macro(text)
        elif settingLoad.key_mapping[self.key_mapping].get(settingLoad.byte_to_key.get(key)) is not None:
            self.macro(settingLoad.key_mapping[self.key_mapping][settingLoad.byte_to_key[key]])

    def __del__(self) -> None:
        self.destroy()

    def destroy(self) -> None:
        try:
            self.__state = 0
            self.keyboard_hook.stop()
        except Exception:
            pass
    
    @exception_handler
    def toggle(self) -> None:
        if not self.is_run():
            settingLoad.load_json()
            self.key_mapping = list(settingLoad.key_mapping.keys())[self.key_mapping_index]
            self.run()
        else:
            self.destroy()

    def error_occurred(self):
        return self.__state == -1

if __name__ == '__main__':
    auto_clicker = AutoClicker()
    auto_clicker.toggle()
