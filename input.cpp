#include <iostream>
#include <Windows.h>
#include <Shellapi.h>

// 전역 훅 함수
LRESULT CALLBACK LowLevelKeyboardProc(int nCode, WPARAM wParam, LPARAM lParam) {
    if (nCode == HC_ACTION) {
        KBDLLHOOKSTRUCT* kbStruct = reinterpret_cast<KBDLLHOOKSTRUCT*>(lParam);
        // 키보드 이벤트가 Key Down일 때만 처리
        if (wParam == WM_KEYDOWN) {
            DWORD vkCode = kbStruct->vkCode;
            if (kbStruct->dwExtraInfo != 3000)
            {
                std::cout << vkCode << std::endl << std::flush;
                return 1;
            }
        }
    }
    // 다음 후크 호출
    return CallNextHookEx(NULL, nCode, wParam, lParam);
}

int main() {
    ShowWindow(GetConsoleWindow(), SW_HIDE);

    // Low-Level Keyboard Hook 설치
    HHOOK keyboardHook = SetWindowsHookEx(WH_KEYBOARD_LL, LowLevelKeyboardProc, NULL, 0);
    if (!keyboardHook) {
        std::cerr << "Failed to install keyboard hook" << std::endl;
        return 1;
    }

    // 메시지 루프
    MSG msg;
    while (GetMessage(&msg, NULL, 0, 0)) {
        TranslateMessage(&msg);
        DispatchMessage(&msg);
    }

    // 후크 제거
    UnhookWindowsHookEx(keyboardHook);

    return 0;
}
