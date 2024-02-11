#include "warning.h"

void show_warning_dialog(const wchar_t* message) {
    MessageBoxW(NULL, message, L"Warning", MB_ICONWARNING | MB_OK | MB_SYSTEMMODAL);
}
