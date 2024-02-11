#ifdef WARNING_EXPORTS
#define WARNING_API __declspec(dllexport)
#else
#define WARNING_API __declspec(dllimport)
#endif

#include <Windows.h>

extern "C" WARNING_API void show_warning_dialog(const wchar_t* message);