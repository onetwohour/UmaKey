#ifdef WINDOWCAPTURE_EXPORTS
#define WINDOWCAPTURE_API __declspec(dllexport)
#else
#define WINDOWCAPTURE_API __declspec(dllimport)
#endif
#ifdef  _WIN64
#define _HEAP_MAXREQ    0xFFFFFFFFFFFFFFE0
#endif

#include <iostream>
#include <Windows.h>

extern "C" WINDOWCAPTURE_API void CaptureAndCropScreen(unsigned char** imageData, int x, int y, int cropWidth, int cropHeight);

extern "C" WINDOWCAPTURE_API void FreeImageData(unsigned char* imageData);