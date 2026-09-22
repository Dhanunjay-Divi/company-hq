use std::{
    io::{BufRead, BufReader},
    path::PathBuf,
    process::{Child, Command, Stdio},
    sync::Mutex,
    time::Duration,
};
use tauri::{Manager, RunEvent, State};
#[cfg(unix)] use std::os::unix::process::CommandExt;

struct Backend(Mutex<Option<Child>>);

fn safe_resource(app: &tauri::AppHandle, relative: &str) -> Result<PathBuf, String> {
    let root = app.path().resource_dir().map_err(|e| format!("No bundle resources: {e}"))?.canonicalize().map_err(|e| format!("No bundle resources: {e}"))?;
    let candidate = root.join(relative).canonicalize().map_err(|e| format!("Missing bundled resource: {e}"))?;
    if !candidate.starts_with(&root) || !candidate.is_file() {
        return Err("Bundled resource is outside the application resources".into());
    }
    Ok(candidate)
}

#[tauri::command]
fn pick_project_folder() -> Result<Option<String>, String> {
    #[cfg(target_os = "macos")]
    {
        let output = Command::new("/usr/bin/osascript")
            .args(["-e", "try\nPOSIX path of (choose folder with prompt \"Choose a Company HQ project folder\")\non error number -128\nreturn \"\"\nend try"])
            .output().map_err(|e| format!("Could not open folder picker: {e}"))?;
        if !output.status.success() { return Err("Folder picker did not complete".into()); }
        let path = String::from_utf8_lossy(&output.stdout).trim().to_owned();
        if path.is_empty() { return Ok(None); }
        let folder = PathBuf::from(path).canonicalize().map_err(|e| format!("Selected folder is unavailable: {e}"))?;
        if !folder.is_dir() { return Err("Selected path is not a folder".into()); }
        Ok(Some(folder.display().to_string()))
    }
    #[cfg(not(target_os = "macos"))]
    { Ok(None) }
}


fn stop_child(child: &mut Child) {
    #[cfg(unix)]
    { let _ = Command::new("/bin/kill").args(["-TERM", &child.id().to_string()]).status(); }
    for _ in 0..300 {
        if child.try_wait().ok().flatten().is_some() { return; }
        std::thread::sleep(Duration::from_millis(100));
    }
    #[cfg(unix)] { let _ = Command::new("/bin/kill").args(["-KILL", "--", &format!("-{}", child.id())]).status(); }
    let _ = child.kill();
    let _ = child.wait();
}

fn start_backend(app: &tauri::AppHandle, state: &State<'_, Backend>) -> Result<String, String> {
    let sidecar = safe_resource(app, "resources/backend/company-hq-backend-aarch64-apple-darwin")?;
    let mut command = Command::new(sidecar);
    command.arg("--port").arg("0").stdin(Stdio::null()).stdout(Stdio::piped()).stderr(Stdio::piped());
    #[cfg(unix)] { command.process_group(0); }
    let mut child = command.spawn().map_err(|e| format!("Could not start bundled Company HQ backend: {e}"))?;
    let stdout = child.stdout.take().ok_or("Bundled backend has no stdout")?;
    let (send, receive) = std::sync::mpsc::channel();
    std::thread::spawn(move || {
        for line in BufReader::new(stdout).lines().map_while(Result::ok) {
            if let Some(url) = line.strip_prefix("ClawTeam metadata board: ") { let _ = send.send(url.to_string()); }
        }
    });
    // Always drain stderr: a full pipe must not stall the bundled server.
    if let Some(stderr) = child.stderr.take() { std::thread::spawn(move || { for _ in BufReader::new(stderr).lines() {} }); }
    let url = match receive.recv_timeout(Duration::from_secs(45)) { Ok(url) => url, Err(_) => { stop_child(&mut child); return Err("Bundled backend did not report a loopback URL within 45 seconds".into()); } };
    let parsed: url::Url = match url.parse() { Ok(value) => value, Err(_) => { stop_child(&mut child); return Err("Bundled backend reported an invalid URL".into()); } };
    if parsed.scheme() != "http" || parsed.host_str() != Some("127.0.0.1") || parsed.port().is_none() { stop_child(&mut child); return Err("Bundled backend did not report a verified loopback URL".into()); }
    *state.0.lock().map_err(|_| "Backend state is unavailable")? = Some(child);
    Ok(url)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(Backend(Mutex::new(None)))
        .invoke_handler(tauri::generate_handler![pick_project_folder])
        .setup(|app| {
            let url = start_backend(&app.handle(), &app.state::<Backend>())?;
            let parsed = url.parse().map_err(|e| format!("Invalid loopback URL: {e}"))?;
            app.get_webview_window("main").ok_or("Missing main window")?.navigate(parsed).map_err(|e| format!("Could not open local backend: {e}"))?;
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building Company HQ desktop app")
        .run(|app, event| if matches!(event, RunEvent::ExitRequested { .. }) { if let Ok(mut child) = app.state::<Backend>().0.lock() { if let Some(mut process) = child.take() { stop_child(&mut process); } } });
}
