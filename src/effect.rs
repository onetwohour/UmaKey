
use std::ffi::c_void;
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
use std::sync::Mutex;
use std::thread;

use windows::core::PCWSTR;
use windows::Win32::Foundation::{COLORREF, HWND, LPARAM, LRESULT, POINT, RECT, WPARAM};
use windows::Win32::Graphics::Gdi::{
    BeginPaint, CreatePen, CreateSolidBrush, DeleteObject, Ellipse, EndPaint, FillRect,
    GetStockObject, InvalidateRect, SelectObject, HGDIOBJ, NULL_BRUSH, PAINTSTRUCT, PS_SOLID,
};
use windows::Win32::System::LibraryLoader::GetModuleHandleW;
use windows::Win32::UI::WindowsAndMessaging::{
    CreateWindowExW, DefWindowProcW, DispatchMessageW, GetCursorPos, GetMessageW, KillTimer,
    PostMessageW, PostQuitMessage, RegisterClassW, SetLayeredWindowAttributes, SetTimer,
    SetWindowPos, ShowWindow, TranslateMessage, HWND_TOPMOST, LWA_COLORKEY, MSG, SWP_NOACTIVATE,
    SW_HIDE, SW_SHOWNOACTIVATE, WM_APP, WM_DESTROY, WM_PAINT, WM_TIMER, WNDCLASSW,
    WS_EX_LAYERED, WS_EX_TOOLWINDOW, WS_EX_TOPMOST, WS_EX_TRANSPARENT, WS_POPUP,
};

use crate::mapper::wide;

const SIZE: i32 = 75;
const CENTER: i32 = SIZE / 2;
const MAX_RADIUS: f64 = 25.0;
const WM_APP_SHOW: u32 = WM_APP + 2;
const TIMER_ID: usize = 1;

static RIPPLE_HWND: AtomicUsize = AtomicUsize::new(0);
static ANIMATING: AtomicBool = AtomicBool::new(false);
static RADIUS: Mutex<f64> = Mutex::new(0.0);

fn rgb(r: i32, g: i32, b: i32) -> COLORREF {
    COLORREF((r as u32) | ((g as u32) << 8) | ((b as u32) << 16))
}

fn pink() -> COLORREF {
    rgb(255, 192, 203)
}

fn cursor() -> (i32, i32) {
    unsafe {
        let mut p = POINT { x: 0, y: 0 };
        let _ = GetCursorPos(&mut p);
        (p.x, p.y)
    }
}

pub fn start() {
    thread::spawn(|| unsafe {
        let hinstance = GetModuleHandleW(PCWSTR::null()).unwrap_or_default();
        let class_name = wide("UmaKeyRipple");
        let wc = WNDCLASSW {
            lpfnWndProc: Some(wndproc),
            hInstance: hinstance.into(),
            lpszClassName: PCWSTR(class_name.as_ptr()),
            ..Default::default()
        };
        RegisterClassW(&wc);

        let hwnd = match CreateWindowExW(
            WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST | WS_EX_TOOLWINDOW,
            PCWSTR(class_name.as_ptr()),
            PCWSTR::null(),
            WS_POPUP,
            0,
            0,
            SIZE,
            SIZE,
            None,
            None,
            hinstance,
            None,
        ) {
            Ok(h) => h,
            Err(_) => return,
        };
        let _ = SetLayeredWindowAttributes(hwnd, pink(), 0, LWA_COLORKEY);
        RIPPLE_HWND.store(hwnd.0 as usize, Ordering::SeqCst);

        let mut msg = MSG::default();
        while GetMessageW(&mut msg, None, 0, 0).0 > 0 {
            let _ = TranslateMessage(&msg);
            DispatchMessageW(&msg);
        }
    });
}

pub fn show() {
    let h = RIPPLE_HWND.load(Ordering::SeqCst);
    if h != 0 {
        unsafe {
            let _ = PostMessageW(HWND(h as *mut c_void), WM_APP_SHOW, WPARAM(0), LPARAM(0));
        }
    }
}

unsafe fn move_to_cursor(hwnd: HWND) {
    let (cx, cy) = cursor();
    let _ = SetWindowPos(
        hwnd,
        HWND_TOPMOST,
        cx - CENTER,
        cy - CENTER,
        SIZE,
        SIZE,
        SWP_NOACTIVATE,
    );
}

unsafe extern "system" fn wndproc(
    hwnd: HWND,
    msg: u32,
    wparam: WPARAM,
    lparam: LPARAM,
) -> LRESULT {
    match msg {
        m if m == WM_APP_SHOW => {
            *RADIUS.lock().unwrap() = 0.0;
            ANIMATING.store(true, Ordering::SeqCst);
            move_to_cursor(hwnd);
            let _ = ShowWindow(hwnd, SW_SHOWNOACTIVATE);
            SetTimer(hwnd, TIMER_ID, 10, None);
            LRESULT(0)
        }
        WM_TIMER => {
            let mut radius = RADIUS.lock().unwrap();
            if *radius > MAX_RADIUS {
                ANIMATING.store(false, Ordering::SeqCst);
                let _ = KillTimer(hwnd, TIMER_ID);
                let _ = ShowWindow(hwnd, SW_HIDE);
            } else {
                move_to_cursor(hwnd);
                *radius += 1.5;
                let _ = InvalidateRect(hwnd, None, true);
            }
            LRESULT(0)
        }
        WM_PAINT => {
            paint(hwnd);
            LRESULT(0)
        }
        WM_DESTROY => {
            PostQuitMessage(0);
            LRESULT(0)
        }
        _ => DefWindowProcW(hwnd, msg, wparam, lparam),
    }
}

unsafe fn paint(hwnd: HWND) {
    let mut ps = PAINTSTRUCT::default();
    let hdc = BeginPaint(hwnd, &mut ps);

    let bg = CreateSolidBrush(pink());
    let full = RECT { left: 0, top: 0, right: SIZE, bottom: SIZE };
    FillRect(hdc, &full, bg);
    let _ = DeleteObject(HGDIOBJ(bg.0));

    if ANIMATING.load(Ordering::SeqCst) {
        let radius = *RADIUS.lock().unwrap();
        let r = (128.0 + radius * 5.0).min(255.0) as i32;
        let g = (136.0 + radius * 3.0).min(255.0) as i32;
        let width = (5.0 - radius * 0.15).max(1.0) as i32;
        let pen = CreatePen(PS_SOLID, width, rgb(r, g, 255));
        let old_pen = SelectObject(hdc, HGDIOBJ(pen.0));
        let old_brush = SelectObject(hdc, GetStockObject(NULL_BRUSH));
        let rad = radius as i32;
        let _ = Ellipse(hdc, CENTER - rad, CENTER - rad, CENTER + rad, CENTER + rad);
        SelectObject(hdc, old_brush);
        SelectObject(hdc, old_pen);
        let _ = DeleteObject(HGDIOBJ(pen.0));
    }

    let _ = EndPaint(hwnd, &ps);
}
