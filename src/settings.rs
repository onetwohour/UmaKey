//! settingLoad.py 이식: 가상키 테이블, config.json 로드/업그레이드, 매핑 값 파싱.

use serde_json::Value;
use std::collections::HashMap;
use std::sync::OnceLock;

pub const DEFAULT_WINDOW_TITLE: &str = "umamusume";
pub const DEFAULT_SCREEN: (i32, i32) = (775, 1377);

/// 신규 설치 시 생성되는 기본 config. 배포본 config.json(v2.0)과 동일하게 유지한다.
pub const DEFAULT_CONFIG: &str = include_str!("../config.json");

/// (vk, 키 이름) 목록. Python 딕셔너리 리터럴과 동일한 순서로 둔다.
/// 107→"+", 109→"-"가 앞선 ADD/SUBTRACT를 덮어써 최종 맵에서 ADD/SUBTRACT가 사라지는 동작까지 재현.
fn raw_table() -> &'static [(u32, &'static str)] {
    &[
        (0x08, "BACKSPACE"), (0x09, "TAB"), (0x0C, "CLEAR"), (0x0D, "ENTER"),
        (0x10, "SHIFT"), (0x11, "CTRL"), (0x12, "ALT"), (0x13, "PAUSE"),
        (0x14, "CAPS_LOCK"), (0x1B, "ESC"), (0x20, "SPACEBAR"), (0x21, "PAGE_UP"),
        (0x22, "PAGE_DOWN"), (0x23, "END"), (0x24, "HOME"), (0x25, "LEFT_ARROW"),
        (0x26, "UP_ARROW"), (0x27, "RIGHT_ARROW"), (0x28, "DOWN_ARROW"),
        (0x2C, "PRINT_SCREEN"), (0x2D, "INSERT"), (0x2E, "DELETE"),
        (0x60, "NUMPAD_0"), (0x61, "NUMPAD_1"), (0x62, "NUMPAD_2"), (0x63, "NUMPAD_3"),
        (0x64, "NUMPAD_4"), (0x65, "NUMPAD_5"), (0x66, "NUMPAD_6"), (0x67, "NUMPAD_7"),
        (0x68, "NUMPAD_8"), (0x69, "NUMPAD_9"),
        (48, "0"), (49, "1"), (50, "2"), (51, "3"), (52, "4"), (53, "5"), (54, "6"),
        (55, "7"), (56, "8"), (57, "9"),
        (65, "A"), (66, "B"), (67, "C"), (68, "D"), (69, "E"), (70, "F"), (71, "G"),
        (72, "H"), (73, "I"), (74, "J"), (75, "K"), (76, "L"), (77, "M"), (78, "N"),
        (79, "O"), (80, "P"), (81, "Q"), (82, "R"), (83, "S"), (84, "T"), (85, "U"),
        (86, "V"), (87, "W"), (88, "X"), (89, "Y"), (90, "Z"),
        (0x5B, "LEFT_WINDOWS"), (0x5C, "RIGHT_WINDOWS"), (0x5D, "CONTEXT_MENU"),
        (0x6A, "MULTIPLY"), (0x6B, "ADD"), (0x6C, "SEPARATOR"), (0x6D, "SUBTRACT"),
        (0x6E, "DECIMAL"), (0x6F, "DIVIDE"),
        (0x70, "F1"), (0x71, "F2"), (0x72, "F3"), (0x73, "F4"), (0x74, "F5"),
        (0x75, "F6"), (0x76, "F7"), (0x77, "F8"), (0x78, "F9"), (0x79, "F10"),
        (0x7A, "F11"), (0x7B, "F12"), (0x7C, "F13"), (0x7D, "F14"), (0x7E, "F15"),
        (0x7F, "F16"), (0x80, "F17"), (0x81, "F18"), (0x82, "F19"), (0x83, "F20"),
        (0x84, "F21"), (0x85, "F22"), (0x86, "F23"), (0x87, "F24"),
        (0x90, "NUM_LOCK"), (0x91, "SCROLL_LOCK"), (0xA0, "LEFT_SHIFT"),
        (0xA1, "RIGHT_SHIFT"), (0xA2, "LEFT_CTRL"), (0xA3, "RIGHT_CTRL"),
        (0xA4, "LEFT_MENU"), (0xA5, "RIGHT_MENU"),
        (186, ";"), (107, "+"), (188, ","), (109, "-"), (190, "."), (191, "/"),
        (192, "`"), (219, "["), (220, "\\"), (221, "]"), (222, "'"),
    ]
}

/// vk → 키 이름. 같은 vk의 나중 항목이 앞 항목을 덮어쓴다(107→"+", 109→"-").
pub fn byte_to_key() -> &'static HashMap<u32, &'static str> {
    static M: OnceLock<HashMap<u32, &'static str>> = OnceLock::new();
    M.get_or_init(|| {
        let mut m = HashMap::new();
        for &(k, v) in raw_table() {
            m.insert(k, v);
        }
        m
    })
}

/// 키 이름 → vk. 최종 byte_to_key를 역전한 것이라 ADD/SUBTRACT는 포함되지 않는다.
pub fn key_to_byte() -> &'static HashMap<&'static str, u32> {
    static M: OnceLock<HashMap<&'static str, u32>> = OnceLock::new();
    M.get_or_init(|| {
        let mut m = HashMap::new();
        for (&k, &v) in byte_to_key().iter() {
            m.insert(v, k);
        }
        m
    })
}

/// 매핑 값 하나. convert_value가 문자열을 이 형태 중 하나로 해석한다.
#[derive(Clone, Debug, PartialEq)]
pub enum Action {
    Color([i32; 3]),
    Pos((i32, i32)),
    Key(u32),
    Raw(String),
}

/// settingLoad.convert_value 이식. 해석에 실패하면 원문을 Raw로 둔다.
pub fn convert_value(value_str: &str) -> Action {
    let t = value_str.trim();
    if t.starts_with('[') && t.ends_with(']') {
        let inner = &t[1..t.len() - 1];
        let parts: Vec<&str> = inner.split(',').collect();
        if parts.len() == 3 {
            if let (Ok(r), Ok(g), Ok(b)) = (
                parts[0].trim().parse::<i32>(),
                parts[1].trim().parse::<i32>(),
                parts[2].trim().parse::<i32>(),
            ) {
                return Action::Color([r, g, b]);
            }
        }
    } else if t.starts_with('(') && t.ends_with(')') {
        let inner = &t[1..t.len() - 1];
        let parts: Vec<&str> = inner.split(',').collect();
        if parts.len() == 2 {
            if let (Ok(x), Ok(y)) =
                (parts[0].trim().parse::<i32>(), parts[1].trim().parse::<i32>())
            {
                return Action::Pos((x, y));
            }
        }
    }
    if let Some(&vk) = key_to_byte().get(t) {
        return Action::Key(vk);
    }
    Action::Raw(t.to_string())
}

/// 로드·파싱이 끝난 설정 상태. Python settingLoad 모듈 전역들에 대응.
#[derive(Clone, Debug)]
pub struct Settings {
    pub window_title: String,
    /// (x, y) — Python ratio.
    pub ratio: (i32, i32),
    /// key_mapping의 키 순서(“switch” 포함). 프리셋 순환이 이 순서를 따른다.
    pub key_order: Vec<String>,
    /// 프리셋 이름 → (키 이름 → Action).
    pub presets: HashMap<String, HashMap<String, Action>>,
    /// "switch" 항목 값(예: "F1").
    pub switch: Option<String>,
    /// 로드된 원본 JSON. 매크로 정의 조회에 사용(Python `load`).
    pub raw: Value,
}

impl Settings {
    pub fn preset(&self, name: &str) -> Option<&HashMap<String, Action>> {
        self.presets.get(name)
    }

    /// 매크로 이름 등 최상위 키의 값을 조회(Python `load.get`).
    pub fn raw_get<'a>(&'a self, key: &str) -> Option<&'a Value> {
        self.raw.get(key)
    }
}

/// settingLoad.upgrade_config 이식. 1.0 → 2.0 변환 여부를 반환한다.
fn upgrade(root: &mut Value) -> bool {
    let current = root
        .get("version")
        .and_then(|v| v.as_str())
        .unwrap_or("1.0")
        .to_string();
    if current != "1.0" {
        return false;
    }

    let obj = match root.as_object_mut() {
        Some(o) => o,
        None => return false,
    };
    obj.insert("version".to_string(), Value::String("2.0".to_string()));

    if let Some(Value::Object(old)) = obj.get("key_mapping") {
        let mut default = serde_json::Map::new();
        for (k, v) in old {
            let s = match v {
                Value::String(s) => s.clone(),
                other => other.to_string(),
            };
            default.insert(k.clone(), Value::String(s));
        }
        let mut new_km = serde_json::Map::new();
        new_km.insert("default".to_string(), Value::Object(default));
        new_km.insert("switch".to_string(), Value::String("F1".to_string()));
        obj.insert("key_mapping".to_string(), Value::Object(new_km));
    }
    true
}

/// JSON Value를 Settings로 해석. 필요하면 1.0→2.0 업그레이드를 먼저 적용한다.
pub fn parse(mut root: Value) -> Settings {
    upgrade(&mut root);

    let window_title = root
        .get("window_title")
        .and_then(|v| v.as_str())
        .map(String::from)
        .unwrap_or_else(|| DEFAULT_WINDOW_TITLE.to_string());

    let ratio = match root.get("screen_size") {
        Some(ss) => (
            ss.get("x").and_then(|v| v.as_i64()).map(|n| n as i32).unwrap_or(DEFAULT_SCREEN.0),
            ss.get("y").and_then(|v| v.as_i64()).map(|n| n as i32).unwrap_or(DEFAULT_SCREEN.1),
        ),
        None => DEFAULT_SCREEN,
    };

    let mut key_order = Vec::new();
    let mut presets = HashMap::new();
    let mut switch = None;

    if let Some(Value::Object(km)) = root.get("key_mapping") {
        for (name, val) in km {
            key_order.push(name.clone());
            match val {
                Value::String(s) => {
                    if name == "switch" {
                        switch = Some(s.clone());
                    }
                }
                Value::Object(entries) => {
                    let mut mapping = HashMap::new();
                    for (key, v) in entries {
                        let s = match v {
                            Value::String(s) => s.clone(),
                            other => other.to_string(),
                        };
                        mapping.insert(key.clone(), convert_value(&s));
                    }
                    presets.insert(name.clone(), mapping);
                }
                _ => {}
            }
        }
    }

    Settings { window_title, ratio, key_order, presets, switch, raw: root }
}

/// config.json을 읽어 Settings로 로드한다. 파일이 없으면 기본 config를 쓰고,
/// 1.0→2.0 업그레이드가 발생하면 파일에 다시 저장한다.
pub fn load_from(path: &str) -> Result<Settings, String> {
    if !std::path::Path::new(path).is_file() {
        std::fs::write(path, DEFAULT_CONFIG).map_err(|e| e.to_string())?;
    }

    let raw = std::fs::read(path).map_err(|e| e.to_string())?;
    let text = decode_bytes(&raw);
    let mut root: Value = serde_json::from_str(&text)
        .map_err(|_| "config.json has wrong syntax.".to_string())?;

    if upgrade(&mut root) {
        let pretty = serde_json::to_string_pretty(&root).map_err(|e| e.to_string())?;
        std::fs::write(path, pretty).map_err(|e| e.to_string())?;
    }

    Ok(parse(root))
}

/// chardet 대체: 인코딩을 감지해 UTF-8 문자열로 디코드한다.
fn decode_bytes(raw: &[u8]) -> String {
    let mut detector = chardetng::EncodingDetector::new();
    detector.feed(raw, true);
    let encoding = detector.guess(None, true);
    let (text, _, _) = encoding.decode(raw);
    text.into_owned()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn vk_tables_reproduce_python_overwrites() {
        let b2k = byte_to_key();
        assert_eq!(b2k.get(&107), Some(&"+"));
        assert_eq!(b2k.get(&109), Some(&"-"));
        assert_eq!(b2k.get(&0x20), Some(&"SPACEBAR"));
        assert_eq!(b2k.get(&65), Some(&"A"));

        let k2b = key_to_byte();
        assert_eq!(k2b.get("+"), Some(&107));
        assert_eq!(k2b.get("-"), Some(&109));
        assert_eq!(k2b.get("SPACEBAR"), Some(&0x20));
        assert_eq!(k2b.get("ADD"), None);
        assert_eq!(k2b.get("SUBTRACT"), None);
    }

    #[test]
    fn convert_value_forms() {
        assert_eq!(convert_value("[99, 182, 0]"), Action::Color([99, 182, 0]));
        assert_eq!(convert_value("(700, 1300)"), Action::Pos((700, 1300)));
        assert_eq!(convert_value("(-1, -1)"), Action::Pos((-1, -1)));
        assert_eq!(convert_value("SPACEBAR"), Action::Key(0x20));
        assert_eq!(
            convert_value("drag (20, 1150) (660, 1150)"),
            Action::Raw("drag (20, 1150) (660, 1150)".to_string())
        );
        assert_eq!(convert_value("MAC"), Action::Raw("MAC".to_string()));
    }

    #[test]
    fn parse_default_config() {
        let root: Value = serde_json::from_str(DEFAULT_CONFIG).unwrap();
        let s = parse(root);
        assert_eq!(s.window_title, "umamusume");
        assert_eq!(s.ratio, (775, 1377));
        assert_eq!(s.switch.as_deref(), Some("F1"));
        assert!(s.key_order.contains(&"switch".to_string()));
        assert!(s.presets.contains_key("default"));
        assert!(s.presets.contains_key("scroll"));

        let default = s.preset("default").unwrap();
        assert_eq!(default.get("SPACEBAR"), Some(&Action::Color([99, 182, 0])));
        assert_eq!(default.get("/"), Some(&Action::Pos((700, 1300))));
        assert_eq!(default.get("CAPS_LOCK"), Some(&Action::Pos((-1, -1))));
        assert_eq!(default.get("NUMPAD_0"), Some(&Action::Raw("MAC".to_string())));
        assert!(s.raw_get("MAC").is_some());
    }

    #[test]
    fn upgrade_v1_to_v2() {
        let mut root: Value = serde_json::json!({
            "key_mapping": { "Q": "[124, 203, 42]", "/": "(700, 1300)" }
        });
        assert!(upgrade(&mut root));
        assert_eq!(root.get("version").unwrap(), "2.0");
        let km = root.get("key_mapping").unwrap();
        assert_eq!(km.get("switch").unwrap(), "F1");
        assert_eq!(km.get("default").unwrap().get("Q").unwrap(), "[124, 203, 42]");
    }
}
