
use std::sync::atomic::{AtomicBool, Ordering};
use std::thread;
use std::time::Duration;

use serde_json::Value;
use tao::dpi::LogicalSize;
use tao::event::{Event, WindowEvent};
use tao::event_loop::{ControlFlow, EventLoopBuilder, EventLoopProxy};
use tao::platform::run_return::EventLoopExtRunReturn;
use tao::platform::windows::EventLoopBuilderExtWindows;
use tao::window::WindowBuilder;
use wry::{WebView, WebViewBuilder};

use windows::core::PCWSTR;
use windows::Win32::Foundation::{CloseHandle, BOOL, HWND, LPARAM, POINT, RECT};
use windows::Win32::Graphics::Gdi::{ClientToScreen, GetDC, GetPixel, ReleaseDC};
use windows::Win32::System::Diagnostics::ToolHelp::{
    CreateToolhelp32Snapshot, Process32FirstW, Process32NextW, PROCESSENTRY32W, TH32CS_SNAPPROCESS,
};
use windows::Win32::UI::Input::KeyboardAndMouse::{GetAsyncKeyState, VK_LBUTTON};
use windows::Win32::UI::WindowsAndMessaging::{
    EnumWindows, FindWindowW, GetClientRect, GetCursorPos, GetWindowTextLengthW, GetWindowTextW,
    GetWindowThreadProcessId, IsWindowVisible,
};

use crate::mapper::{from_wide, wide};
use crate::settings::byte_to_key;

const TARGET_PROCESS: &str = "umamusume.exe";

const HTML: &str = include_str!("settings_ui.html");
const CONFIG_PATH: &str = "config.json";

static OPEN: AtomicBool = AtomicBool::new(false);

enum UserEvent {
    Ipc(String),
    Eval(String),
}

pub fn open() {
    if OPEN.swap(true, Ordering::SeqCst) {
        return;
    }
    thread::spawn(|| {
        run();
        OPEN.store(false, Ordering::SeqCst);
    });
}

fn run() {
    let mut builder = EventLoopBuilder::<UserEvent>::with_user_event();
    builder.with_any_thread(true);
    let mut event_loop = builder.build();
    let proxy = event_loop.create_proxy();

    let window = match WindowBuilder::new()
        .with_title("UmaKey 설정")
        .with_inner_size(LogicalSize::new(900.0, 720.0))
        .build(&event_loop)
    {
        Ok(w) => w,
        Err(_) => return,
    };

    let ipc_proxy = proxy.clone();
    let webview = match WebViewBuilder::new()
        .with_html(HTML)
        .with_ipc_handler(move |req| {
            let _ = ipc_proxy.send_event(UserEvent::Ipc(req.into_body()));
        })
        .build(&window)
    {
        Ok(w) => w,
        Err(_) => return,
    };

    event_loop.run_return(move |event, _, control_flow| {
        *control_flow = ControlFlow::Wait;
        match event {
            Event::UserEvent(UserEvent::Ipc(msg)) => handle_ipc(&webview, &proxy, &msg),
            Event::UserEvent(UserEvent::Eval(js)) => {
                let _ = webview.evaluate_script(&js);
            }
            Event::WindowEvent { event: WindowEvent::CloseRequested, .. } => {
                *control_flow = ControlFlow::Exit;
            }
            _ => {}
        }
    });
}

fn handle_ipc(webview: &WebView, proxy: &EventLoopProxy<UserEvent>, msg: &str) {
    let v: Value = match serde_json::from_str(msg) {
        Ok(v) => v,
        Err(_) => return,
    };
    match v.get("cmd").and_then(|c| c.as_str()).unwrap_or("") {
        "load" => {
            if let Some(eng) = crate::mapper::engine() {
                eng.reload();
            }
            let text = std::fs::read_to_string(CONFIG_PATH)
                .unwrap_or_else(|_| crate::settings::DEFAULT_CONFIG.to_string());
            let js = format!("window.__load({})", json_str(&text));
            let _ = webview.evaluate_script(&js);
        }
        "save" => {
            let ok = v
                .get("data")
                .and_then(|d| d.as_str())
                .map(|data| std::fs::write(CONFIG_PATH, data).is_ok())
                .unwrap_or(false);
            if ok {
                if let Some(eng) = crate::mapper::engine() {
                    eng.reload();
                }
            }
            let _ = webview.evaluate_script(&format!("window.__saved({ok})"));
        }
        "detect" => {
            let js = match detect_game() {
                Some((title, w, h)) => {
                    format!("window.__detected({}, {}, {})", json_str(&title), w, h)
                }
                None => "window.__detected(null, 0, 0)".to_string(),
            };
            let _ = webview.evaluate_script(&js);
        }
        "captureKey" | "captureSwitch" => {
            let token = token_of(&v);
            let p = proxy.clone();
            thread::spawn(move || {
                let name = capture_key();
                let _ = p.send_event(UserEvent::Eval(on_capture(&token, &json_str(&name))));
            });
        }
        "captureValue" => {
            let token = token_of(&v);
            let kind = str_of(&v, "kind");
            let title = str_of(&v, "title");
            let sx = v.get("sx").and_then(|n| n.as_i64()).unwrap_or(775) as i32;
            let sy = v.get("sy").and_then(|n| n.as_i64()).unwrap_or(1377) as i32;
            let p = proxy.clone();
            thread::spawn(move || {
                let value = match kind.as_str() {
                    "color" => Some(capture_color()),
                    "pos" => capture_pos(&title, sx, sy),
                    "drag" => capture_drag(&title, sx, sy),
                    _ => None,
                };
                let vjson = match value {
                    Some(s) => json_str(&s),
                    None => "null".to_string(),
                };
                let _ = p.send_event(UserEvent::Eval(on_capture(&token, &vjson)));
            });
        }
        _ => {}
    }
}

fn token_of(v: &Value) -> String {
    str_of(v, "token")
}

fn str_of(v: &Value, key: &str) -> String {
    v.get(key).and_then(|s| s.as_str()).unwrap_or("").to_string()
}

fn json_str(s: &str) -> String {
    serde_json::to_string(s).unwrap_or_else(|_| "\"\"".to_string())
}

fn on_capture(token: &str, value_js: &str) -> String {
    format!("window.__onCapture({}, {})", json_str(token), value_js)
}

struct DetectCtx {
    pid: u32,
    hwnd: Option<HWND>,
}

unsafe extern "system" fn detect_proc(hwnd: HWND, lparam: LPARAM) -> BOOL {
    let ctx = &mut *(lparam.0 as *mut DetectCtx);
    if IsWindowVisible(hwnd).as_bool() {
        let mut pid = 0u32;
        GetWindowThreadProcessId(hwnd, Some(&mut pid));
        if pid == ctx.pid && GetWindowTextLengthW(hwnd) > 0 {
            ctx.hwnd = Some(hwnd);
            return BOOL(0);
        }
    }
    BOOL(1)
}

fn find_pid(name: &str) -> Option<u32> {
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
        let _ = CloseHandle(snap);
        result
    }
}

fn detect_game() -> Option<(String, i32, i32)> {
    let pid = find_pid(TARGET_PROCESS)?;
    let mut ctx = DetectCtx { pid, hwnd: None };
    unsafe {
        let _ = EnumWindows(Some(detect_proc), LPARAM(&mut ctx as *mut _ as isize));
    }
    let hwnd = ctx.hwnd?;
    unsafe {
        let mut buf = [0u16; 512];
        let len = GetWindowTextW(hwnd, &mut buf);
        let title = from_wide(&buf[..len.max(0) as usize]);
        let mut rect = RECT::default();
        GetClientRect(hwnd, &mut rect).ok()?;
        let w = rect.right - rect.left;
        let h = rect.bottom - rect.top;
        if title.is_empty() || w <= 0 || h <= 0 {
            return None;
        }
        Some((title, w, h))
    }
}

fn pressed(vk: u32) -> bool {
    unsafe { (GetAsyncKeyState(vk as i32) as u16 & 0x8000) != 0 }
}

fn capture_key() -> String {
    let table = byte_to_key();
    while table.keys().any(|&vk| pressed(vk)) {
        thread::sleep(Duration::from_millis(15));
    }
    loop {
        for (&vk, &name) in table.iter() {
            if pressed(vk) {
                return name.to_string();
            }
        }
        thread::sleep(Duration::from_millis(15));
    }
}

fn cap_cursor() -> (i32, i32) {
    unsafe {
        let mut p = POINT { x: 0, y: 0 };
        let _ = GetCursorPos(&mut p);
        (p.x, p.y)
    }
}

fn wait_click() -> (i32, i32) {
    while pressed(VK_LBUTTON.0 as u32) {
        thread::sleep(Duration::from_millis(10));
    }
    while !pressed(VK_LBUTTON.0 as u32) {
        thread::sleep(Duration::from_millis(10));
    }
    let pos = cap_cursor();
    while pressed(VK_LBUTTON.0 as u32) {
        thread::sleep(Duration::from_millis(10));
    }
    pos
}

fn cap_pixel(x: i32, y: i32) -> (i32, i32, i32) {
    unsafe {
        let dc = GetDC(None);
        let color = GetPixel(dc, x, y);
        ReleaseDC(None, dc);
        (
            (color.0 & 0xff) as i32,
            ((color.0 >> 8) & 0xff) as i32,
            ((color.0 >> 16) & 0xff) as i32,
        )
    }
}

fn game_client(title: &str) -> Option<(i32, i32, i32, i32)> {
    unsafe {
        let title_w = wide(title);
        let hwnd = FindWindowW(PCWSTR::null(), PCWSTR(title_w.as_ptr())).ok()?;
        if hwnd.0.is_null() {
            return None;
        }
        let mut rect = RECT::default();
        GetClientRect(hwnd, &mut rect).ok()?;
        let w = rect.right - rect.left;
        let h = rect.bottom - rect.top;
        let mut origin = POINT { x: 0, y: 0 };
        let _ = ClientToScreen(hwnd, &mut origin);
        Some((origin.x, origin.y, w, h))
    }
}

fn to_reference(x: i32, y: i32, title: &str, sx: i32, sy: i32) -> Option<(i32, i32)> {
    let (ox, oy, w, h) = game_client(title)?;
    if w == 0 || h == 0 {
        return None;
    }
    Some(((x - ox) * sx / w, (y - oy) * sy / h))
}

fn capture_color() -> String {
    let (x, y) = wait_click();
    let (r, g, b) = cap_pixel(x, y);
    format!("[{r}, {g}, {b}]")
}

fn capture_pos(title: &str, sx: i32, sy: i32) -> Option<String> {
    let (x, y) = wait_click();
    let (rx, ry) = to_reference(x, y, title, sx, sy)?;
    Some(format!("({rx}, {ry})"))
}

fn capture_drag(title: &str, sx: i32, sy: i32) -> Option<String> {
    while pressed(VK_LBUTTON.0 as u32) {
        thread::sleep(Duration::from_millis(10));
    }
    while !pressed(VK_LBUTTON.0 as u32) {
        thread::sleep(Duration::from_millis(10));
    }

    crate::trail::start();
    let mut path: Vec<(i32, i32)> = Vec::new();
    let mut last = cap_cursor();
    path.push(last);
    crate::trail::push(last.0, last.1);

    while pressed(VK_LBUTTON.0 as u32) {
        let p = cap_cursor();
        let (dx, dy) = (p.0 - last.0, p.1 - last.1);
        if dx * dx + dy * dy >= 64 {
            path.push(p);
            crate::trail::push(p.0, p.1);
            last = p;
            if path.len() >= 400 {
                break;
            }
        }
        thread::sleep(Duration::from_millis(10));
    }
    let end = cap_cursor();
    if end != last {
        path.push(end);
    }
    crate::trail::stop();

    let path = downsample(path, 48);
    let pts: Vec<(i32, i32)> = path
        .iter()
        .filter_map(|&(x, y)| to_reference(x, y, title, sx, sy))
        .collect();
    if pts.len() < 2 {
        return None;
    }
    let body = pts
        .iter()
        .map(|(x, y)| format!("({x}, {y})"))
        .collect::<Vec<_>>()
        .join(" ");
    Some(format!("drag {body}"))
}

fn downsample(path: Vec<(i32, i32)>, max: usize) -> Vec<(i32, i32)> {
    if path.len() <= max {
        return path;
    }
    let step = path.len() as f64 / max as f64;
    let mut out = Vec::with_capacity(max + 1);
    let mut i = 0.0;
    while (i as usize) < path.len() {
        out.push(path[i as usize]);
        i += step;
    }
    let last = *path.last().unwrap();
    if out.last() != Some(&last) {
        out.push(last);
    }
    out
}
