import win32gui
import win32con
import win32api
import win32com.client
import pythoncom
import numpy as np
import subprocess
import time
import os
import json
import re
import psutil
import win32process
from threading import Thread
import ctypes
from ctypes import windll, cdll, c_wchar_p
user32 = windll.user32
user32.SetProcessDPIAware()
os.path

is_run = False

# 특정 프로그램의 창 제목과 키와 색상 매핑 설정
window_title = "umamusume"
key_mapping = {}
ratio = 0, 0

# ASCII 문자에 해당하는 바이트 값을 키로 가지는 딕셔너리
byte_to_key = {
    win32con.VK_BACK: "BACKSPACE", win32con.VK_TAB: "TAB", win32con.VK_CLEAR: "CLEAR",
    win32con.VK_RETURN: "ENTER", win32con.VK_SHIFT: "SHIFT", win32con.VK_CONTROL: "CTRL",
    win32con.VK_MENU: "ALT", win32con.VK_PAUSE: "PAUSE", win32con.VK_CAPITAL: "CAPS_LOCK",
    win32con.VK_ESCAPE: "ESC", win32con.VK_SPACE: "SPACEBAR", win32con.VK_PRIOR: "PAGE_UP",
    win32con.VK_NEXT: "PAGE_DOWN", win32con.VK_END: "END", win32con.VK_HOME: "HOME",
    win32con.VK_LEFT: "LEFT_ARROW", win32con.VK_UP: "UP_ARROW", win32con.VK_RIGHT: "RIGHT_ARROW",
    win32con.VK_DOWN: "DOWN_ARROW", win32con.VK_SNAPSHOT: "PRINT_SCREEN", win32con.VK_INSERT: "INSERT",
    win32con.VK_DELETE: "DELETE", win32con.VK_NUMPAD0: "NUMPAD_0", win32con.VK_NUMPAD1: "NUMPAD_1",
    win32con.VK_NUMPAD2: "NUMPAD_2", win32con.VK_NUMPAD3: "NUMPAD_3", win32con.VK_NUMPAD4: "NUMPAD_4",
    win32con.VK_NUMPAD5: "NUMPAD_5", win32con.VK_NUMPAD6: "NUMPAD_6", win32con.VK_NUMPAD7: "NUMPAD_7",
    win32con.VK_NUMPAD8: "NUMPAD_8", win32con.VK_NUMPAD9: "NUMPAD_9", 48: "0", 49: "1", 50: "2",
    51: "3", 52: "4", 53: "5", 54: "6", 55: "7", 56: "8", 57: "9", ord('A'): "A", ord('B'): "B",
    ord('C'): "C", ord('D'): "D", ord('E'): "E", ord('F'): "F", ord('G'): "G", ord('H'): "H",
    ord('I'): "I", ord('J'): "J", ord('K'): "K", ord('L'): "L", ord('M'): "M", ord('N'): "N",
    ord('O'): "O", ord('P'): "P", ord('Q'): "Q", ord('R'): "R", ord('S'): "S", ord('T'): "T",
    ord('U'): "U", ord('V'): "V", ord('W'): "W", ord('X'): "X", ord('Y'): "Y", ord('Z'): "Z",
    win32con.VK_LWIN: "LEFT_WINDOWS", win32con.VK_RWIN: "RIGHT_WINDOWS", win32con.VK_APPS: "CONTEXT_MENU",
    win32con.VK_MULTIPLY: "MULTIPLY", win32con.VK_ADD: "ADD", win32con.VK_SEPARATOR: "SEPARATOR",
    win32con.VK_SUBTRACT: "SUBTRACT", win32con.VK_DECIMAL: "DECIMAL", win32con.VK_DIVIDE: "DIVIDE",
    win32con.VK_F1: "F1", win32con.VK_F2: "F2", win32con.VK_F3: "F3", win32con.VK_F4: "F4",
    win32con.VK_F5: "F5", win32con.VK_F6: "F6", win32con.VK_F7: "F7", win32con.VK_F8: "F8",
    win32con.VK_F9: "F9", win32con.VK_F10: "F10", win32con.VK_F11: "F11", win32con.VK_F12: "F12",
    win32con.VK_F13: "F13", win32con.VK_F14: "F14", win32con.VK_F15: "F15", win32con.VK_F16: "F16",
    win32con.VK_F17: "F17", win32con.VK_F18: "F18", win32con.VK_F19: "F19", win32con.VK_F20: "F20",
    win32con.VK_F21: "F21", win32con.VK_F22: "F22", win32con.VK_F23: "F23", win32con.VK_F24: "F24",
    win32con.VK_NUMLOCK: "NUM_LOCK", win32con.VK_SCROLL: "SCROLL_LOCK", win32con.VK_LSHIFT: "LEFT_SHIFT",
    win32con.VK_RSHIFT: "RIGHT_SHIFT", win32con.VK_LCONTROL: "LEFT_CTRL", win32con.VK_RCONTROL: "RIGHT_CTRL",
    win32con.VK_LMENU: "LEFT_MENU", win32con.VK_RMENU: "RIGHT_MENU", 186: ";",
    107: "+", 188: ",", 109: "-", 190: ".", 191: "/", 192: "`",
    219: "[", 220: "\\", 221: "]", 222: "'"
}

key_to_byte = {v: k for k, v in byte_to_key.items()}

def convert_value(value_str : str):
    """
    Converts a string representation of a value to its corresponding Python data type.

    :param value_str: The string representation of the value
    :type value_str: str
    :return: The converted value
    """
    split = value_str[1:-1].split(',')
    # 리스트 형태인 경우
    if value_str.startswith("[") and value_str.endswith("]") and len(split) == 3:
        return [int(x) for x in split]
    # 튜플 형태인 경우
    elif value_str.startswith("(") and value_str.endswith(")") and len(split) == 2:
        return tuple(int(x) for x in split)
    # 키 형태인 경우
    elif key_to_byte.get(value_str) != None:
        return key_to_byte[value_str]
    else:
        return value_str

def load_json() -> None:
    """
    Loads settings from the config file and initializes global variables.

    :return: None
    """
    global key_mapping, ratio, load, window_title
    key_mapping = {
        'SPACEBAR': [99,182,0],        # 초록버튼
        '`':     [231, 231, 236],   # 흰 버튼
        'Q':     [124, 203, 42],    # 휴식
        'W':     [41, 122, 207],    # 트레이닝
        'E':     [40, 191, 214],    # 스킬
        'R':     [247, 154, 8],     # 외출
        'F':     [145, 96, 239],    # 양호실
        'T':     [217, 81, 242],    # 레슨
        'G':     [244, 69, 137],    # 레이스
        'NUMPAD_0':   'MAC',        # 훈련 돌아보기 1
        'A':    [225, 255, 178],    # 1번 선택지
        'S':    [255, 247, 192],    # 2번 선택지
        'D':    [255, 228, 239],    # 3번 선택지
        '/':    (730, 1330),
        "TAB": "drag (20, 1230) (788, 1230)" # 훈련 돌아보기 2
    }

    screen_size = {
        'x': 808,
        'y': 1453
    }

    support_key = ["BACKSPACE, TAB, CLEAR, ENTER, SHIFT, CTRL, PAUSE, CAPS_LOCK, ESC, SPACEBAR, PAGE_UP, PAGE_DOWN, ",
                "END, HOME, LEFT_ARROW, UP_ARROW, RIGHT_ARROW, DOWN_ARROW, PRINT_SCREEN, INSERT, DELETE, NUMPAD_0, ",
                "NUMPAD_1, NUMPAD_2, NUMPAD_3, NUMPAD_4, NUMPAD_5, NUMPAD_6, NUMPAD_7, NUMPAD_8, NUMPAD_9, 0, 1, 2, ",
                "3, 4, 5, 6, 7, 8, 9, A, B, C, D, E, F, G, H, I, J, K, L, M, N, O, P, Q, R, S, T, U, V, W, X, Y, Z, ",
                "LEFT_WINDOWS, RIGHT_WINDOWS, CONTEXT_MENU, MULTIPLY, ADD, SEPARATOR, SUBTRACT, DECIMAL, DIVIDE, F1, F2, ",
                "F3, F4, F5, F6, F7, F8, F9, F10, F11, F12, F13, F14, F15, F16, F17, F18, F19, F20, F21, F22, F23, F24, ",
                "NUM_LOCK, SCROLL_LOCK, LEFT_SHIFT, RIGHT_SHIFT, LEFT_CTRL, RIGHT_CTRL, ;, +, ,, ",
                "-, ., /, `, [, \\, ], '"]

    mac = "RIGHT_ARROW, sleep 0.1, RIGHT_ARROW, sleep 0.1, RIGHT_ARROW, sleep 0.1, RIGHT_ARROW"

    text = {
        "RGB": "[0, 0, 0]",
        "POS": "(0, 0)",
        "KEY": "KEY name",
        "DRAG": "drag (from pos) (to pos)",
        "DELAY": "sleep 0.0",
        "MACRO": "MACRO name"
    }
    if not os.path.isfile('./config.json'):
        with open('./config.json', 'w') as f:
            save = {key:str(value) for key, value in key_mapping.items()}
            json.dump({"window_title":window_title, "support_key":support_key, "type":text, "key_mapping":save, "screen_size":screen_size, "MAC":mac}, f, indent=4)
    else:
        try:
            with open('./config.json', 'r') as f:
                load = json.load(f)

            if load.get('key_mapping') != None:
                key_mapping = {key:convert_value(value) for key, value in load["key_mapping"].items()}
            if load.get('screen_size') != None:
                screen_size = load["screen_size"]
            if load.get('window_title') != None:
                window_title = load['window_title']
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError("config.json has wrong syntax.", e.doc, e.pos)
        
    ratio = screen_size['x'], screen_size['y']

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
        self.hwnd = win32gui.FindWindow(None, window_title)
        if not self.hwnd:
            return
        process = self.find_process_by_name('umamusume.exe')
        if process is None:
            self.hwnd = 0
            return

        if win32process.GetWindowThreadProcessId(self.hwnd)[0] == process:
            return

        def callback(hwnd : int, _) -> None:
            if win32gui.IsWindowVisible(hwnd) and window_title == win32gui.GetWindowText(hwnd):
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
        self.frequency = 0.25
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
        time.sleep(10)
        # 5초간 화면 비율 검사
        while is_run and time.time() - delay < timeout and win32gui.IsWindow(self.window_handler.hwnd) and self.error == "":
            left, top, right, bottom = win32gui.GetWindowRect(self.window_handler.hwnd)
            # 최소화시 화면 크기가 달라짐
            if win32gui.IsIconic(self.window_handler.hwnd):
                timeout += 0.1
            elif abs(((bottom - top) / (right - left)) / (ratio[1] / ratio[0]) - 1) > 0.1:
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
        tokens = re.findall(r'\[.*?\]|\(.*?\)|\d+|\b\w+\s[\d.]+\b|\w+', load[text])
        for token in tokens:
            if token.startswith('('):
                if len(keys) > 0 and str(keys[-1]).startswith('drag') and keys[-1].count('(') < 2:
                    keys[-1] += ' ' + str(tuple(map(int, token[1:-1].split(','))))
                else:
                    keys.append(tuple(map(int, token[1:-1].split(','))))
            elif token.startswith('['):
                keys.append([int(x) for x in token[1:-1].split(',')])
            elif token.isdigit():
                keys.append(key_to_byte[token])
            elif re.match(r'\b\w+\s[\d.]+\b', token):
                keys.append(token)
            elif key_mapping.get(token) is not None:
                keys.append(key_mapping[token])
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
        key = key_mapping.get(byte_to_key.get(byte_data))
        if key is None or not self.window_handler.is_window_foreground():
            self.keyboard(byte_data)
            return False
        if type(key) == str and load.get(key) is not None:
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
        distance = min(max(abs(x1 - x2) / 20, abs(y1 - y2) / 20, 1), 40)
        width = right - left
        height = bottom - top
        x1 = (x1 * width) // ratio[0] + left
        y1 = (y1 * height) // ratio[1] + top
        x2 = (x2 * width) // ratio[0] + left
        y2 = (y2 * height) // ratio[1] + top
        left, top, right, bottom = left + 20, top + 60, right - 20, bottom - 20
        x1 = left if x1 < left else (right if x1 > right else x1)
        y1 = top if y1 < top else (bottom if y1 > bottom else y1)
        x2 = left if x2 < left else (right if x2 > right else x2)
        y2 = top if y2 < top else (bottom if y2 > bottom else y2)
        win32api.SetCursorPos((x1, y1))
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.01)
        dx, dy = (x2 - x1) / distance, (y2 - y1) / distance
        for _ in range(int(distance)):
            x1 += dx
            y1 += dy
            win32api.SetCursorPos((int(x1), int(y1)))
            time.sleep(0.0001)
        win32api.SetCursorPos((x2, y2))
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

    # 적절한 기능 수행
    def macro(self, key) -> None:
        """
        Executes a macro command.

        :param key: The macro command to execute
        :type key: str
        """
        if type(key) == list: # 색깔 기반
            self.color_finder.hwnd = self.window_handler.hwnd
            self.color_finder.timer = self.timer
            cx, cy = self.color_finder.find_color(key, self.tolerance)
            if cx is not None and cy is not None:
                if cx or cy:
                    self.click(cx, cy)
                    cx = cy = None
                self.timer = time.time()
        elif type(key) == tuple: # 좌표 기반
            left, top, right, bottom = win32gui.GetWindowRect(self.window_handler.hwnd)
            key = key[0] * (right - left) // ratio[0], key[1] * (bottom - top) // ratio[1]
            key = tuple(x + y for x, y in zip(key, (left, top)))
            left, top, right, bottom = left + 20, top + 60, right - 20, bottom - 20
            key = max(left, min(key[0], right)), max(top, min(key[1], bottom))
            self.click(*key)
        elif key.startswith('sleep'): # 딜레이
            try:
                time.sleep(float(key.lstrip('sleep ')))
            except:
                pass
        elif key.startswith('drag'):
            try:
                self.drag(key.lstrip('drag '))
            except:
                pass
        elif key_to_byte.get(key) is not None: # 단순 매핑
            self.keyboard(key_to_byte[key]) 
        elif load.get(key) is not None: # 매크로 속 매크로
            for text in self.decode(key):
                self.macro(text)

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
            load_json()
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
