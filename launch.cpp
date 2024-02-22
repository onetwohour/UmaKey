#include <iostream>
#include <Windows.h>
#include <string>
#include <filesystem>
#include <TlHelp32.h>

namespace fs = std::filesystem;

bool isProcessRunning(const std::wstring& processName) {
    HANDLE hProcessSnap;
    PROCESSENTRY32 pe32;

    // Take a snapshot of all processes in the system.
    hProcessSnap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (hProcessSnap == INVALID_HANDLE_VALUE) {
        return false;
    }

    // Set the size of the structure before using it.
    pe32.dwSize = sizeof(PROCESSENTRY32);

    // Retrieve information about the first process and exit if unsuccessful
    if (!Process32First(hProcessSnap, &pe32)) {
        CloseHandle(hProcessSnap);          // clean the snapshot object
        return false;
    }

    // Now walk the snapshot of processes
    do {
        // Check if the process name matches
        if (_wcsicmp(pe32.szExeFile, processName.c_str()) == 0) {
            CloseHandle(hProcessSnap);
            return true;
        }
    } while (Process32Next(hProcessSnap, &pe32));

    CloseHandle(hProcessSnap);
    return false;
}

int main() {
    std::wstring processName = L"UmaKey.exe";
    std::wstring targetDir = fs::current_path().wstring() + L"\\_internal\\";

    if (isProcessRunning(processName)) {
        return 0;
    }

    for (const auto& file : { L"UmaKey.ico", L"warning.dll", L"WindowCapture.dll", L"findColor.dll", L"opencv_world490.dll"}) {
        if (!fs::exists(targetDir + file)) {
            std::wcerr << L"File not Found : " << targetDir + file << std::endl;
            return 1;
        }
    }

    // Launch UmaKey.exe
    ShellExecute(NULL, NULL, processName.c_str(), NULL, NULL, SW_HIDE); // SW_HIDE를 사용하여 프로세스 실행 중 창을 숨깁니다.

    return 0;
}
