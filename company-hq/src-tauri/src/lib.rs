use std::{path::PathBuf, process::Command};
use tauri::Manager;

fn project_root() -> Result<PathBuf, String> {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .canonicalize()
        .map_err(|error| format!("Could not locate Company HQ checkout: {error}"))
}

fn start_company_hq() -> Result<String, String> {
    let root = project_root()?;
    let script = root.join("scripts/hq.py");
    let output = Command::new("python3")
        .arg(&script)
        .arg("start")
        .current_dir(&root)
        .output()
        .map_err(|error| format!("Could not start Company HQ backend: {error}"))?;

    if !output.status.success() {
        return Err(format!(
            "Company HQ backend failed to start: {}",
            String::from_utf8_lossy(&output.stderr)
        ));
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    stdout
        .lines()
        .find(|line| line.starts_with("http://127.0.0.1:"))
        .map(|line| line.trim().to_owned())
        .ok_or_else(|| format!("Company HQ backend did not report a local URL. Output: {stdout}"))
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .setup(|app| {
            let window = app
                .get_webview_window("main")
                .ok_or_else(|| "Missing main window".to_string())?;
            match start_company_hq() {
                Ok(url) => {
                    let parsed_url = url
                        .parse()
                        .map_err(|error| format!("Company HQ backend reported an invalid URL: {error}"))?;
                    window
                        .navigate(parsed_url)
                        .map_err(|error| format!("Could not open Company HQ in the app window: {error}"))?;
                }
                Err(error) => {
                    eprintln!("{error}");
                }
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running Company HQ desktop app");
}
