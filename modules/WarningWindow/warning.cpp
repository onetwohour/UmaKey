// warning.cpp : DLL을 위해 내보낸 함수를 정의
//

#include "pch.h"
#include "framework.h"
#include "warning.h"
#include <Windows.h>
extern "C" {
__declspec(dllexport)
// 내보낸 함수.
WARNING_API void show_warning_dialog(const wchar_t* message) {
    MessageBoxW(NULL, message, L"Warning", MB_ICONWARNING | MB_OK | MB_SYSTEMMODAL);
}
} // extern "C"
