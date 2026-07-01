//! modules/update.py 이식: GitHub 최신 릴리스 확인.

use serde_json::Value;

/// 최신 릴리스를 조회해 (업데이트 필요 여부, 릴리스 JSON)을 반환.
pub fn check_new_release(
    owner: &str,
    name: &str,
    current_version: &str,
) -> (bool, Option<Value>) {
    let url = format!("https://api.github.com/repos/{owner}/{name}/releases/latest");
    let resp = match ureq::get(&url).set("User-Agent", "UmaKey").call() {
        Ok(r) => r,
        Err(_) => return (false, None),
    };
    let body = match resp.into_string() {
        Ok(b) => b,
        Err(_) => return (false, None),
    };
    let release: Value = match serde_json::from_str(&body) {
        Ok(v) => v,
        Err(_) => return (false, None),
    };
    match release.get("tag_name").and_then(|t| t.as_str()) {
        Some(tag) if tag != current_version => (true, Some(release)),
        _ => (false, None),
    }
}

/// 릴리스 JSON에서 (첫 에셋 다운로드 URL, 태그명)을 추출.
pub fn release_info(release: &Value) -> (Option<String>, Option<String>) {
    let url = release
        .get("assets")
        .and_then(|a| a.get(0))
        .and_then(|a| a.get("browser_download_url"))
        .and_then(|u| u.as_str())
        .map(String::from);
    let tag = release
        .get("tag_name")
        .and_then(|t| t.as_str())
        .map(String::from);
    (url, tag)
}
