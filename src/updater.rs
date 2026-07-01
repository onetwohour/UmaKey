//! download.py 이식 + 자기 교체. 별도 exe 없이 umakey.exe 하나로 업데이트한다.
//! 업데이트 시 자신을 %TEMP%로 복사해 실행하고, 복사본 옆 마커 파일로 모드를 판별한다.

use std::fs;
use std::io::{self, Read};
use std::path::{Path, PathBuf};
use std::process::Command;

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use windows::core::PCWSTR;
use windows::Win32::UI::Shell::ShellExecuteW;
use windows::Win32::UI::WindowsAndMessaging::{
    MessageBoxW, MB_ICONWARNING, MB_TOPMOST, SW_HIDE,
};

use crate::mapper::wide;

const MARKER: &str = "umakey_update.json";

#[derive(Serialize, Deserialize)]
pub struct UpdateParams {
    zip_url: String,
    install_dir: String,
    exclude: Vec<String>,
}

/// 현재 exe 옆에 마커가 있으면 업데이트 모드로 간주하고 파라미터를 읽는다.
pub fn is_update_mode() -> Option<UpdateParams> {
    let exe = std::env::current_exe().ok()?;
    let marker = exe.parent()?.join(MARKER);
    let text = fs::read_to_string(marker).ok()?;
    serde_json::from_str(&text).ok()
}

/// 자신을 %TEMP%로 복사하고 마커를 남긴 뒤 실행한다(호출한 쪽은 종료해야 함).
pub fn launch_update(zip_url: String, install_dir: String, exclude: Vec<String>) {
    let current = match std::env::current_exe() {
        Ok(p) => p,
        Err(_) => return,
    };
    let file_name = match current.file_name() {
        Some(n) => n.to_owned(),
        None => return,
    };
    let temp = std::env::temp_dir().join(format!("umakey_update_{}", std::process::id()));
    if fs::create_dir_all(&temp).is_err() {
        return;
    }
    let dst_exe = temp.join(&file_name);
    if fs::copy(&current, &dst_exe).is_err() {
        return;
    }
    let params = UpdateParams { zip_url, install_dir, exclude };
    if let Ok(text) = serde_json::to_string(&params) {
        let _ = fs::write(temp.join(MARKER), text);
    }
    let _ = Command::new(&dst_exe).current_dir(&temp).spawn();
}

/// 업데이트 모드 본체: 다운로드→적용→재실행.
pub fn run_update(params: UpdateParams) {
    let install_dir = PathBuf::from(&params.install_dir);
    let payload = std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|d| d.join("payload")))
        .unwrap_or_else(|| std::env::temp_dir().join("umakey_payload"));

    if let Err(e) = apply(&params, &install_dir, &payload) {
        message_box("Error", &format!("업데이트 실패: {e}"));
        return;
    }

    message_box("알림", "업데이트 완료");
    relaunch(&install_dir);
    let _ = fs::remove_dir_all(&payload);
}

fn apply(params: &UpdateParams, install_dir: &Path, payload: &Path) -> io::Result<()> {
    let _ = fs::create_dir_all(payload);
    defender_exclude(payload);

    download_and_extract(&params.zip_url, payload)?;
    remove_stale_dirs(install_dir, payload);
    apply_files(install_dir, payload, &params.exclude)?;

    defender_remove(payload);
    Ok(())
}

fn download_and_extract(url: &str, dst: &Path) -> io::Result<()> {
    let resp = ureq::get(url)
        .set("User-Agent", "UmaKey")
        .call()
        .map_err(|e| io::Error::new(io::ErrorKind::Other, e.to_string()))?;
    let mut bytes = Vec::new();
    resp.into_reader().read_to_end(&mut bytes)?;

    let cursor = io::Cursor::new(bytes);
    let mut archive = zip::ZipArchive::new(cursor)
        .map_err(|e| io::Error::new(io::ErrorKind::Other, e.to_string()))?;
    for i in 0..archive.len() {
        let mut file = archive
            .by_index(i)
            .map_err(|e| io::Error::new(io::ErrorKind::Other, e.to_string()))?;
        let rel = match file.enclosed_name() {
            Some(p) => p.to_path_buf(),
            None => continue,
        };
        let out = dst.join(rel);
        if file.is_dir() {
            fs::create_dir_all(&out)?;
        } else {
            if let Some(parent) = out.parent() {
                fs::create_dir_all(parent)?;
            }
            let mut o = fs::File::create(&out)?;
            io::copy(&mut file, &mut o)?;
        }
    }
    Ok(())
}

fn remove_stale_dirs(install: &Path, payload: &Path) {
    for dir in walk_dirs(install) {
        let rel = match dir.strip_prefix(install) {
            Ok(r) => r,
            Err(_) => continue,
        };
        if !payload.join(rel).exists() {
            let _ = fs::remove_dir_all(&dir);
        }
    }
}

fn apply_files(install: &Path, payload: &Path, exclude: &[String]) -> io::Result<()> {
    for src in walk_files(payload) {
        let rel = match src.strip_prefix(payload) {
            Ok(r) => r,
            Err(_) => continue,
        };
        let dst = install.join(rel);
        let file_name = src
            .file_name()
            .map(|n| n.to_string_lossy().to_string())
            .unwrap_or_default();

        if exclude.iter().any(|e| e == &file_name) && dst.is_file() {
            continue;
        }
        if dst.is_file() && file_hash(&src)? == file_hash(&dst)? {
            continue;
        }
        if let Some(parent) = dst.parent() {
            fs::create_dir_all(parent)?;
        }
        fs::copy(&src, &dst)?;
    }
    Ok(())
}

fn walk_dirs(root: &Path) -> Vec<PathBuf> {
    let mut result = Vec::new();
    let mut stack = vec![root.to_path_buf()];
    while let Some(dir) = stack.pop() {
        if let Ok(entries) = fs::read_dir(&dir) {
            for entry in entries.flatten() {
                let path = entry.path();
                if path.is_dir() {
                    result.push(path.clone());
                    stack.push(path);
                }
            }
        }
    }
    result
}

fn walk_files(root: &Path) -> Vec<PathBuf> {
    let mut result = Vec::new();
    let mut stack = vec![root.to_path_buf()];
    while let Some(dir) = stack.pop() {
        if let Ok(entries) = fs::read_dir(&dir) {
            for entry in entries.flatten() {
                let path = entry.path();
                if path.is_dir() {
                    stack.push(path);
                } else {
                    result.push(path);
                }
            }
        }
    }
    result
}

fn file_hash(path: &Path) -> io::Result<String> {
    let mut file = fs::File::open(path)?;
    let mut hasher = Sha256::new();
    let mut buf = [0u8; 65536];
    loop {
        let n = file.read(&mut buf)?;
        if n == 0 {
            break;
        }
        hasher.update(&buf[..n]);
    }
    Ok(format!("{:x}", hasher.finalize()))
}

fn relaunch(install_dir: &Path) {
    let exe = install_dir.join("umakey.exe");
    let _ = Command::new(&exe).current_dir(install_dir).spawn();
}

fn defender_exclude(path: &Path) {
    run_powershell(&format!("Add-MpPreference -ExclusionPath \"{}\"", path.display()));
}

fn defender_remove(path: &Path) {
    run_powershell(&format!("Remove-MpPreference -ExclusionPath \"{}\"", path.display()));
}

fn run_powershell(command: &str) {
    let verb = wide("open");
    let file = wide("powershell.exe");
    let params = wide(command);
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

fn message_box(title: &str, message: &str) {
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
