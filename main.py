import win32gui
import win32con
from win32con import VK_LSHIFT, VK_RSHIFT, VK_LCONTROL, VK_RCONTROL
import win32api
import numpy as np
import cv2
import subprocess
import time
import os
from PIL import ImageGrab
from ctypes import windll
user32 = windll.user32
user32.SetProcessDPIAware()

is_run = False

# 특정 프로그램의 창 제목과 키와 색상 매핑 설정
window_title = "umamusume"
key_mapping = {
    'Space': [99,182,0],        # 초록버튼
    '`':     [231, 231, 236],   # 흰 버튼
    'Q':     [124, 203, 42],    # 휴식
    'W':     [41, 122, 207],    # 트레이닝
    'E':     [40, 191, 214],    # 스킬
    'R':     [247, 154, 8],     # 외출
    'F':     [145, 96, 239],    # 양호실
    'T':     [217, 81, 242],    # 레슨
    'G':     [244, 69, 137],    # 레이스
    'TAB':     'Drag',            # 훈련 돌아보기
    'A':    [225, 255, 178],    # 1번 선택지
    'S':    [255, 247, 192],    # 2번 선택지
    'D':    [255, 228, 239],    # 3번 선택지
}



def match_byte_to_key(byte_data):
    # ASCII 문자에 해당하는 바이트 값을 키로 가지는 딕셔너리
    byte_to_key = {
        0: "NUL", 1: "SOH", 2: "STX", 3: "ETX", 4: "EOT", 5: "ENQ", 6: "ACK", 7: "BEL",
        8: "BS", 9: "TAB", 10: "LF", 11: "VT", 12: "FF", 13: "CR", 14: "SO", 15: "SI",
        16: "DLE", 17: "DC1", 18: "DC2", 19: "DC3", 20: "DC4", 21: "NAK", 22: "SYN", 23: "ETB",
        24: "CAN", 25: "EM", 26: "SUB", 27: "ESC", 28: "FS", 29: "GS", 30: "RS", 31: "US",
        32: "Space", 33: "!", 34: "\"", 35: "#", 36: "$", 37: "%", 38: "&", 39: "'",
        40: "(", 41: ")", 42: "*", 43: "+", 44: ",", 45: "-", 46: ".", 47: "/",
        48: "0", 49: "1", 50: "2", 51: "3", 52: "4", 53: "5", 54: "6", 55: "7",
        56: "8", 57: "9", 58: ":", 59: ";", 60: "<", 61: "=", 62: ">", 63: "?",
        64: "@", 65: "A", 66: "B", 67: "C", 68: "D", 69: "E", 70: "F", 71: "G",
        72: "H", 73: "I", 74: "J", 75: "K", 76: "L", 77: "M", 78: "N", 79: "O",
        80: "P", 81: "Q", 82: "R", 83: "S", 84: "T", 85: "U", 86: "V", 87: "W",
        88: "X", 89: "Y", 90: "Z", 91: "[", 92: "\\", 93: "]", 94: "^", 95: "_",
        96: "`", 97: "a", 98: "b", 99: "c", 100: "d", 101: "e", 102: "f", 103: "g",
        104: "h", 105: "i", 106: "j", 107: "k", 108: "l", 109: "m", 110: "n", 111: "o",
        112: "p", 113: "q", 114: "r", 115: "s", 116: "t", 117: "u", 118: "v", 119: "w",
        120: "x", 121: "y", 122: "z", 123: "{", 124: "|", 125: "}", 126: "~", 127: "DEL",
        160: VK_LSHIFT, 161: VK_RSHIFT, 162: VK_LCONTROL, 163: VK_RCONTROL, 192: '`'
    }
    
    # 딕셔너리에서 해당하는 키 반환, 없으면 None 반환
    return byte_to_key.get(byte_data)

class WindowHandler:
    def __init__(self):
        self.hwnd = 0
        while self.hwnd == 0 and is_run:
            self.hwnd = win32gui.FindWindow(None, window_title)
            time.sleep(0.5)

    def is_window_foreground(self):
        return self.hwnd == win32gui.GetForegroundWindow()

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
        self.max_height = int((bottom - top) // (5 / 2))
        self.max_width = (right - left) // 2

        image = ImageGrab.grab(all_screens=True)
        img = np.array(image)[top + self.max_height:bottom, left:right]
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

    def run(self):
        if not is_run:
            return
        self.timer = time.time()

        if self.window_handler == None:
            self.window_handler = WindowHandler()

        # C++ 프로그램 실행
        if self.cpp_process == None:
            self.cpp_process = subprocess.Popen(f"{os.path.join(os.getcwd(), '_internal', 'input.exe')}", stdout=subprocess.PIPE, bufsize=1, universal_newlines=True)
            if not os.path.isfile(os.path.join(os.getcwd(), '_internal', 'input.exe')):
                raise FileNotFoundError(f"File not exist : {os.path.join(os.getcwd(), '_internal', 'input.exe')}")

        # C++ 프로그램의 출력을 읽어 키보드 입력 추출
        while is_run:
            if not win32gui.IsWindow(self.window_handler.hwnd):
                self.cpp_process.terminate()
                del self.window_handler
                self.window_handler = WindowHandler()
                self.cpp_process = subprocess.Popen(f"{os.path.join(os.getcwd(), '_internal', 'input.exe')}", stdout=subprocess.PIPE, bufsize=1, universal_newlines=True)
            
            # 바이트 단위로 데이터를 읽어옴
            byte_data = self.cpp_process.stdout.readline()[:-1]
            t, text = byte_data.split(' ')
            if int(time.time() * 1000) - int(t) > 100:
                continue
            self.on_keyboard_event(int(text))

    def on_keyboard_event(self, byte_data):
        if self.window_handler.is_window_foreground():
            key = self.key_mapping.get(match_byte_to_key(byte_data))
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
        if self.cpp_process != None:
            try:
                self.cpp_process.terminate()
            except:
                pass
        if self.window_handler != None:
            del self.window_handler

    def toggle(self):
        global is_run
        is_run = not is_run
        if is_run:
            self.run()
        elif self.cpp_process != None:
            self.cpp_process.terminate()
            self.cpp_process = None
            del self.window_handler
            self.window_handler = None

if __name__ == '__main__':
    auto_clicker = AutoClicker(key_mapping)
    auto_clicker.toggle()
