import win32gui
import win32con
import win32api
import numpy as np
import cv2
import subprocess
import time
import os
import json
import sys
from PIL import ImageGrab
from threading import Thread
from ctypes import *
user32 = windll.user32
user32.SetProcessDPIAware()

is_run = False

# 특정 프로그램의 창 제목과 키와 색상 매핑 설정
window_title = "umamusume"
key_mapping = {}
ratio = 0

def convert_value(value_str):
    # 리스트 형태인 경우
    if value_str.startswith("[") and value_str.endswith("]"):
        return [int(x) for x in value_str[1:-1].split(",")]
    # 튜플 형태인 경우
    elif value_str.startswith("(") and value_str.endswith(")"):
        return tuple(int(x) for x in value_str[1:-1].split(","))
    # 정수 형태인 경우
    elif value_str.isdigit():
        return int(value_str)
    else:
        return value_str

def load_json():
    global key_mapping, ratio
    if not os.path.isfile('./config.json'):
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
            'TAB':   'Drag',            # 훈련 돌아보기
            'A':    [225, 255, 178],    # 1번 선택지
            'S':    [255, 247, 192],    # 2번 선택지
            'D':    [255, 228, 239],    # 3번 선택지
            '/':    (730, 1320),
        }

        screen_size = {
            'x': 808,
            'y': 1453
        }

        with open('./config.json', 'w') as f:
            save = {key:str(value) for key, value in key_mapping.items()}
            json.dump({"key_mapping":save, "screen_size":screen_size}, f, indent=4)
    else:
        try:
            with open('./config.json', 'r') as f:
                load = json.load(f)

            key_mapping = {key:convert_value(value) for key, value in load["key_mapping"].items()}
            screen_size = load["screen_size"]
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError("config.json has wrong syntax.", e.doc, e.pos)
        
    ratio = screen_size['x'], screen_size['y']

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

class WindowHandler:
    def __init__(self):
        self.hwnd = 0

    def is_window_foreground(self):
        return self.hwnd == win32gui.GetForegroundWindow()
    
    def update(self):
        self.hwnd = win32gui.FindWindow(None, window_title)

    def activate_widnow(self):
        try:
            time.sleep(0.25)
            win32gui.SetForegroundWindow(self.hwnd)
            return True
        except:
            return False

class ColorFinder:
    def __init__(self, hwnd, timer):
        self.hwnd = hwnd
        self.max_height = 0
        self.max_width = 0
        self.timer = timer
        self.frequency = 0.25

    def find_color(self, target_color, tolerance):
        if time.time() - self.timer < self.frequency:
            return None, None

        left, top, right, bottom = win32gui.GetWindowRect(self.hwnd)
        self.max_height = int((bottom - top) // (5 / 1))
        self.max_width = (right - left) // 2

        image = ImageGrab.grab(bbox=(left, top + self.max_height, right, bottom), all_screens=True)
        img = np.array(image)
        image.close()

        lower_bound = np.clip(np.array([target_color[0] - tolerance, target_color[1] - tolerance, target_color[2] - tolerance]), 0, 255)
        upper_bound = np.clip(np.array([target_color[0] + tolerance, target_color[1] + tolerance, target_color[2] + tolerance]), 0, 255)
        mask = cv2.inRange(img, lower_bound, upper_bound)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        contours = [contour for contour in contours if cv2.boundingRect(contour)[2] <= self.max_width and cv2.boundingRect(contour)[3] <= self.max_height]
        if not contours:
            return False, False

        max_contour = max(contours, key=cv2.contourArea)
        M = cv2.moments(max_contour)
        if M['m00'] != 0:
            cx = int(M['m10'] / M['m00']) + left
            cy = int(M['m01'] / M['m00']) + top + self.max_height

            return cx, cy
        else:
            return False, False

class AutoClicker:
    def __init__(self, key_mapping=key_mapping, tolerance=10):
        self.window_handler = None
        self.color_finder = None
        self.key_mapping = key_mapping
        self.tolerance = tolerance
        self.cpp_process = None
        self.timer = 0
        self.runner = 0

    def run(self):
        if not is_run or self.runner > 0:
            return
        self.timer = time.time()
        self.runner += 1
        Thread(target=self.check_screen, daemon=True).start()

        if self.window_handler == None:
            self.window_handler = WindowHandler()

        # C++ 프로그램 실행
        if self.cpp_process == None:
            self.cpp_process = subprocess.Popen("./_internal/input.exe", stdout=subprocess.PIPE, bufsize=1, universal_newlines=True)
            if not os.path.isfile('./_internal/input.exe'):
                raise FileNotFoundError(f"File not exist : {os.path.join(os.getcwd(), '_internal', 'input.exe')}")

        # C++ 프로그램의 출력을 읽어 키보드 입력 추출
        while is_run:
            if not win32gui.IsWindow(self.window_handler.hwnd):
                self.window_handler.update()
                if self.window_handler.hwnd == 0:
                    self.destroy()
                    self.cpp_process = None
                    time.sleep(0.5)
                    continue
                elif not self.window_handler.activate_widnow():
                    continue
                Thread(target=self.screen_size_detect).start()

            byte_data = ""

            # 데이터를 읽어옴
            if self.cpp_process != None:
                byte_data = self.cpp_process.stdout.readline()[:-1]

            if not byte_data:
                self.destroy()
                if is_run:
                    self.cpp_process = subprocess.Popen("./_internal/input.exe", stdout=subprocess.PIPE, bufsize=1, universal_newlines=True)
                continue
            elif byte_data == "UmaKeyNotFound":
                raise ProcessLookupError(byte_data)
            
            t, text = byte_data.split(' ')
            if int(time.time() * 1000) - int(t) > 100:
                continue
            self.on_keyboard_event(int(text))

        self.runner -= 1

    def screen_size_detect(self):
        delay = timer = time.time()
        while is_run and time.time() - delay < 30 and win32gui.IsWindow(self.window_handler.hwnd):
            left, top, right, bottom = win32gui.GetWindowRect(self.window_handler.hwnd)
            if abs(((bottom - top) / (right - left)) / (ratio[1] / ratio[0]) - 1) > 0.05 and (240, 320) != (bottom - top, right - left):
                if time.time() - timer < 5:
                    continue
                if not os.path.isfile('./_internal/warning.dll'):
                    raise FileNotFoundError(f"File not exist : {os.path.join(os.getcwd(), '_internal', 'warning.dll')}")
                dll = cdll.LoadLibrary(os.path.join(os.getcwd(), '_internal', 'warning.dll')).show_warning_dialog
                dll.argtypes = [c_wchar_p]
                dll.restype = None
                dll("게임 화면 비율이 다릅니다.")
                del dll
                break

    def check_screen(self):
        timer = time.time()
        while is_run:
            if not win32gui.IsWindow(self.window_handler.hwnd):
                if time.time() - timer > 10:
                    self.destroy()
                    self.cpp_process = None
            else:
                timer = time.time()

            time.sleep(0.5)

    def on_keyboard_event(self, byte_data):
        if self.window_handler.is_window_foreground():
            key = self.key_mapping.get(byte_to_key.get(byte_data))
            if key != None:
                if type(key) == list: # 색깔 기반
                    self.color_finder = ColorFinder(self.window_handler.hwnd, self.timer)
                    cx, cy = self.color_finder.find_color(key, self.tolerance)

                    if cx != None and cy != None:
                        if cx or cy:
                            self.click(cx, cy)
                            cx = cy = None
                        self.timer = time.time()

                elif type(key) == tuple: # 좌표 기반
                    left, top, right, bottom = win32gui.GetWindowRect(self.window_handler.hwnd)
                    key = key[0] * (right - left) // ratio[0], key[1] * (bottom - top) // ratio[1]
                    key = tuple(x + y for x, y in zip(key, (left, top)))
                    self.click(*key)
                elif type(key) == int: # 단순 매핑
                    self.keyboard(key)
                elif key == 'Drag': # 특수기능
                    left, top, right, bottom = win32gui.GetWindowRect(self.window_handler.hwnd)
                    self.click((left + right) // 2, (top + bottom) // 2)
                    for i in range(49, 54):
                        self.keyboard(i)
                        time.sleep(0.1)
                return True 
        win32api.keybd_event(byte_data, 0, 0, 3000)
        return False
            
    def keyboard(self, code):
        win32api.keybd_event(code, 0, 0, 3000)
        win32api.keybd_event(code, 0, win32con.KEYEVENTF_KEYUP, 3000)

    def click(self, x, y):
        win32api.SetCursorPos((x, y))
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, x, y, 0, 0)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, x, y, 0, 0)

    def __del__(self):
        global is_run
        is_run = False
        self.destroy()

    def destroy(self):
        try:
            self.cpp_process.terminate()
            del self.cpp_process
        except:
            pass

    def toggle(self):
        global is_run
        is_run = not is_run
        if is_run:
            load_json()
            self.key_mapping = key_mapping
            self.run()
        else:
            self.destroy()
            del self.window_handler
            self.cpp_process = self.window_handler = None

if __name__ == '__main__':
    auto_clicker = AutoClicker(key_mapping)
    auto_clicker.toggle()
