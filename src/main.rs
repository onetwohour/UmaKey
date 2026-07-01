#![windows_subsystem = "windows"]

use std::sync::OnceLock;

use windows::core::PCWSTR;
use windows::Win32::Foundation::{GetLastError, ERROR_ALREADY_EXISTS};
use windows::Win32::System::Threading::CreateMutexW;
use windows::Win32::UI::HiDpi::{SetProcessDpiAwareness, PROCESS_SYSTEM_DPI_AWARE};
use windows::Win32::UI::Shell::ShellExecuteW;
use windows::Win32::UI::WindowsAndMessaging::SW_HIDE;

use umakey::mapper::{self, AutoClicker};
use umakey::{effect, tray, update, updater};

const VERSION: &str = "v1.3.3";

static INSTANCE_MUTEX: OnceLock<usize> = OnceLock::new();

/// named Mutex로 단일 인스턴스를 보장. 이미 실행 중이면 true.
fn already_running() -> bool {
    let name = mapper::wide("UmaKey");
    unsafe {
        let handle = CreateMutexW(None, true, PCWSTR(name.as_ptr()));
        let exists = GetLastError() == ERROR_ALREADY_EXISTS;
        if let Ok(h) = handle {
            let _ = INSTANCE_MUTEX.set(h.0 as usize);
        }
        exists
    }
}

/// 현재 폴더를 Windows Defender 예외 경로로 등록(원본 동작 유지).
fn add_defender_exclusion() {
    let cwd = std::env::current_dir().unwrap_or_default();
    let cmd = format!("Add-MpPreference -ExclusionPath \"{}\"", cwd.display());
    let verb = mapper::wide("open");
    let file = mapper::wide("powershell.exe");
    let params = mapper::wide(&cmd);
    unsafe {
        ShellExecuteW(
            None,
            PCWSTR(verb.as_ptr()),
            PCWSTR(file.as_ptr()),
            PCWSTR(params.as_ptr()),
            PCWSTR::null(),
            SW_HIDE,
        );
    }
}

fn main() {
    if let Some(params) = updater::is_update_mode() {
        updater::run_update(params);
        return;
    }
    unsafe {
        let _ = SetProcessDpiAwareness(PROCESS_SYSTEM_DPI_AWARE);
    }
    if already_running() {
        std::process::exit(0);
    }
    add_defender_exclusion();

    let (download, release) = update::check_new_release("onetwohour", "UmaKey", VERSION);
    let (release_url, release_tag) = match &release {
        Some(r) => update::release_info(r),
        None => (None, None),
    };
    if download {
        tray::message_box(
            "알림",
            &format!("새로운 업데이트 : {}", release_tag.unwrap_or_default()),
        );
    }

    let clicker = AutoClicker::new();
    clicker.install();
    effect::start();

    tray::run(clicker, download, release_url, VERSION);
}
