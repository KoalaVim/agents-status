use serde::Deserialize;
use std::path::PathBuf;

#[derive(Debug, Clone, Default, Deserialize)]
pub struct Config {
    #[serde(default)]
    pub hooks: Hooks,
}

#[derive(Debug, Clone, Default, Deserialize)]
pub struct Hooks {
    #[serde(default, rename = "on-question")]
    pub on_question: Option<String>,

    #[serde(default, rename = "on-question-submit")]
    pub on_question_submit: Option<String>,

    #[serde(default = "default_cooldown_ms", rename = "on-question-cooldown-ms")]
    pub on_question_cooldown_ms: u64,
}

fn default_cooldown_ms() -> u64 {
    500
}

impl Config {
    pub fn load() -> Self {
        Self::config_path()
            .and_then(|path| std::fs::read_to_string(&path).ok())
            .and_then(|contents| toml::from_str::<Config>(&contents).ok())
            .unwrap_or_default()
    }

    fn config_path() -> Option<PathBuf> {
        dirs::config_dir().map(|d| d.join("cursor-cli-wrapper").join("config.toml"))
    }
}
