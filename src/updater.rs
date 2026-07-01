
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

pub fn is_update_mode() -> Option<UpdateParams> {
    let exe = std::env::current_exe().ok()?;
    let marker = exe.parent()?.join(MARKER);
    let text = fs::read_to_string(marker).ok()?;
    serde_json::from_str(&text).ok()
}

pub fn cleanup_legacy() {
    if let Some(dir) = std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|d| d.to_path_buf()))
    {
        cleanup_dir(&dir);
    }
}

fn cleanup_dir(dir: &Path) {
    if let Ok(entries) = fs::read_dir(dir) {
        for entry in entries.flatten() {
            let path = entry.path();
            if path.is_file() && is_python_leftover(&entry.file_name().to_string_lossy()) {
                let _ = fs::remove_file(&path);
            }
        }
    }
    for d in ["_internal", "tk", "update"] {
        let _ = fs::remove_dir_all(dir.join(d));
    }
}

fn is_python_leftover(name: &str) -> bool {
    let n = name.to_ascii_lowercase();
    n.ends_with(".pyd")
        || (n.starts_with("python3") && n.ends_with(".dll"))
        || n == "launcher.exe"
        || n == "tcl86t.dll"
        || n == "tk86t.dll"
        || (n.starts_with("libcrypto") && n.ends_with(".dll"))
        || (n.starts_with("libssl") && n.ends_with(".dll"))
        || (n.starts_with("libffi") && n.ends_with(".dll"))
        || (n.starts_with("vcruntime") && n.ends_with(".dll"))
        || n == "ucrtbase.dll"
        || (n.starts_with("api-ms-win") && n.ends_with(".dll"))
}

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

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;
    use std::net::TcpListener;

    fn tmp(name: &str) -> PathBuf {
        let d = std::env::temp_dir().join(format!("umakey_test_{}_{}", std::process::id(), name));
        let _ = fs::remove_dir_all(&d);
        fs::create_dir_all(&d).unwrap();
        d
    }

    fn make_zip(entries: &[(&str, &[u8])]) -> Vec<u8> {
        let mut buf = Vec::new();
        {
            let mut w = zip::ZipWriter::new(io::Cursor::new(&mut buf));
            let opts = zip::write::SimpleFileOptions::default();
            for (name, content) in entries {
                w.start_file(*name, opts).unwrap();
                w.write_all(content).unwrap();
            }
            w.finish().unwrap();
        }
        buf
    }

    fn serve_zip(zip: Vec<u8>) -> u16 {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let port = listener.local_addr().unwrap().port();
        std::thread::spawn(move || {
            for stream in listener.incoming() {
                let mut stream = match stream {
                    Ok(s) => s,
                    Err(_) => break,
                };
                let mut buf = [0u8; 2048];
                let _ = std::io::Read::read(&mut stream, &mut buf);
                let header = format!(
                    "HTTP/1.1 200 OK\r\nContent-Length: {}\r\nContent-Type: application/zip\r\nConnection: close\r\n\r\n",
                    zip.len()
                );
                let _ = stream.write_all(header.as_bytes());
                let _ = stream.write_all(&zip);
                let _ = stream.flush();
            }
        });
        port
    }

    #[test]
    fn hash_matches_known_sha256() {
        let d = tmp("hash");
        let f = d.join("a.txt");
        fs::write(&f, b"hello").unwrap();
        assert_eq!(
            file_hash(&f).unwrap(),
            "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
        );
        let _ = fs::remove_dir_all(&d);
    }

    #[test]
    fn downloads_and_extracts_zip() {
        let zip = make_zip(&[("umakey.exe", b"NEW EXE"), ("config.json", b"{\"a\":1}")]);
        let port = serve_zip(zip);
        let dst = tmp("dl");
        download_and_extract(&format!("http://127.0.0.1:{port}/Umakey.zip"), &dst).unwrap();
        assert_eq!(fs::read(dst.join("umakey.exe")).unwrap(), b"NEW EXE");
        assert_eq!(fs::read_to_string(dst.join("config.json")).unwrap(), "{\"a\":1}");
        let _ = fs::remove_dir_all(&dst);
    }

    #[test]
    fn apply_preserves_config_and_updates_rest() {
        let install = tmp("apply_install");
        let payload = tmp("apply_payload");
        fs::write(install.join("config.json"), b"USER CONFIG").unwrap();
        fs::write(install.join("umakey.exe"), b"OLD EXE").unwrap();
        fs::write(install.join("same.txt"), b"SAME").unwrap();
        fs::write(payload.join("config.json"), b"DEFAULT CONFIG").unwrap();
        fs::write(payload.join("umakey.exe"), b"NEW EXE").unwrap();
        fs::write(payload.join("same.txt"), b"SAME").unwrap();
        fs::write(payload.join("new.txt"), b"NEW FILE").unwrap();

        apply_files(&install, &payload, &["config.json".to_string()]).unwrap();

        assert_eq!(fs::read(install.join("config.json")).unwrap(), b"USER CONFIG");
        assert_eq!(fs::read(install.join("umakey.exe")).unwrap(), b"NEW EXE");
        assert_eq!(fs::read(install.join("same.txt")).unwrap(), b"SAME");
        assert_eq!(fs::read(install.join("new.txt")).unwrap(), b"NEW FILE");
        let _ = fs::remove_dir_all(&install);
        let _ = fs::remove_dir_all(&payload);
    }

    #[test]
    fn removes_dirs_absent_from_payload() {
        let install = tmp("stale_install");
        let payload = tmp("stale_payload");
        fs::create_dir_all(install.join("keep")).unwrap();
        fs::create_dir_all(install.join("stale")).unwrap();
        fs::write(install.join("stale").join("x.txt"), b"x").unwrap();
        fs::create_dir_all(payload.join("keep")).unwrap();

        remove_stale_dirs(&install, &payload);

        assert!(install.join("keep").exists());
        assert!(!install.join("stale").exists());
        let _ = fs::remove_dir_all(&install);
        let _ = fs::remove_dir_all(&payload);
    }

    #[test]
    fn full_download_to_apply_flow() {
        let zip = make_zip(&[
            ("umakey.exe", b"NEW EXE"),
            ("config.json", b"DEFAULT"),
            ("data/lib.dat", b"NEWLIB"),
        ]);
        let port = serve_zip(zip);
        let install = tmp("flow_install");
        let payload = tmp("flow_payload");
        fs::write(install.join("config.json"), b"USER CONFIG").unwrap();
        fs::write(install.join("umakey.exe"), b"OLD EXE").unwrap();

        download_and_extract(&format!("http://127.0.0.1:{port}/x.zip"), &payload).unwrap();
        remove_stale_dirs(&install, &payload);
        apply_files(&install, &payload, &["config.json".to_string()]).unwrap();

        assert_eq!(fs::read(install.join("config.json")).unwrap(), b"USER CONFIG");
        assert_eq!(fs::read(install.join("umakey.exe")).unwrap(), b"NEW EXE");
        assert_eq!(fs::read(install.join("data").join("lib.dat")).unwrap(), b"NEWLIB");
        let _ = fs::remove_dir_all(&install);
        let _ = fs::remove_dir_all(&payload);
    }

    #[test]
    fn cleanup_removes_python_leftovers_keeps_rest() {
        let d = tmp("cleanup");
        fs::write(d.join("UmaKey.exe"), b"RUST").unwrap();
        fs::write(d.join("config.json"), b"cfg").unwrap();
        fs::write(d.join("vcruntime140.dll"), b"vc").unwrap();
        fs::write(d.join("vcruntime140_1.dll"), b"vc").unwrap();
        fs::write(d.join("ucrtbase.dll"), b"u").unwrap();
        fs::write(d.join("api-ms-win-crt-runtime-l1-1-0.dll"), b"a").unwrap();
        fs::write(d.join("python311.dll"), b"x").unwrap();
        fs::write(d.join("win32api.pyd"), b"x").unwrap();
        fs::write(d.join("Launcher.exe"), b"x").unwrap();
        fs::write(d.join("libcrypto-3.dll"), b"x").unwrap();
        fs::create_dir_all(d.join("_internal")).unwrap();
        fs::write(d.join("_internal").join("UmaKey.ico"), b"x").unwrap();
        fs::create_dir_all(d.join("update")).unwrap();
        fs::write(d.join("update").join("update.exe"), b"x").unwrap();

        cleanup_dir(&d);

        assert!(d.join("UmaKey.exe").exists());
        assert!(d.join("config.json").exists());
        assert!(!d.join("vcruntime140.dll").exists());
        assert!(!d.join("vcruntime140_1.dll").exists());
        assert!(!d.join("ucrtbase.dll").exists());
        assert!(!d.join("api-ms-win-crt-runtime-l1-1-0.dll").exists());
        assert!(!d.join("python311.dll").exists());
        assert!(!d.join("win32api.pyd").exists());
        assert!(!d.join("Launcher.exe").exists());
        assert!(!d.join("libcrypto-3.dll").exists());
        assert!(!d.join("_internal").exists());
        assert!(!d.join("update").exists());
        let _ = fs::remove_dir_all(&d);
    }

    #[test]
    #[ignore]
    fn real_github_release_download_and_apply() {
        let (download, release) = crate::update::check_new_release("onetwohour", "UmaKey", "v0.0.0");
        assert!(download, "v0.0.0보다 최신 릴리스가 있어야 함");
        let release = release.unwrap();
        let (url, tag) = crate::update::release_info(&release);
        let url = url.expect("에셋 URL");
        eprintln!("[release] tag={:?}", tag);
        eprintln!("[asset]   {url}");

        let payload = tmp("real_payload");
        download_and_extract(&url, &payload).unwrap();

        let mut names: Vec<String> = walk_files(&payload)
            .iter()
            .filter_map(|p| p.strip_prefix(&payload).ok().map(|r| r.to_string_lossy().replace('\\', "/")))
            .collect();
        names.sort();
        eprintln!("[extracted] {} files", names.len());
        for n in &names {
            eprintln!("  {n}");
        }

        let install = tmp("real_install");
        fs::write(install.join("config.json"), b"USER CONFIG").unwrap();
        remove_stale_dirs(&install, &payload);
        apply_files(&install, &payload, &["config.json".to_string()]).unwrap();

        assert_eq!(
            fs::read(install.join("config.json")).unwrap(),
            b"USER CONFIG",
            "config.json이 보존돼야 함"
        );
        let applied = walk_files(&install).len();
        eprintln!("[install] 적용 후 파일 {applied}개");
        assert!(applied > 1, "설치 폴더에 파일이 적용돼야 함");

        let _ = fs::remove_dir_all(&payload);
        let _ = fs::remove_dir_all(&install);
    }
}
