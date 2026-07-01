
use std::sync::atomic::Ordering;
use std::thread;
use std::time::Duration;
use windows::core::PCWSTR;
use windows::Win32::Foundation::{HINSTANCE, HWND, LPARAM, LRESULT, WPARAM};
use windows::Win32::System::LibraryLoader::GetModuleHandleW;
use windows::Win32::UI::WindowsAndMessaging::{
    CallNextHookEx, DispatchMessageW, PeekMessageW, SetWindowsHookExW, TranslateMessage,
    UnhookWindowsHookEx, HHOOK, KBDLLHOOKSTRUCT, MSG, PM_REMOVE, WH_KEYBOARD_LL, WM_KEYDOWN,
};

use super::{engine, AutoClicker};

pub fn start() {
    let eng = match engine() {
        Some(e) => e.clone(),
        None => return,
    };
    if eng.hook_handle.load(Ordering::SeqCst) != 0 {
        return;
    }
    eng.hook_running.store(true, Ordering::SeqCst);
    thread::spawn(move || unsafe {
        let hmod = GetModuleHandleW(PCWSTR::null()).unwrap_or_default();
        let hook = SetWindowsHookExW(WH_KEYBOARD_LL, Some(hook_proc), HINSTANCE(hmod.0), 0);
        let hook = match hook {
            Ok(h) => h,
            Err(_) => {
                eng.hook_running.store(false, Ordering::SeqCst);
                return;
            }
        };
        eng.hook_handle.store(hook.0 as usize, Ordering::SeqCst);
        message_loop(&eng);
    });
}

unsafe fn message_loop(eng: &AutoClicker) {
    let mut msg = MSG::default();
    while eng.hook_running.load(Ordering::SeqCst) {
        if PeekMessageW(&mut msg, HWND(std::ptr::null_mut()), 0, 0, PM_REMOVE).as_bool() {
            let _ = TranslateMessage(&msg);
            DispatchMessageW(&msg);
        }
        thread::sleep(Duration::from_millis(10));
    }
}

pub fn stop() {
    let eng = match engine() {
        Some(e) => e,
        None => return,
    };
    let h = eng.hook_handle.swap(0, Ordering::SeqCst);
    if h != 0 {
        unsafe {
            let _ = UnhookWindowsHookEx(HHOOK(h as *mut _));
        }
    }
    eng.hook_running.store(false, Ordering::SeqCst);
}

unsafe extern "system" fn hook_proc(code: i32, wparam: WPARAM, lparam: LPARAM) -> LRESULT {
    if code >= 0 && wparam.0 == WM_KEYDOWN as usize {
        let kb = &*(lparam.0 as *const KBDLLHOOKSTRUCT);
        let vk = kb.vkCode;
        let extra = kb.dwExtraInfo;
        if let Some(eng) = engine() {
            if eng.enabled.load(Ordering::SeqCst) && extra == 0 && eng.is_mapped(vk) {
                if !eng.hook_lock.swap(true, Ordering::SeqCst) {
                    let e = eng.clone();
                    thread::spawn(move || {
                        e.on_keyboard_event(vk);
                        e.hook_lock.store(false, Ordering::SeqCst);
                    });
                }
                return LRESULT(1);
            }
        }
    }
    CallNextHookEx(HHOOK(std::ptr::null_mut()), code, wparam, lparam)
}
