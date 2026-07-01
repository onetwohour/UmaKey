
use windows::Win32::UI::Input::KeyboardAndMouse::{
    keybd_event, mouse_event, GetKeyState, KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP,
    MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP, VK_CONTROL, VK_SHIFT,
};
use windows::Win32::UI::WindowsAndMessaging::{GetCursorPos, SetCursorPos};
use windows::Win32::Foundation::POINT;

use super::SYNTH_EXTRA;

pub fn get_cursor_pos() -> (i32, i32) {
    unsafe {
        let mut p = POINT { x: 0, y: 0 };
        let _ = GetCursorPos(&mut p);
        (p.x, p.y)
    }
}

pub fn click(x: i32, y: i32) {
    unsafe {
        let _ = SetCursorPos(x, y);
        mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0);
        mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0);
    }
}

pub fn set_cursor_pos(x: i32, y: i32) {
    unsafe {
        let _ = SetCursorPos(x, y);
    }
}

pub fn mouse_left_down() {
    unsafe { mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0) }
}

pub fn mouse_left_up() {
    unsafe { mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0) }
}

pub fn press_key(code: u32) {
    unsafe {
        let control = GetKeyState(VK_CONTROL.0 as i32) < 0;
        let shift = GetKeyState(VK_SHIFT.0 as i32) < 0;
        if control {
            keybd_event(VK_CONTROL.0 as u8, 0, KEYEVENTF_EXTENDEDKEY, SYNTH_EXTRA);
        }
        if shift {
            keybd_event(VK_SHIFT.0 as u8, 0, KEYEVENTF_EXTENDEDKEY, SYNTH_EXTRA);
        }
        keybd_event(code as u8, 0, Default::default(), SYNTH_EXTRA);
        if control {
            keybd_event(
                VK_CONTROL.0 as u8,
                0,
                KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP,
                SYNTH_EXTRA,
            );
        }
        if shift {
            keybd_event(
                VK_SHIFT.0 as u8,
                0,
                KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP,
                SYNTH_EXTRA,
            );
        }
    }
}

pub fn keyboard(code: u32) {
    unsafe {
        keybd_event(code as u8, 0, Default::default(), SYNTH_EXTRA);
        keybd_event(code as u8, 0, KEYEVENTF_KEYUP, SYNTH_EXTRA);
    }
}
