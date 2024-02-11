#include "WindowCapture.hpp"

void CaptureAndCropScreen(unsigned char** imageData, int x, int y, int cropWidth, int cropHeight) {
    SetProcessDPIAware();

    HDC hdcScreen = GetDC(NULL);
    HDC hdcMem = CreateCompatibleDC(hdcScreen);
    HBITMAP hBitmap = CreateCompatibleBitmap(hdcScreen, cropWidth, cropHeight);
    HBITMAP hOldBitmap = (HBITMAP)SelectObject(hdcMem, hBitmap);

    BitBlt(hdcMem, 0, 0, cropWidth, cropHeight, hdcScreen, x, y, SRCCOPY);

    int size = cropWidth * cropHeight * 3;
    *imageData = (unsigned char*)malloc(size);

    BITMAPINFO bmi;
    ZeroMemory(&bmi, sizeof(BITMAPINFO));
    bmi.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
    bmi.bmiHeader.biWidth = cropWidth;
    bmi.bmiHeader.biHeight = -cropHeight;
    bmi.bmiHeader.biPlanes = 1;
    bmi.bmiHeader.biBitCount = 24;
    bmi.bmiHeader.biCompression = BI_RGB;

    GetDIBits(hdcMem, hBitmap, 0, cropHeight, *imageData, &bmi, DIB_RGB_COLORS);

    SelectObject(hdcMem, hOldBitmap);
    DeleteObject(hBitmap);
    DeleteDC(hdcMem);
    ReleaseDC(NULL, hdcScreen);
}

void FreeImageData(unsigned char* imageData) {
    free(imageData);
}
