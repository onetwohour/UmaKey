
pub mod color;
pub mod hook;
pub mod input;
pub mod window;

use std::ffi::c_void;
use std::sync::atomic::{AtomicBool, AtomicI32, AtomicUsize, Ordering};
use std::sync::{Arc, Mutex, OnceLock, RwLock};
use std::thread;
use std::time::{Duration, Instant};

use regex::Regex;
use windows::core::PCWSTR;
use windows::Win32::Foundation::HWND;
use windows::Win32::UI::WindowsAndMessaging::{
    IsIconic, IsWindow, MessageBoxW, MB_ICONWARNING, MB_TOPMOST,
};

use crate::settings::{self, byte_to_key, key_to_byte, Action, Settings};
use color::ColorFinder;
use window::WindowHandler;

pub const TARGET_PROCESS: &str = "umamusume.exe";

pub const SYNTH_EXTRA: usize = 3000;

const TOLERANCE: i32 = 10;

static ENGINE: OnceLock<Arc<AutoClicker>> = OnceLock::new();

pub(crate) fn engine() -> Option<&'static Arc<AutoClicker>> {
    ENGINE.get()
}

pub fn wide(s: &str) -> Vec<u16> {
    s.encode_utf16().chain(std::iter::once(0)).collect()
}

pub(crate) fn from_wide(buf: &[u16]) -> String {
    let end = buf.iter().position(|&c| c == 0).unwrap_or(buf.len());
    String::from_utf16_lossy(&buf[..end])
}

fn token_re() -> &'static Regex {
    static R: OnceLock<Regex> = OnceLock::new();
    R.get_or_init(|| Regex::new(r"\[.*?\]|\(.*?\)|\d+|\b\w+\s[\d.]+\b|\w+").unwrap())
}

fn drag_re() -> &'static Regex {
    static R: OnceLock<Regex> = OnceLock::new();
    R.get_or_init(|| Regex::new(r"\((\w+), (\w+)\)").unwrap())
}

enum Mapped {
    NoMap,
    Switch,
    Act(Action),
}

pub struct AutoClicker {
    settings: RwLock<Settings>,
    tolerance: i32,
    state: AtomicI32,
    hwnd: AtomicUsize,
    enabled: AtomicBool,
    hook_lock: AtomicBool,
    hook_handle: AtomicUsize,
    hook_running: AtomicBool,
    preset_index: AtomicUsize,
    current_preset: Mutex<String>,
    error: Mutex<Option<String>>,
}

impl AutoClicker {
    pub fn new() -> Arc<Self> {
        let settings = settings::load_from("config.json").unwrap_or_else(|_| {
            settings::parse(serde_json::from_str(settings::DEFAULT_CONFIG).unwrap())
        });
        Self::with_settings(settings)
    }

    pub fn with_settings(settings: Settings) -> Arc<Self> {
        Arc::new(Self {
            settings: RwLock::new(settings),
            tolerance: TOLERANCE,
            state: AtomicI32::new(0),
            hwnd: AtomicUsize::new(0),
            enabled: AtomicBool::new(false),
            hook_lock: AtomicBool::new(false),
            hook_handle: AtomicUsize::new(0),
            hook_running: AtomicBool::new(false),
            preset_index: AtomicUsize::new(0),
            current_preset: Mutex::new(String::new()),
            error: Mutex::new(None),
        })
    }

    pub fn install(self: &Arc<Self>) {
        let _ = ENGINE.set(self.clone());
    }

    fn hwnd_handle(&self) -> HWND {
        HWND(self.hwnd.load(Ordering::SeqCst) as *mut c_void)
    }

    fn set_hwnd(&self, hwnd: HWND) {
        self.hwnd.store(hwnd.0 as usize, Ordering::SeqCst);
    }

    fn window(&self) -> WindowHandler {
        WindowHandler { hwnd: self.hwnd_handle() }
    }

    pub fn is_run(&self) -> bool {
        self.state.load(Ordering::SeqCst) > 0
    }

    pub fn error_occurred(&self) -> bool {
        self.state.load(Ordering::SeqCst) == -1
    }

    pub fn error_message(&self) -> Option<String> {
        self.error.lock().unwrap().clone()
    }

    fn enable(&self) {
        self.enabled.store(true, Ordering::SeqCst);
    }

    fn disable(&self) {
        self.enabled.store(false, Ordering::SeqCst);
    }

    pub(crate) fn is_mapped(&self, vk: u32) -> bool {
        let name = match byte_to_key().get(&vk).copied() {
            Some(n) => n,
            None => return false,
        };
        let settings = self.settings.read().unwrap();
        if settings.switch.as_deref() == Some(name) {
            return true;
        }
        let preset = self.current_preset.lock().unwrap().clone();
        settings
            .presets
            .get(&preset)
            .map_or(false, |m| m.contains_key(name))
    }

    pub(crate) fn on_keyboard_event(&self, vk: u32) {
        let keyname = byte_to_key().get(&vk).copied();

        let mapped = {
            let settings = self.settings.read().unwrap();
            let is_switch = keyname.map_or(false, |k| settings.switch.as_deref() == Some(k));
            if is_switch {
                Mapped::Switch
            } else {
                let preset = self.current_preset.lock().unwrap().clone();
                match keyname
                    .and_then(|k| settings.presets.get(&preset).and_then(|m| m.get(k)))
                {
                    Some(a) => Mapped::Act(a.clone()),
                    None => Mapped::NoMap,
                }
            }
        };

        let foreground = self.window().is_window_foreground();

        match mapped {
            Mapped::NoMap => input::press_key(vk),
            _ if !foreground => input::press_key(vk),
            Mapped::Switch => self.do_switch(),
            Mapped::Act(act) => {
                let is_macro = match &act {
                    Action::Raw(name) => self.settings.read().unwrap().raw_get(name).is_some(),
                    _ => false,
                };
                if is_macro {
                    if let Action::Raw(name) = &act {
                        for item in self.decode(name) {
                            self.run_action(&item);
                        }
                    }
                } else {
                    self.run_action(&act);
                }
            }
        }
    }

    fn decode(&self, name: &str) -> Vec<Action> {
        let settings = self.settings.read().unwrap();
        let text = match settings.raw_get(name).and_then(|v| v.as_str()) {
            Some(t) => t.to_string(),
            None => return Vec::new(),
        };
        let preset_name = self.current_preset.lock().unwrap().clone();
        let preset = settings.presets.get(&preset_name);

        let mut keys: Vec<Action> = Vec::new();
        for m in token_re().find_iter(&text) {
            let tok = m.as_str();
            if tok.starts_with('(') {
                let nums = parse_ints(&tok[1..tok.len() - 1]);
                if let Some(Action::Raw(last)) = keys.last_mut() {
                    if last.starts_with("drag") && nums.len() == 2 {
                        last.push_str(&format!(" ({}, {})", nums[0], nums[1]));
                        continue;
                    }
                }
                if nums.len() == 2 {
                    keys.push(Action::Pos((nums[0], nums[1])));
                }
            } else if tok.starts_with('[') {
                let nums = parse_ints(&tok[1..tok.len() - 1]);
                if nums.len() == 3 {
                    keys.push(Action::Color([nums[0], nums[1], nums[2]]));
                }
            } else if !tok.is_empty() && tok.bytes().all(|b| b.is_ascii_digit()) {
                match key_to_byte().get(tok) {
                    Some(&vk) => keys.push(Action::Key(vk)),
                    None => keys.push(Action::Raw(tok.to_string())),
                }
            } else if tok.contains(' ') {
                keys.push(Action::Raw(tok.to_string()));
            } else if let Some(a) = preset.and_then(|p| p.get(tok)) {
                keys.push(a.clone());
            } else {
                keys.push(Action::Raw(tok.to_string()));
            }
        }
        keys
    }

    fn run_action(&self, act: &Action) {
        match act {
            Action::Color(c) => {
                let finder = ColorFinder::new(self.hwnd_handle());
                if let Some((cx, cy)) = finder.find_color(*c, self.tolerance) {
                    if cx != 0 || cy != 0 {
                        input::click(cx, cy);
                    }
                }
            }
            Action::Pos(p) => self.click_pos(*p),
            Action::Key(vk) => {
                let settings = self.settings.read().unwrap();
                let preset = self.current_preset.lock().unwrap().clone();
                if let Some(name) = byte_to_key().get(vk).copied() {
                    if let Some(a) = settings
                        .presets
                        .get(&preset)
                        .and_then(|m| m.get(name))
                        .cloned()
                    {
                        drop(settings);
                        self.run_action(&a);
                    }
                }
            }
            Action::Raw(s) => {
                if s.starts_with("sleep") || s.starts_with("drag") {
                    let mut parts = s.splitn(2, ' ');
                    let cmd = parts.next().unwrap_or("");
                    let value = parts.next().unwrap_or("");
                    if cmd == "sleep" {
                        if let Ok(sec) = value.parse::<f64>() {
                            thread::sleep(Duration::from_secs_f64(sec.max(0.0)));
                        }
                    } else if cmd == "drag" {
                        self.drag(value);
                    }
                } else if s == "switch" {
                    self.do_switch();
                } else if let Some(&vk) = key_to_byte().get(s.as_str()) {
                    input::keyboard(vk);
                }
            }
        }
    }

    fn click_pos(&self, p: (i32, i32)) {
        let (left, top, right, bottom) = self.window().get_window_position();
        if p == (-1, -1) {
            let (x, y) = input::get_cursor_pos();
            if left + 20 <= x && x <= right - 20 && top + 60 <= y && y <= bottom - 20 {
                input::click(x, y);
            }
            return;
        }
        let ratio = self.settings.read().unwrap().ratio;
        let x = (p.0 as f64 * (right - left) as f64 / ratio.0 as f64 + left as f64) as i32;
        let y = (p.1 as f64 * (bottom - top) as f64 / ratio.1 as f64 + top as f64) as i32;
        let (l, t, r, b) = (left + 20, top + 60, right - 20, bottom - 20);
        input::click(x.clamp(l, r), y.clamp(t, b));
    }

    fn drag(&self, pos: &str) {
        let raw: Vec<(i32, i32)> = drag_re()
            .captures_iter(pos)
            .filter_map(|c| {
                let a = c.get(1)?.as_str().parse::<i32>().ok()?;
                let b = c.get(2)?.as_str().parse::<i32>().ok()?;
                Some((a, b))
            })
            .collect();
        if raw.len() < 2 {
            return;
        }

        let (left, top, right, bottom) = self.window().get_window_position();
        let ratio = self.settings.read().unwrap().ratio;
        let width = (right - left) as f64;
        let height = (bottom - top) as f64;
        let (l, t, r, b) = (left + 20, top + 60, right - 20, bottom - 20);
        let pts: Vec<(i32, i32)> = raw
            .iter()
            .map(|&(x, y)| {
                let sx = (x as f64 * (width / ratio.0 as f64) + left as f64) as i32;
                let sy = (y as f64 * (height / ratio.1 as f64) + top as f64) as i32;
                (sx.clamp(l, r), sy.clamp(t, b))
            })
            .collect();

        input::set_cursor_pos(pts[0].0, pts[0].1);
        input::mouse_left_down();
        thread::sleep(Duration::from_millis(10));

        let mut cur = pts[0];
        for &next in &pts[1..] {
            if cur == next {
                continue;
            }
            let distance = ((cur.0 - next.0).abs() as f64 / 20.0)
                .max((cur.1 - next.1).abs() as f64 / 20.0)
                .max(1.0)
                .min(40.0);
            let dx = (next.0 - cur.0) as f64 / distance;
            let dy = (next.1 - cur.1) as f64 / distance;
            let mut fx = cur.0 as f64;
            let mut fy = cur.1 as f64;
            for _ in 0..(distance as i32) {
                fx += dx;
                fy += dy;
                input::set_cursor_pos(fx as i32, fy as i32);
                thread::sleep(Duration::from_millis(15));
            }
            input::set_cursor_pos(next.0, next.1);
            cur = next;
        }
        input::mouse_left_up();
    }

    fn do_switch(&self) {
        let (len, mut idx, mut current);
        {
            let settings = self.settings.read().unwrap();
            len = settings.key_order.len();
            if len == 0 {
                return;
            }
            idx = (self.preset_index.load(Ordering::SeqCst) + 1) % len;
            current = settings.key_order[idx].clone();
        }
        self.preset_index.store(idx, Ordering::SeqCst);
        *self.current_preset.lock().unwrap() = current.clone();
        self.ring_effect();
        if current == "switch" {
            let settings = self.settings.read().unwrap();
            idx = (idx + 1) % len;
            current = settings.key_order[idx].clone();
            self.preset_index.store(idx, Ordering::SeqCst);
            *self.current_preset.lock().unwrap() = current;
        }
    }

    fn ring_effect(&self) {
        crate::effect::show();
    }

    pub fn toggle(self: &Arc<Self>) {
        if !self.is_run() {
            if let Ok(s) = settings::load_from("config.json") {
                *self.settings.write().unwrap() = s;
            }
            let name = {
                let s = self.settings.read().unwrap();
                s.key_order
                    .get(self.preset_index.load(Ordering::SeqCst))
                    .cloned()
                    .unwrap_or_default()
            };
            *self.current_preset.lock().unwrap() = name;
            self.run();
        } else {
            self.destroy();
        }
    }

    pub fn reload(&self) {
        let s = match settings::load_from("config.json") {
            Ok(s) => s,
            Err(_) => return,
        };
        let title_changed = self.settings.read().unwrap().window_title != s.window_title;
        let len = s.key_order.len();
        *self.settings.write().unwrap() = s;
        if title_changed {
            self.set_hwnd(HWND(std::ptr::null_mut()));
        }
        if len == 0 {
            return;
        }
        let mut idx = self.preset_index.load(Ordering::SeqCst);
        if idx >= len {
            idx = 0;
            self.preset_index.store(0, Ordering::SeqCst);
        }
        let name = self
            .settings
            .read()
            .unwrap()
            .key_order
            .get(idx)
            .cloned()
            .unwrap_or_default();
        *self.current_preset.lock().unwrap() = name;
    }

    fn run(self: &Arc<Self>) {
        if self.is_run() {
            return;
        }
        self.state.store(1, Ordering::SeqCst);
        hook::start();
        let me = self.clone();
        thread::spawn(move || me.monitor());
    }

    fn monitor(self: Arc<Self>) {
        while self.is_run() {
            if !self.valid_window() {
                self.disable();
                thread::sleep(Duration::from_millis(500));
                self.update_window();
                continue;
            }

            match self.state.load(Ordering::SeqCst) {
                1 => {
                    if !self.window().activate_window() {
                        self.disable();
                        thread::sleep(Duration::from_millis(500));
                        continue;
                    }
                    let me = self.clone();
                    thread::spawn(move || me.screen_size_detect());
                    self.enable();
                    self.state.store(2, Ordering::SeqCst);
                }
                2 => {
                    if self.window().is_window_foreground() {
                        self.enable();
                    } else {
                        self.disable();
                    }
                    thread::sleep(Duration::from_millis(500));
                }
                _ => {}
            }
        }
    }

    fn valid_window(&self) -> bool {
        let h = self.hwnd_handle();
        !h.0.is_null() && unsafe { IsWindow(h).as_bool() }
    }

    fn update_window(&self) {
        let title = self.settings.read().unwrap().window_title.clone();
        let mut wh = WindowHandler { hwnd: self.hwnd_handle() };
        wh.update(&title);
        self.set_hwnd(wh.hwnd);
    }

    fn screen_size_detect(self: Arc<Self>) {
        let start = Instant::now();
        let mut timeout = 15.0f64;
        while self.is_run() && start.elapsed().as_secs_f64() < 10.0 {
            thread::sleep(Duration::from_millis(100));
        }
        while self.is_run()
            && start.elapsed().as_secs_f64() < timeout
            && self.valid_window()
            && self.error.lock().unwrap().is_none()
        {
            let (left, top, right, bottom) = self.window().get_window_position();
            if unsafe { IsIconic(self.hwnd_handle()).as_bool() } {
                timeout += 0.1;
            } else if right != left {
                let ratio = self.settings.read().unwrap().ratio;
                let actual = (bottom - top) as f64 / (right - left) as f64;
                let expected = ratio.1 as f64 / ratio.0 as f64;
                if (actual / expected - 1.0).abs() > 0.1 {
                    show_warning("게임 화면 비율이 다릅니다.");
                    break;
                }
            }
            thread::sleep(Duration::from_millis(100));
        }
    }

    pub fn destroy(&self) {
        self.state.store(0, Ordering::SeqCst);
        hook::stop();
    }
}

fn parse_ints(inner: &str) -> Vec<i32> {
    inner
        .split(',')
        .filter_map(|s| s.trim().parse::<i32>().ok())
        .collect()
}

fn show_warning(message: &str) {
    let text = wide(message);
    let caption = wide("Warning");
    unsafe {
        MessageBoxW(
            HWND(std::ptr::null_mut()),
            PCWSTR(text.as_ptr()),
            PCWSTR(caption.as_ptr()),
            MB_ICONWARNING | MB_TOPMOST,
        );
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn engine_with(json: serde_json::Value, preset: &str) -> Arc<AutoClicker> {
        let ac = AutoClicker::with_settings(settings::parse(json));
        *ac.current_preset.lock().unwrap() = preset.to_string();
        ac
    }

    #[test]
    fn decode_mac_digits_and_sleeps() {
        let json = serde_json::from_str(settings::DEFAULT_CONFIG).unwrap();
        let ac = engine_with(json, "default");
        let items = ac.decode("MAC");
        let vk1 = *key_to_byte().get("1").unwrap();
        let vk2 = *key_to_byte().get("2").unwrap();
        assert_eq!(items[0], Action::Key(vk1));
        assert_eq!(items[1], Action::Raw("sleep 0.1".to_string()));
        assert_eq!(items[2], Action::Key(vk2));
    }

    #[test]
    fn decode_builds_drag_string() {
        let json = serde_json::json!({
            "version": "2.0",
            "window_title": "x",
            "key_mapping": { "default": {}, "switch": "F1" },
            "screen_size": { "x": 100, "y": 100 },
            "DR": "drag (1, 2) (3, 4)"
        });
        let ac = engine_with(json, "default");
        let items = ac.decode("DR");
        assert_eq!(items, vec![Action::Raw("drag (1, 2) (3, 4)".to_string())]);
    }

    #[test]
    fn is_mapped_switch_and_preset() {
        let json = serde_json::from_str(settings::DEFAULT_CONFIG).unwrap();
        let ac = engine_with(json, "default");
        let f1 = *key_to_byte().get("F1").unwrap();
        let q = *key_to_byte().get("Q").unwrap();
        let z = *key_to_byte().get("Z").unwrap();
        assert!(ac.is_mapped(f1));
        assert!(ac.is_mapped(q));
        assert!(!ac.is_mapped(z));
    }
}
