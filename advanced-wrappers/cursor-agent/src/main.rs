use cursor_cli_wrapper::config;
use std::io::IsTerminal;
use std::os::fd::AsRawFd;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::fs::OpenOptions;
use tokio::io::{self, AsyncReadExt, AsyncWriteExt};
use tokio::signal::unix::{signal, SignalKind};

fn debug_log(msg: &str) {
    if let Ok(path) = std::env::var("CURSOR_WRAPPER_DEBUG_LOG") {
        if !path.is_empty() {
            use std::io::Write;
            if let Ok(mut f) = std::fs::OpenOptions::new()
                .create(true)
                .append(true)
                .open(&path)
            {
                let _ = writeln!(f, "{msg}");
            }
        }
    }
}

const QUESTION_MARKER: &str = "\u{2191}/\u{2193} option \u{00b7} \u{2190}/\u{2192} question";

#[tokio::main]
async fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();

    let (pty, pts) = pty_process::open().unwrap_or_else(|e| {
        eprintln!("failed to create pty: {e}");
        std::process::exit(1);
    });

    if let Ok((cols, rows)) = crossterm::terminal::size() {
        let _ = pty.resize(pty_process::Size::new(rows, cols));
    }

    let pty_raw_fd = pty.as_raw_fd();

    let cursor_agent_bin = dirs::home_dir()
        .expect("could not determine home directory")
        .join(".local/bin/cursor-agent");

    let mut child = pty_process::Command::new(&cursor_agent_bin)
        .args(&args)
        .spawn(pts)
        .unwrap_or_else(|e| {
            eprintln!("failed to spawn {}: {e}", cursor_agent_bin.display());
            std::process::exit(1);
        });

    let (mut pty_reader, mut pty_writer) = pty.into_split();

    let is_tty = std::io::stdin().is_terminal();
    if is_tty {
        crossterm::terminal::enable_raw_mode().unwrap_or_else(|e| {
            eprintln!("failed to enable raw mode: {e}");
            std::process::exit(1);
        });
    }

    // Forward terminal resize (SIGWINCH) to the PTY
    tokio::spawn(async move {
        if let Ok(mut sigwinch) = signal(SignalKind::window_change()) {
            while sigwinch.recv().await.is_some() {
                if let Ok((cols, rows)) = crossterm::terminal::size() {
                    let ws = libc::winsize {
                        ws_row: rows,
                        ws_col: cols,
                        ws_xpixel: 0,
                        ws_ypixel: 0,
                    };
                    unsafe {
                        libc::ioctl(pty_raw_fd, libc::TIOCSWINSZ, &ws);
                    }
                }
            }
        }
    });

    let cfg = config::Config::load();
    debug_log(&format!(
        "config loaded, on_question={:?}, on_question_submit={:?}",
        cfg.hooks.on_question, cfg.hooks.on_question_submit
    ));

    let question_active = Arc::new(AtomicBool::new(false));

    // Relay stdin -> PTY
    let on_question_submit = cfg.hooks.on_question_submit.clone();
    let stdin_question_active = Arc::clone(&question_active);
    let _stdin_task = tokio::spawn(async move {
        let mut stdin = io::stdin();
        let mut buf = [0u8; 4096];
        loop {
            let n = match stdin.read(&mut buf).await {
                Ok(0) | Err(_) => break,
                Ok(n) => n,
            };
            let data = &buf[..n];

            if let Some(ref cmd) = on_question_submit {
                if data.contains(&b'\r') && stdin_question_active.load(Ordering::Relaxed) {
                    debug_log(&format!("QUESTION SUBMIT — running: {cmd}"));
                    let _ = std::process::Command::new("sh")
                        .args(["-c", cmd])
                        .stdout(std::process::Stdio::null())
                        .stderr(std::process::Stdio::null())
                        .status();
                }
            }

            if pty_writer.write_all(data).await.is_err() {
                break;
            }
        }
    });

    // Optionally dump all raw PTY output to a file (like tmux pipe-pane)
    let mut dump_file = match std::env::var("CURSOR_WRAPPER_DUMP_FILE") {
        Ok(path) if !path.is_empty() => Some(
            OpenOptions::new()
                .create(true)
                .truncate(true)
                .write(true)
                .open(&path)
                .await
                .unwrap_or_else(|e| {
                    eprintln!("failed to open dump file {path}: {e}");
                    std::process::exit(1);
                }),
        ),
        _ => None,
    };

    // Relay PTY -> stdout, watching for the question prompt
    let on_question = cfg.hooks.on_question.clone();
    let cooldown = Duration::from_millis(cfg.hooks.on_question_cooldown_ms);
    let stdout_question_active = Arc::clone(&question_active);
    let stdout_task = tokio::spawn(async move {
        let mut stdout = io::stdout();
        let mut buf = [0u8; 4096];
        let mut tail = Vec::new();
        let marker_bytes = QUESTION_MARKER.as_bytes();
        let mut marker_active = false;
        let mut last_match: Option<Instant> = None;

        loop {
            let n = match pty_reader.read(&mut buf).await {
                Ok(0) | Err(_) => break,
                Ok(n) => n,
            };

            let chunk = &buf[..n];

            if let Some(ref mut f) = dump_file {
                let _ = f.write_all(chunk).await;
                let _ = f.flush().await;
            }

            if let Some(ref cmd) = on_question {
                tail.extend_from_slice(chunk);
                const MAX_RAW_TAIL: usize = 8192;
                if tail.len() > MAX_RAW_TAIL {
                    let drain = tail.len() - MAX_RAW_TAIL;
                    tail.drain(..drain);
                }

                let stripped = strip_ansi_escapes::strip(&tail);
                let stripped_str = String::from_utf8_lossy(&stripped);
                let truncated: String = stripped_str.chars().rev().take(120).collect::<Vec<_>>().into_iter().rev().collect();
                debug_log(&format!(
                    "chunk: {} raw, tail: {} raw -> {} stripped: {:?}",
                    chunk.len(),
                    tail.len(),
                    stripped.len(),
                    truncated,
                ));

                let matched = stripped
                    .windows(marker_bytes.len())
                    .any(|w| w == marker_bytes);

                if matched {
                    if !marker_active
                        && last_match.is_none_or(|t| t.elapsed() > cooldown)
                    {
                        debug_log(&format!("MATCH — running: {cmd}"));
                        last_match = Some(Instant::now());
                        let _ = std::process::Command::new("sh")
                            .args(["-c", cmd])
                            .stdout(std::process::Stdio::null())
                            .stderr(std::process::Stdio::null())
                            .status();
                    }
                    marker_active = true;
                } else {
                    marker_active = false;
                }
                stdout_question_active.store(marker_active, Ordering::Relaxed);
            }

            if stdout.write_all(chunk).await.is_err() {
                break;
            }
            let _ = stdout.flush().await;
        }
    });

    let status = child.wait().await.unwrap_or_else(|e| {
        if is_tty {
            let _ = crossterm::terminal::disable_raw_mode();
        }
        eprintln!("failed to wait on cursor-agent: {e}");
        std::process::exit(1);
    });

    let _ = stdout_task.await;

    if is_tty {
        let _ = crossterm::terminal::disable_raw_mode();
    }

    std::process::exit(status.code().unwrap_or(1));
}
