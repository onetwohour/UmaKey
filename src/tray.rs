
use std::ffi::c_void;
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
use std::sync::{Arc, OnceLock};
use std::thread;
use std::time::Duration;

use windows::core::PCWSTR;
use windows::Win32::Foundation::{HWND, LPARAM, LRESULT, POINT, WPARAM};
use windows::Win32::System::LibraryLoader::GetModuleHandleW;
use windows::Win32::UI::Shell::{
    Shell_NotifyIconW, NIF_ICON, NIF_INFO, NIF_MESSAGE, NIF_TIP, NIM_ADD, NIM_DELETE, NIM_MODIFY,
    NOTIFYICONDATAW,
};
use windows::Win32::UI::WindowsAndMessaging::{
    AppendMenuW, CreateIconFromResourceEx, CreatePopupMenu, CreateWindowExW, DefWindowProcW,
    DestroyMenu, DispatchMessageW, GetCursorPos, GetMessageW, LookupIconIdFromDirectoryEx,
    PostMessageW, PostQuitMessage, RegisterClassW, SetForegroundWindow, TrackPopupMenu,
    TranslateMessage, HICON, LR_DEFAULTCOLOR, MB_ICONWARNING, MB_TOPMOST, MF_GRAYED, MF_STRING,
    MSG, TPM_LEFTALIGN, TPM_RIGHTBUTTON, WM_APP, WM_COMMAND, WM_DESTROY, WM_LBUTTONUP,
    WM_RBUTTONUP, WNDCLASSW, WS_OVERLAPPED,
};
use windows::Win32::UI::WindowsAndMessaging::MessageBoxW;

use crate::mapper::{wide, AutoClicker};

const WM_TRAYICON: u32 = WM_APP + 1;
const TRAY_UID: u32 = 1;

const ID_TOGGLE: usize = 1;
const ID_UPDATE: usize = 3;
const ID_EXIT: usize = 4;
const ID_SETTINGS: usize = 5;

static APP: OnceLock<App> = OnceLock::new();

fn app() -> &'static App {
    APP.get().expect("app not initialized")
}

pub struct App {
    clicker: Arc<AutoClicker>,
    running: AtomicBool,
    download: bool,
    release_url: Option<String>,
    version: &'static str,
    hwnd: AtomicUsize,
}

impl App {
    fn hwnd(&self) -> HWND {
        HWND(self.hwnd.load(Ordering::SeqCst) as *mut c_void)
    }

    fn action(&self) {
        let now = !self.running.load(Ordering::SeqCst);
        self.running.store(now, Ordering::SeqCst);
        let c = self.clicker.clone();
        thread::spawn(move || c.toggle());
        if now {
            thread::spawn(error_check);
        }
    }

    fn upgrade(&self) {
        message_box("Warning", "업데이트를 위해 프로그램이 재시작됩니다.");
        let url = self.release_url.clone().unwrap_or_default();
        let install_dir = std::env::current_exe()
            .ok()
            .and_then(|p| p.parent().map(|d| d.to_string_lossy().to_string()))
            .unwrap_or_default();
        crate::updater::launch_update(url, install_dir, vec!["config.json".to_string()]);
        std::process::exit(0);
    }

    fn open_settings(&self) {
        crate::settings_ui::open();
    }

    fn exit(&self) {
        self.clicker.destroy();
        remove_icon(self.hwnd());
        std::process::exit(0);
    }
}

fn error_check() {
    let app = app();
    let mut error = false;
    while app.running.load(Ordering::SeqCst) && !error {
        if app.clicker.error_occurred() {
            error = true;
        }
        thread::sleep(Duration::from_millis(100));
    }
    if error {
        let msg = app.clicker.error_message().unwrap_or_default();
        notify(app.hwnd(), &msg, "Error");
        app.exit();
    }
}

pub fn run(
    clicker: Arc<AutoClicker>,
    download: bool,
    release_url: Option<String>,
    version: &'static str,
) {
    let state = App {
        clicker,
        running: AtomicBool::new(false),
        download,
        release_url,
        version,
        hwnd: AtomicUsize::new(0),
    };
    let _ = APP.set(state);

    unsafe {
        let hinstance = GetModuleHandleW(PCWSTR::null()).unwrap_or_default();
        let class_name = wide("UmaKeyTray");
        let wc = WNDCLASSW {
            lpfnWndProc: Some(wndproc),
            hInstance: hinstance.into(),
            lpszClassName: PCWSTR(class_name.as_ptr()),
            ..Default::default()
        };
        RegisterClassW(&wc);

        let hwnd = CreateWindowExW(
            Default::default(),
            PCWSTR(class_name.as_ptr()),
            PCWSTR(wide("UmaKey").as_ptr()),
            WS_OVERLAPPED,
            0,
            0,
            0,
            0,
            None,
            None,
            hinstance,
            None,
        )
        .expect("create tray window");
        app().hwnd.store(hwnd.0 as usize, Ordering::SeqCst);

        add_icon(hwnd);
        app().action();

        let mut msg = MSG::default();
        while GetMessageW(&mut msg, None, 0, 0).0 > 0 {
            let _ = TranslateMessage(&msg);
            DispatchMessageW(&msg);
        }
    }
}

unsafe extern "system" fn wndproc(
    hwnd: HWND,
    msg: u32,
    wparam: WPARAM,
    lparam: LPARAM,
) -> LRESULT {
    match msg {
        WM_TRAYICON => {
            let event = (lparam.0 as u32) & 0xffff;
            if event == WM_LBUTTONUP || event == WM_RBUTTONUP {
                show_menu(hwnd);
            }
            LRESULT(0)
        }
        WM_COMMAND => {
            let id = wparam.0 & 0xffff;
            match id {
                ID_TOGGLE => app().action(),
                ID_SETTINGS => app().open_settings(),
                ID_UPDATE => app().upgrade(),
                ID_EXIT => app().exit(),
                _ => {}
            }
            LRESULT(0)
        }
        WM_DESTROY => {
            PostQuitMessage(0);
            LRESULT(0)
        }
        _ => DefWindowProcW(hwnd, msg, wparam, lparam),
    }
}

unsafe fn show_menu(hwnd: HWND) {
    let a = app();
    let menu = match CreatePopupMenu() {
        Ok(m) => m,
        Err(_) => return,
    };

    let version = wide(a.version);
    let _ = AppendMenuW(menu, MF_STRING | MF_GRAYED, 0, PCWSTR(version.as_ptr()));

    let toggle_label = wide(if a.running.load(Ordering::SeqCst) { "중지" } else { "시작" });
    let _ = AppendMenuW(menu, MF_STRING, ID_TOGGLE, PCWSTR(toggle_label.as_ptr()));

    let settings_label = wide("설정");
    let _ = AppendMenuW(menu, MF_STRING, ID_SETTINGS, PCWSTR(settings_label.as_ptr()));

    let update_label = wide("업데이트");
    let update_flags = if a.download { MF_STRING } else { MF_STRING | MF_GRAYED };
    let _ = AppendMenuW(menu, update_flags, ID_UPDATE, PCWSTR(update_label.as_ptr()));

    let exit_label = wide("종료");
    let _ = AppendMenuW(menu, MF_STRING, ID_EXIT, PCWSTR(exit_label.as_ptr()));

    let mut pt = POINT { x: 0, y: 0 };
    let _ = GetCursorPos(&mut pt);
    let _ = SetForegroundWindow(hwnd);
    let _ = TrackPopupMenu(
        menu,
        TPM_LEFTALIGN | TPM_RIGHTBUTTON,
        pt.x,
        pt.y,
        0,
        hwnd,
        None,
    );
    let _ = PostMessageW(hwnd, 0, WPARAM(0), LPARAM(0));
    let _ = DestroyMenu(menu);
}

static ICON_BYTES: &[u8] = include_bytes!("../UmaKey.ico");

fn load_icon() -> HICON {
    unsafe {
        let offset = LookupIconIdFromDirectoryEx(ICON_BYTES.as_ptr(), true, 0, 0, LR_DEFAULTCOLOR);
        if offset <= 0 {
            return HICON(std::ptr::null_mut());
        }
        let image = &ICON_BYTES[offset as usize..];
        CreateIconFromResourceEx(image, true, 0x0003_0000, 0, 0, LR_DEFAULTCOLOR)
            .unwrap_or(HICON(std::ptr::null_mut()))
    }
}

fn base_nid(hwnd: HWND) -> NOTIFYICONDATAW {
    NOTIFYICONDATAW {
        cbSize: std::mem::size_of::<NOTIFYICONDATAW>() as u32,
        hWnd: hwnd,
        uID: TRAY_UID,
        ..Default::default()
    }
}

fn fill_wide(dst: &mut [u16], src: &str) {
    let s: Vec<u16> = src.encode_utf16().collect();
    let n = s.len().min(dst.len().saturating_sub(1));
    dst[..n].copy_from_slice(&s[..n]);
    dst[n] = 0;
}

fn add_icon(hwnd: HWND) {
    let mut nid = base_nid(hwnd);
    nid.uFlags = NIF_ICON | NIF_MESSAGE | NIF_TIP;
    nid.uCallbackMessage = WM_TRAYICON;
    nid.hIcon = load_icon();
    fill_wide(&mut nid.szTip, "UmaKey");
    unsafe {
        let _ = Shell_NotifyIconW(NIM_ADD, &nid);
    }
}

fn remove_icon(hwnd: HWND) {
    let nid = base_nid(hwnd);
    unsafe {
        let _ = Shell_NotifyIconW(NIM_DELETE, &nid);
    }
}

fn notify(hwnd: HWND, message: &str, title: &str) {
    let mut nid = base_nid(hwnd);
    nid.uFlags = NIF_INFO;
    fill_wide(&mut nid.szInfo, message);
    fill_wide(&mut nid.szInfoTitle, title);
    unsafe {
        let _ = Shell_NotifyIconW(NIM_MODIFY, &nid);
    }
}

pub fn message_box(title: &str, message: &str) {
    let text = wide(message);
    let caption = wide(title);
    unsafe {
        MessageBoxW(
            None,
            PCWSTR(text.as_ptr()),
            PCWSTR(caption.as_ptr()),
            MB_ICONWARNING | MB_TOPMOST,
        );
    }
}
