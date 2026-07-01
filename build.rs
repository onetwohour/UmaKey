fn main() {
    // 관리자 권한 매니페스트를 실행 바이너리에만 임베드(테스트 하니스 제외).
    if std::env::var_os("CARGO_CFG_WINDOWS").is_some() {
        println!("cargo:rustc-link-arg-bins=/MANIFEST:EMBED");
        println!("cargo:rustc-link-arg-bins=/MANIFESTUAC:level='requireAdministrator'");
    }
    println!("cargo:rerun-if-changed=build.rs");
}
