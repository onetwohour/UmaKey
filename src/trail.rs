
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
use std::sync::Mutex;
use std::thread;

use windows::core::PCWSTR;
use windows::Win32::Foundation::{COLORREF, HWND, LPARAM, LRESULT, RECT, WPARAM};
use windows::Win32::Graphics::Gdi::{
    BeginPaint, CreatePen, CreateSolidBrush, DeleteObject, EndPaint, FillRect, InvalidateRect,
    LineTo, MoveToEx, SelectObject, HGDIOBJ, PAINTSTRUCT, PS_SOLID,
};
use windows::Win32::System::LibraryLoader::GetModuleHandleW;
use windows::Win32::UI::WindowsAndMessaging::{
    CreateWindowExW, DefWindowProcW, DispatchMessageW, GetClientRect, GetMessageW,
    GetSystemMetrics, RegisterClassW, SetLayeredWindowAttributes, SetTimer, SetWindowPos,
    ShowWindow, TranslateMessage, HWND_TOPMOST, LWA_COLORKEY, MSG, SM_CXVIRTUALSCREEN,
    SM_CYVIRTUALSCREEN, SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN, SWP_NOACTIVATE, SW_HIDE,
    SW_SHOWNOACTIVATE, WM_PAINT, WM_TIMER, WNDCLASSW, WS_EX_LAYERED, WS_EX_TOOLWINDOW,
    WS_EX_TOPMOST, WS_EX_TRANSPARENT, WS_POPUP,
};

use crate::mapper::wide;

const TIMER_ID: usize = 1;

static HWND_PTR: AtomicUsize = AtomicUsize::new(0);
static INIT: AtomicBool = AtomicBool::new(false);
static ACTIVE: AtomicBool = AtomicBool::new(false);
static SHOWN: AtomicBool = AtomicBool::new(false);
static ORIGIN: Mutex<(i32, i32)> = Mutex::new((0, 0));
static POINTS: Mutex<Vec<(i32, i32)>> = Mutex::new(Vec::new());

fn rgb(r: i32, g: i32, b: i32) -> COLORREF {
    COLORREF((r as u32) | ((g as u32) << 8) | ((b as u32) << 16))
}
fn colorkey() -> COLORREF {
    rgb(255, 0, 255)
}
fn trail_color() -> COLORREF {
    rgb(90, 200, 90)
}

fn virtual_screen() -> (i32, i32, i32, i32) {
    unsafe {
        (
            GetSystemMetrics(SM_XVIRTUALSCREEN),
            GetSystemMetrics(SM_YVIRTUALSCREEN),
            GetSystemMetrics(SM_CXVIRTUALSCREEN),
            GetSystemMetrics(SM_CYVIRTUALSCREEN),
        )
    }
}

pub fn start() {
    POINTS.lock().unwrap().clear();
    ACTIVE.store(true, Ordering::SeqCst);
    if !INIT.swap(true, Ordering::SeqCst) {
        thread::spawn(|| unsafe { window_thread() });
    }
}

pub fn push(x: i32, y: i32) {
    POINTS.lock().unwrap().push((x, y));
}

pub fn stop() {
    ACTIVE.store(false, Ordering::SeqCst);
}

unsafe fn window_thread() {
    let hinstance = GetModuleHandleW(PCWSTR::null()).unwrap_or_default();
    let class_name = wide("UmaKeyTrail");
    let wc = WNDCLASSW {
        lpfnWndProc: Some(wndproc),
        hInstance: hinstance.into(),
        lpszClassName: PCWSTR(class_name.as_ptr()),
        ..Default::default()
    };
    RegisterClassW(&wc);

    let (xv, yv, cxv, cyv) = virtual_screen();
    *ORIGIN.lock().unwrap() = (xv, yv);

    let hwnd = match CreateWindowExW(
        WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST | WS_EX_TOOLWINDOW,
        PCWSTR(class_name.as_ptr()),
        PCWSTR::null(),
        WS_POPUP,
        xv,
        yv,
        cxv,
        cyv,
        None,
        None,
        hinstance,
        None,
    ) {
        Ok(h) => h,
        Err(_) => return,
    };
    let _ = SetLayeredWindowAttributes(hwnd, colorkey(), 0, LWA_COLORKEY);
    HWND_PTR.store(hwnd.0 as usize, Ordering::SeqCst);
    SetTimer(hwnd, TIMER_ID, 16, None);

    let mut msg = MSG::default();
    while GetMessageW(&mut msg, None, 0, 0).0 > 0 {
        let _ = TranslateMessage(&msg);
        DispatchMessageW(&msg);
    }
}

unsafe extern "system" fn wndproc(
    hwnd: HWND,
    msg: u32,
    wparam: WPARAM,
    lparam: LPARAM,
) -> LRESULT {
    match msg {
        WM_TIMER => {
            if ACTIVE.load(Ordering::SeqCst) {
                if !SHOWN.swap(true, Ordering::SeqCst) {
                    let (xv, yv, cxv, cyv) = virtual_screen();
                    *ORIGIN.lock().unwrap() = (xv, yv);
                    let _ = SetWindowPos(hwnd, HWND_TOPMOST, xv, yv, cxv, cyv, SWP_NOACTIVATE);
                    let _ = ShowWindow(hwnd, SW_SHOWNOACTIVATE);
                }
                let _ = InvalidateRect(hwnd, None, true);
            } else if SHOWN.swap(false, Ordering::SeqCst) {
                let _ = ShowWindow(hwnd, SW_HIDE);
            }
            LRESULT(0)
        }
        WM_PAINT => {
            paint(hwnd);
            LRESULT(0)
        }
        _ => DefWindowProcW(hwnd, msg, wparam, lparam),
    }
}

unsafe fn paint(hwnd: HWND) {
    let mut ps = PAINTSTRUCT::default();
    let hdc = BeginPaint(hwnd, &mut ps);

    let mut rect = RECT::default();
    let _ = GetClientRect(hwnd, &mut rect);
    let bg = CreateSolidBrush(colorkey());
    FillRect(hdc, &rect, bg);
    let _ = DeleteObject(HGDIOBJ(bg.0));

    let pts = POINTS.lock().unwrap().clone();
    if pts.len() >= 2 {
        let (ox, oy) = *ORIGIN.lock().unwrap();
        let pen = CreatePen(PS_SOLID, 3, trail_color());
        let old = SelectObject(hdc, HGDIOBJ(pen.0));
        let _ = MoveToEx(hdc, pts[0].0 - ox, pts[0].1 - oy, None);
        for p in &pts[1..] {
            let _ = LineTo(hdc, p.0 - ox, p.1 - oy);
        }
        SelectObject(hdc, old);
        let _ = DeleteObject(HGDIOBJ(pen.0));
    }

    let _ = EndPaint(hwnd, &ps);
}
