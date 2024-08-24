import win32gui
import win32con
import win32api
import win32com.client
import pythoncom
import numpy as np
import subprocess
import time
import os
import re
import psutil
import win32process
from threading import Thread
from modules import settingLoad
import ctypes
from ctypes import windll, cdll, c_wchar_p
user32 = windll.user32
user32.SetProcessDPIAware()

is_run = False

class WindowHandler:
    def __init__(self) -> None:
        self.hwnd = 0

    def is_window_foreground(self) -> bool:
        """
        Check if the window is in the foreground.

        :return: True if the window is in the foreground, False otherwise
        """
        return self.hwnd == win32gui.GetForegroundWindow()

    def find_process_by_name(self, process_name : str) -> None|int:
        """
        Find a process by its name.

        :param process_name: The name of the process to find
        :return: The PID of the process if found, None otherwise
        """
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'] == process_name:
                return proc.info['pid']
        return None

    def update(self) -> None:
        """
        Update the window handler.

        :return: None
        """
        self.hwnd = win32gui.FindWindow(None, settingLoad.window_title)
        if not self.hwnd:
            return
        process = self.find_process_by_name('umamusume.exe')
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

    # 화면 활성화 시 오류 발생 방지
    def activate_widnow(self) -> bool:
        """
        Activate the window.

        :return: True if the window is successfully activated, False otherwise
        """
        try:
            time.sleep(0.25)
            if win32gui.IsIconic(self.hwnd):
                win32gui.ShowWindow(self.hwnd, win32con.SW_RESTORE)
            else:
                pythoncom.CoInitialize()
                win32gui.SetForegroundWindow(self.hwnd)
                shell = win32com.client.Dispatch("WScript.Shell")
                shell.SendKeys('%')
                win32gui.SetForegroundWindow(self.hwnd)
            return True
        except:
            return False

class ColorFinder:
    def __init__(self, hwnd = 0, timer = 0) -> None:
        self.hwnd = hwnd
        self.timer = timer
        self.frequency = 0.2
        self.capture = ctypes.CDLL("./_internal/WindowCapture.dll")
        self.getpos = ctypes.CDLL("./_internal/findColor.dll")

        self.capture.CaptureAndCropScreen.argtypes = (ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte)), ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int)
        self.capture.CaptureAndCropScreen.restype = None

        self.capture.FreeImageData.argtypes = (ctypes.POINTER(ctypes.c_ubyte),)
        self.capture.FreeImageData.restype = None

        self.getpos.findTarget.argtypes = (ctypes.POINTER(ctypes.c_ubyte), ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_int), ctypes.c_int, 
                                           ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_bool))
        self.getpos.findTarget.restype = None


    def find_color(self, target_color : list[int, int, int], tolerance : float) -> tuple[None, None]|tuple[int, int]|tuple[bool, bool]:
        """
        Find a color on the screen.

        :param target_color: The target color to find
        :type target_color: list[int, int, int]
        :param tolerance: The tolerance level for color comparison
        :type tolerance: float
        :return: The coordinates of the found color if successful, or False otherwise
        :rtype: tuple[None, None] | tuple[int, int] | tuple[bool, bool]
        """

        if time.time() - self.timer < self.frequency:
            return None, None
        target_color = np.array(target_color[::-1])
        left, top, right, bottom = win32gui.GetWindowRect(self.hwnd)
        max_height = (bottom - top) // 5
        width = right - left - 40
        height = bottom - top - max_height - 20
        margin_width = width % 4
        width -= margin_width
        left += margin_width // 2

        image_data = ctypes.POINTER(ctypes.c_ubyte)()
        self.capture.CaptureAndCropScreen(ctypes.byref(image_data), left + 20, top + max_height, width, height)

        success = ctypes.c_bool(False)
        cx = ctypes.c_int()
        cy = ctypes.c_int()

        self.getpos.findTarget(image_data, width, height, target_color.ctypes.data_as(ctypes.POINTER(ctypes.c_int)),
                                tolerance, ctypes.byref(cx), ctypes.byref(cy), ctypes.byref(success))

        self.capture.FreeImageData(image_data)

        if success.value:
            return cx.value + left + 20, cy.value + top + max_height
        else:
            return False, False
        
class AutoClicker:
    def __init__(self, tolerance : float = 10) -> None:
        self.window_handler = None
        self.color_finder = None
        self.tolerance = tolerance
        self.cpp_process = None
        self.timer = 0
        self.runner = 0
        self.error = ""

    # 키보드 입력 감지 프로그램
    def open_exe(self) -> None:
        """
        Opens an external program to detect keyboard inputs.
        """
        self.cpp_process = subprocess.Popen("./_internal/input.exe", stdout=subprocess.PIPE, bufsize=1, universal_newlines=True, shell=False)
        Thread(target=self.check_screen, daemon=True).start()

    def run(self) -> None:
        """
        Runs the AutoClicker and detects keyboard events.
        """
        if not is_run or self.runner > 0:
            return
        self.timer = time.time()
        self.runner += 1

        if self.window_handler is None:
            self.window_handler = WindowHandler()

        if self.color_finder is None:
            self.color_finder = ColorFinder()

        # C++ 프로그램 실행
        if self.cpp_process is None:
            if not os.path.isfile('./_internal/input.exe'):
                raise FileNotFoundError(f"File not exist : {os.path.join(os.getcwd(), '_internal', 'input.exe')}")
            self.open_exe()

        # C++ 프로그램의 출력을 읽어 키보드 입력 추출
        while is_run:
            if not win32gui.IsWindow(self.window_handler.hwnd):
                self.window_handler.update()
                if not self.window_handler.hwnd:
                    self.destroy()
                    time.sleep(0.5)
                    continue
                elif not self.window_handler.activate_widnow():
                    continue
                Thread(target=self.screen_size_detect, daemon=True).start()

            byte_data = ""
            
            # 데이터를 읽어옴
            if self.cpp_process != None and self.window_handler.is_window_foreground():
                byte_data = self.cpp_process.stdout.readline().strip()
            if not byte_data:
                self.destroy()
                if is_run and self.window_handler.is_window_foreground():
                    self.open_exe()
                time.sleep(0.1)
                continue
            elif byte_data == "UmaKeyNotFound":
                raise ProcessLookupError(byte_data)
            
            t, text = byte_data.split(' ')
            if int(time.time() * 1000) - int(t) > 100:
                continue
            if self.on_keyboard_event(int(text)):
                time.sleep(0.1)
        self.runner -= 1

    # 처음 실행 시, 게임 창 비율을 확인
    def screen_size_detect(self) -> None:
        """
        Detects the size of the game window and verifies the aspect ratio.
        """
        delay = time.time()
        timeout = 15
        # 처음 실행 시 화면 크기가 요동치므로 무시
        while is_run and time.time() - delay < 10:
            time.sleep(0.1)
        # 5초간 화면 비율 검사
        while is_run and time.time() - delay < timeout and win32gui.IsWindow(self.window_handler.hwnd) and self.error == "":
            left, top, right, bottom = win32gui.GetWindowRect(self.window_handler.hwnd)
            # 최소화시 화면 크기가 달라짐
            if win32gui.IsIconic(self.window_handler.hwnd):
                timeout += 0.1
            elif abs(((bottom - top) / (right - left)) / (settingLoad.ratio[1] / settingLoad.ratio[0]) - 1) > 0.1:
                self.show_warning_dialog("게임 화면 비율이 다릅니다.")
                break
            time.sleep(0.1)

    def show_warning_dialog(self, message : str) -> None:
        """
        Shows a warning dialog box with the specified message.

        :param message: The message to display in the warning dialog
        :type message: str
        """
        if not os.path.isfile('./_internal/warning.dll'):
            raise FileNotFoundError(f"File not exist : {os.path.join(os.getcwd(), '_internal', 'warning.dll')}")
        dll = cdll.LoadLibrary(os.path.join(os.getcwd(), '_internal', 'warning.dll')).show_warning_dialog
        dll.argtypes = [c_wchar_p]
        dll.restype = None
        dll(message)
    
    # 게임 창이 꺼져있다면, 키보드 입력 감지 종료
    def check_screen(self) -> None:
        """
        Checks if the game window is still active and terminates keyboard event detection if not.
        """
        while is_run and self.cpp_process is not None and self.error == "":
            if not self.window_handler.is_window_foreground():
                self.destroy()
                break
            time.sleep(0.5)
    
    # 매크로 해석
    # 매크로 문자열을 분해하여 적절한 명령으로 변환
    def decode(self, text : str) -> list:
        """
        Decodes a macro string into a list of appropriate commands.

        :param text: The macro string to decode
        :type text: str
        :return: The list of decoded commands
        :rtype: list
        """
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
            elif settingLoad.key_mapping.get(token) is not None:
                keys.append(settingLoad.key_mapping[token])
            else:
                keys.append(token) 
        return keys

    # 키보드 입력시 
    def on_keyboard_event(self, byte_data : str) -> bool:
        """
        Handles keyboard events received from the external program.

        :param byte_data: The keyboard event data received
        :type byte_data: str
        :return: True if the event was handled successfully, False otherwise
        :rtype: bool
        """
        key = settingLoad.key_mapping.get(settingLoad.byte_to_key.get(byte_data))
        if key is None or not self.window_handler.is_window_foreground():
            self.keyboard(byte_data)
            return False
        if type(key) == str and settingLoad.load.get(key) is not None:
            keys = self.decode(key)  
        else:
            keys = (key,)

        for key in keys:
            self.macro(key)
        return True 
            
    def keyboard(self, code : int) -> None:
        """
        Simulates a keyboard input based on the provided code.

        :param code: The code of the keyboard input to simulate
        :type code: int
        """
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
        """
        Simulates a mouse click at the specified coordinates.

        :param x: The x-coordinate of the click
        :type x: int
        :param y: The y-coordinate of the click
        :type y: int
        """
        win32api.SetCursorPos((x, y))
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

    def drag(self, pos : str) -> None:
        """
        Simulates dragging the mouse from one position to another.

        :param pos: The positions to drag the mouse between
        :type pos: str
        """
        (x1, y1), (x2, y2) = (tuple(map(int, match)) for match in re.findall(r'\((\w+), (\w+)\)', pos))
        left, top, right, bottom = win32gui.GetWindowRect(self.window_handler.hwnd)
        
        if (x1, y1) == (-1, -1):
            x1, y1 = win32api.GetCursorPos()
            if not (left + 20 < x1 < right - 20 and top + 60 < y1 < bottom - 20):
                return
        if (x2, y2) == (-1, -1):
            x2, y2 = win32api.GetCursorPos()
            if not (left + 20 < x2 < right - 20 and top + 60 < y2 < bottom - 20):
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

        win32api.SetCursorPos((x1, y1))
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.01)
        dx, dy = (x2 - x1) / distance, (y2 - y1) / distance
        for _ in range(int(distance)):
            x1 += dx
            y1 += dy
            win32api.SetCursorPos((int(x1), int(y1)))
            time.sleep(0.015)
        win32api.SetCursorPos((x2, y2))
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

    # 적절한 기능 수행
    def macro(self, key) -> None:
        """
        Executes a macro command.

        :param key: The macro command to execute
        :type key: str
        """
        if isinstance(key, list): # 색깔
            self.color_finder.hwnd = self.window_handler.hwnd
            self.color_finder.timer = self.timer
            cx, cy = self.color_finder.find_color(key, self.tolerance)
            if cx is not None and cy is not None:
                if cx or cy:
                    self.click(cx, cy)
                self.timer = time.time()
        elif isinstance(key, tuple): # 좌표
            left, top, right, bottom = win32gui.GetWindowRect(self.window_handler.hwnd)
            if key == (-1, -1):
                x, y = win32api.GetCursorPos()
                if not (left + 20 < x < right - 20 and top + 60 < y < bottom - 20):
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
                except:
                    return
            elif settingLoad.key_to_byte.get(key) is not None: # 단순 매핑
                self.keyboard(settingLoad.key_to_byte[key]) 
        elif settingLoad.load.get(key) is not None: # 매크로 속 매크로
            for text in self.decode(key):
                self.macro(text)
        elif settingLoad.key_mapping.get(settingLoad.byte_to_key.get(key)) is not None:
            self.macro(settingLoad.key_mapping[settingLoad.byte_to_key[key]])

    def __del__(self) -> None:
        """
        Cleans up resources and terminates the AutoClicker.
        """
        global is_run
        is_run = False
        self.destroy()

    def destroy(self) -> None:
        """
        Terminates the AutoClicker and releases associated resources.
        """
        try:
            if self.cpp_process != None:
                self.cpp_process.terminate()
        except:
            pass
        self.cpp_process = None

    def toggle(self) -> None:
        """
        Toggles the AutoClicker on or off.
        """
        global is_run
        is_run = not is_run
        if is_run:
            self.error = ""
            settingLoad.load_json()
            try:
                self.run()
            except Exception as e:
                self.error = e
                self.runner -= 1
                print(e)
        else:
            self.destroy()
            try:
                del self.window_handler, self.color_finder
            except:
                pass
            self.window_handler = self.color_finder = None

if __name__ == '__main__':
    auto_clicker = AutoClicker()
    auto_clicker.toggle()
