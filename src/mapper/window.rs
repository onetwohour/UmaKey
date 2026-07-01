//! WindowHandler 이식: 게임 창 탐색·활성화·위치 조회.

use std::thread;
use std::time::Duration;
use windows::Win32::Foundation::{BOOL, HWND, LPARAM, POINT, RECT};
use windows::Win32::Graphics::Gdi::ClientToScreen;
use windows::Win32::System::Diagnostics::ToolHelp::{
    CreateToolhelp32Snapshot, Process32FirstW, Process32NextW, PROCESSENTRY32W, TH32CS_SNAPPROCESS,
};
use windows::Win32::UI::Input::KeyboardAndMouse::{keybd_event, KEYEVENTF_KEYUP, VK_MENU};
use windows::Win32::UI::WindowsAndMessaging::{
    EnumWindows, FindWindowW, GetForegroundWindow, GetWindowTextW, GetWindowThreadProcessId,
    IsIconic, IsWindowVisible, SetForegroundWindow, ShowWindow, SW_RESTORE,
};
use windows::Win32::UI::WindowsAndMessaging::GetClientRect;
use windows::core::PCWSTR;

use super::{from_wide, wide, SYNTH_EXTRA, TARGET_PROCESS};

pub struct WindowHandler {
    pub hwnd: HWND,
}

struct EnumCtx {
    title: String,
    pid: u32,
    found: Option<HWND>,
}

unsafe extern "system" fn enum_proc(hwnd: HWND, lparam: LPARAM) -> BOOL {
    let ctx = &mut *(lparam.0 as *mut EnumCtx);
    if IsWindowVisible(hwnd).as_bool() {
        let mut buf = [0u16; 512];
        let len = GetWindowTextW(hwnd, &mut buf);
        let text = from_wide(&buf[..len as usize]);
        if text == ctx.title {
            let mut pid = 0u32;
            GetWindowThreadProcessId(hwnd, Some(&mut pid));
            if pid == ctx.pid {
                ctx.found = Some(hwnd);
                return BOOL(0);
            }
        }
    }
    BOOL(1)
}

impl WindowHandler {
    pub fn new() -> Self {
        Self { hwnd: HWND(std::ptr::null_mut()) }
    }

    pub fn is_valid(&self) -> bool {
        !self.hwnd.0.is_null()
    }

    pub fn is_window_foreground(&self) -> bool {
        unsafe { self.hwnd == GetForegroundWindow() }
    }

    fn find_process_by_name(name: &str) -> Option<u32> {
        unsafe {
            let snap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0).ok()?;
            let mut entry = PROCESSENTRY32W {
                dwSize: std::mem::size_of::<PROCESSENTRY32W>() as u32,
                ..Default::default()
            };
            let mut result = None;
            if Process32FirstW(snap, &mut entry).is_ok() {
                loop {
                    if from_wide(&entry.szExeFile) == name {
                        result = Some(entry.th32ProcessID);
                        break;
                    }
                    if Process32NextW(snap, &mut entry).is_err() {
                        break;
                    }
                }
            }
            let _ = windows::Win32::Foundation::CloseHandle(snap);
            result
        }
    }

    pub fn update(&mut self, window_title: &str) {
        unsafe {
            let title_w = wide(window_title);
            self.hwnd = FindWindowW(PCWSTR::null(), PCWSTR(title_w.as_ptr())).unwrap_or(HWND(std::ptr::null_mut()));
            if !self.is_valid() {
                return;
            }
            let process = match Self::find_process_by_name(TARGET_PROCESS) {
                Some(p) => p,
                None => {
                    self.hwnd = HWND(std::ptr::null_mut());
                    return;
                }
            };

            let mut pid = 0u32;
            GetWindowThreadProcessId(self.hwnd, Some(&mut pid));
            if pid == process {
                return;
            }

            let mut ctx = EnumCtx { title: window_title.to_string(), pid: process, found: None };
            let _ = EnumWindows(Some(enum_proc), LPARAM(&mut ctx as *mut _ as isize));
            if let Some(h) = ctx.found {
                self.hwnd = h;
            }
        }
    }

    pub fn activate_window(&self) -> bool {
        unsafe {
            thread::sleep(Duration::from_millis(250));
            if IsIconic(self.hwnd).as_bool() {
                let _ = ShowWindow(self.hwnd, SW_RESTORE);
                true
            } else {
                keybd_event(VK_MENU.0 as u8, 0, Default::default(), SYNTH_EXTRA);
                keybd_event(VK_MENU.0 as u8, 0, KEYEVENTF_KEYUP, SYNTH_EXTRA);
                SetForegroundWindow(self.hwnd).as_bool()
            }
        }
    }

    /// (left, top, right, bottom) — 게임 클라이언트 영역의 스크린 좌표.
    pub fn get_window_position(&self) -> (i32, i32, i32, i32) {
        unsafe {
            let mut rect = RECT::default();
            let _ = GetClientRect(self.hwnd, &mut rect);
            let width = rect.right - rect.left;
            let height = rect.bottom - rect.top;
            let mut origin = POINT { x: 0, y: 0 };
            let _ = ClientToScreen(self.hwnd, &mut origin);
            (origin.x, origin.y, origin.x + width, origin.y + height)
        }
    }
}
