#include <iostream>
#include <Windows.h>
#include <Shellapi.h>
#include <tlhelp32.h>
#include <chrono>

const int TIME = 500;
std::chrono::milliseconds duration(TIME);
auto millisecond = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::system_clock::now().time_since_epoch());
auto now = millisecond;

bool isProcessRunning(const std::wstring& processName) {
    HANDLE hSnap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (hSnap == INVALID_HANDLE_VALUE) {
        return false;
    }

    PROCESSENTRY32W pe;
    pe.dwSize = sizeof(PROCESSENTRY32W);

    if (!Process32FirstW(hSnap, &pe)) {
        CloseHandle(hSnap);
        return false;
    }

    do {
        if (processName == pe.szExeFile) {
            CloseHandle(hSnap);
            return true;
        }
    } while (Process32NextW(hSnap, &pe));

    CloseHandle(hSnap);
    return false;
}

// 전역 훅 함수
LRESULT CALLBACK LowLevelKeyboardProc(int nCode, WPARAM wParam, LPARAM lParam) {
    now = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::system_clock::now().time_since_epoch());
    if (now - millisecond > duration)
    {
        if (!isProcessRunning(L"UmaKey.exe"))
            std::exit(0);
        millisecond = now;
    }

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
