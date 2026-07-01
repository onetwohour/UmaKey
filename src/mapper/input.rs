//! 마우스·키보드 합성 프리미티브 (press_key/click/keyboard 이식).

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

/// 원래 눌린 키를 게임으로 통과시킨다. Ctrl/Shift 상태를 함께 재현한다.
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

/// 매핑된 키를 게임에 입력한다. 원본의 누락된 self.keyboard를 대체한다.
pub fn keyboard(code: u32) {
    unsafe {
        keybd_event(code as u8, 0, Default::default(), SYNTH_EXTRA);
        keybd_event(code as u8, 0, KEYEVENTF_KEYUP, SYNTH_EXTRA);
    }
}
