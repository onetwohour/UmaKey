//! ColorFinder 이식: PrintWindow로 창을 캡처하고 색을 찾아 무게중심을 반환.
//! OpenCV 대신 마스크 + 최대 연결요소 무게중심을 직접 계산한다.

use std::ffi::c_void;
use windows::Win32::Foundation::HWND;
use windows::Win32::Graphics::Gdi::{
    ClientToScreen, CreateCompatibleBitmap, CreateCompatibleDC, DeleteDC, DeleteObject, GetDIBits,
    GetWindowDC, ReleaseDC, SelectObject, BITMAPINFO, BITMAPINFOHEADER, BI_RGB, DIB_RGB_COLORS,
    HGDIOBJ,
};
use windows::Win32::Storage::Xps::{PrintWindow, PRINT_WINDOW_FLAGS};
use windows::Win32::UI::WindowsAndMessaging::GetClientRect;
use windows::Win32::Foundation::POINT;
use windows::Win32::Foundation::RECT;

pub struct ColorFinder {
    pub hwnd: HWND,
}

impl ColorFinder {
    pub fn new(hwnd: HWND) -> Self {
        Self { hwnd }
    }

    /// 창 클라이언트 영역을 BGRA 버퍼로 캡처. (buffer, width, height).
    fn capture(&self) -> Option<(Vec<u8>, i32, i32)> {
        unsafe {
            let mut rect = RECT::default();
            GetClientRect(self.hwnd, &mut rect).ok()?;
            let width = rect.right - rect.left;
            let height = rect.bottom - rect.top;
            if width <= 0 || height <= 0 {
                return None;
            }

            let hwindc = GetWindowDC(self.hwnd);
            let memdc = CreateCompatibleDC(hwindc);
            let bitmap = CreateCompatibleBitmap(hwindc, width, height);
            let old = SelectObject(memdc, HGDIOBJ(bitmap.0));
            let _ = PrintWindow(self.hwnd, memdc, PRINT_WINDOW_FLAGS(3));

            let mut bmi = BITMAPINFO {
                bmiHeader: BITMAPINFOHEADER {
                    biSize: std::mem::size_of::<BITMAPINFOHEADER>() as u32,
                    biWidth: width,
                    biHeight: -height,
                    biPlanes: 1,
                    biBitCount: 32,
                    biCompression: BI_RGB.0,
                    ..Default::default()
                },
                ..Default::default()
            };

            let mut buf = vec![0u8; (width * height * 4) as usize];
            let scanned = GetDIBits(
                memdc,
                bitmap,
                0,
                height as u32,
                Some(buf.as_mut_ptr() as *mut c_void),
                &mut bmi,
                DIB_RGB_COLORS,
            );

            SelectObject(memdc, old);
            let _ = DeleteObject(HGDIOBJ(bitmap.0));
            let _ = DeleteDC(memdc);
            ReleaseDC(self.hwnd, hwindc);

            if scanned == 0 {
                return None;
            }
            Some((buf, width, height))
        }
    }

    /// 대상 색을 찾아 스크린 좌표 무게중심을 반환. 못 찾으면 None.
    pub fn find_color(&self, target: [i32; 3], tolerance: i32) -> Option<(i32, i32)> {
        let (buf, width, height) = self.capture()?;
        let w = width as usize;
        let h = height as usize;
        let max_height = h / 5;
        let offset = 20usize;
        if w <= 2 * offset || h <= max_height {
            return None;
        }

        let lower = [
            clamp_u8(target[0] - tolerance),
            clamp_u8(target[1] - tolerance),
            clamp_u8(target[2] - tolerance),
        ];
        let upper = [
            clamp_u8(target[0] + tolerance),
            clamp_u8(target[1] + tolerance),
            clamp_u8(target[2] + tolerance),
        ];

        let mut mask = vec![false; w * h];
        for row in max_height..h {
            for col in offset..(w - offset) {
                let idx = (row * w + col) * 4;
                let b = buf[idx];
                let g = buf[idx + 1];
                let r = buf[idx + 2];
                if in_range([r, g, b], lower, upper) {
                    mask[row * w + col] = true;
                }
            }
        }

        let (cx, cy) = largest_blob_centroid(&mask, w, h)?;

        let mut origin = POINT { x: 0, y: 0 };
        unsafe {
            let _ = ClientToScreen(self.hwnd, &mut origin);
        }
        Some((origin.x + cx.round() as i32, origin.y + cy.round() as i32))
    }
}

fn clamp_u8(v: i32) -> u8 {
    v.clamp(0, 255) as u8
}

/// RGB 픽셀이 [lower, upper] 범위 안인지.
fn in_range(px: [u8; 3], lower: [u8; 3], upper: [u8; 3]) -> bool {
    px[0] >= lower[0]
        && px[0] <= upper[0]
        && px[1] >= lower[1]
        && px[1] <= upper[1]
        && px[2] >= lower[2]
        && px[2] <= upper[2]
}

/// 8-연결 최대 blob의 무게중심(col, row). true 픽셀이 없으면 None.
fn largest_blob_centroid(mask: &[bool], w: usize, h: usize) -> Option<(f64, f64)> {
    let mut visited = vec![false; w * h];
    let mut best_count = 0usize;
    let mut best_centroid = None;
    let mut stack: Vec<(usize, usize)> = Vec::new();

    for start in 0..(w * h) {
        if !mask[start] || visited[start] {
            continue;
        }
        stack.clear();
        stack.push((start % w, start / w));
        visited[start] = true;
        let mut count = 0usize;
        let mut sum_x = 0f64;
        let mut sum_y = 0f64;

        while let Some((cx, cy)) = stack.pop() {
            count += 1;
            sum_x += cx as f64;
            sum_y += cy as f64;
            let x0 = cx.saturating_sub(1);
            let x1 = (cx + 1).min(w - 1);
            let y0 = cy.saturating_sub(1);
            let y1 = (cy + 1).min(h - 1);
            for ny in y0..=y1 {
                for nx in x0..=x1 {
                    let ni = ny * w + nx;
                    if mask[ni] && !visited[ni] {
                        visited[ni] = true;
                        stack.push((nx, ny));
                    }
                }
            }
        }

        if count > best_count {
            best_count = count;
            best_centroid = Some((sum_x / count as f64, sum_y / count as f64));
        }
    }

    best_centroid
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn in_range_bounds() {
        assert!(in_range([100, 100, 100], [90, 90, 90], [110, 110, 110]));
        assert!(!in_range([100, 100, 89], [90, 90, 90], [110, 110, 110]));
    }

    #[test]
    fn centroid_picks_largest_blob() {
        let w = 10;
        let h = 10;
        let mut mask = vec![false; w * h];
        mask[0] = true;
        for row in 5..9 {
            for col in 5..9 {
                mask[row * w + col] = true;
            }
        }
        let (cx, cy) = largest_blob_centroid(&mask, w, h).unwrap();
        assert!((cx - 6.5).abs() < 1e-9);
        assert!((cy - 6.5).abs() < 1e-9);
    }

    #[test]
    fn centroid_none_when_empty() {
        let mask = vec![false; 16];
        assert!(largest_blob_centroid(&mask, 4, 4).is_none());
    }
}
