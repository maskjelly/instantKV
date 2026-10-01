//! Versioned, strict configuration with cross-field policy checks.

use serde::Deserialize;
use std::{collections::HashSet, net::SocketAddr, path::PathBuf};

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Config {
    pub version: u32,
    pub server: Server,
    pub storage: Storage,
    pub auth: Auth,
    pub namespaces: Vec<Namespace>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Server {
    pub bind: SocketAddr,
    pub max_request_body_bytes: u64,
    pub max_in_flight_requests: u32,
    pub request_timeout_seconds: u64,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Storage {
    pub data_dir: PathBuf,
    pub cleanup_interval_seconds: u64,
    pub cleanup_batch_entries: u32,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Auth {
    pub mode: AuthMode,
    #[serde(default)]
    pub principals: Vec<Principal>,
}

#[derive(Debug, PartialEq, Eq, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AuthMode {
    Disabled,
    ApiKey,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Principal {
    pub name: String,
    pub token_env: String,
    pub namespaces: Vec<String>,
    pub operations: Vec<Operation>,
}

#[derive(Debug, PartialEq, Eq, Hash, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Operation {
    Get,
    Put,
    Delete,
    List,
    Stats,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Namespace {
    pub name: String,
    pub mode: StorageMode,
    pub retention: Retention,
    pub admission: Admission,
    pub capacity: Capacity,
}

#[derive(Debug, PartialEq, Eq, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum StorageMode {
    Memory,
    Durable,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Retention {
    pub require_ttl: bool,
    pub default_ttl_seconds: Option<u64>,
    pub max_ttl_seconds: Option<u64>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Admission {
    pub value_kind: ValueKind,
    pub max_key_bytes: u32,
    pub max_value_bytes: u64,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ValueKind {
    Bytes,
    Utf8,
    Json,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Capacity {
    pub max_entries: u64,
    pub max_total_bytes: u64,
    pub on_full: OnFull,
}

#[derive(Debug, PartialEq, Eq, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum OnFull {
    Reject,
    EvictOldest,
}

impl Config {
    /// Parse TOML and reject contradictory or unsupported deployment policies.
    /// Does not read secret environment variables or access storage.
    pub fn parse(input: &str) -> Result<Self, String> {
        let config: Self = toml::from_str(input).map_err(|error| error.to_string())?;
        config.validate()?;
        Ok(config)
    }

    pub fn validate(&self) -> Result<(), String> {
        if self.version != 1 {
            return Err("version must be 1".into());
        }
        positive("server.bind port", u64::from(self.server.bind.port()))?;
        positive(
            "server.max_request_body_bytes",
            self.server.max_request_body_bytes,
        )?;
        positive(
            "server.max_in_flight_requests",
            u64::from(self.server.max_in_flight_requests),
        )?;
        positive(
            "server.request_timeout_seconds",
            self.server.request_timeout_seconds,
        )?;
        positive(
            "storage.cleanup_interval_seconds",
            self.storage.cleanup_interval_seconds,
        )?;
        positive(
            "storage.cleanup_batch_entries",
            u64::from(self.storage.cleanup_batch_entries),
        )?;
        if self.storage.data_dir.as_os_str().is_empty() {
            return Err("storage.data_dir must not be empty".into());
        }
        if self.namespaces.is_empty() {
            return Err("at least one namespace is required".into());
        }

        let mut names = HashSet::new();
        for namespace in &self.namespaces {
            if !valid_name(&namespace.name) || !names.insert(namespace.name.as_str()) {
                return Err(format!(
                    "namespace name '{}' must be unique and use 1-64 ASCII letters, digits, '_' or '-'",
                    namespace.name
                ));
            }
            namespace.validate(self.server.max_request_body_bytes)?;
        }

        match self.auth.mode {
            AuthMode::Disabled => {
                if !self.server.bind.ip().is_loopback() {
                    return Err("auth.mode = disabled requires a loopback bind address".into());
                }
                if !self.auth.principals.is_empty() {
                    return Err("disabled authentication cannot define principals".into());
                }
            }
            AuthMode::ApiKey => {
                if self.auth.principals.is_empty() {
                    return Err("api_key authentication requires at least one principal".into());
                }
                let mut principals = HashSet::new();
                let mut token_envs = HashSet::new();
                for principal in &self.auth.principals {
                    if !valid_name(&principal.name) || !principals.insert(principal.name.as_str()) {
                        return Err("principal names must be valid and unique".into());
                    }
                    if !valid_env_name(&principal.token_env)
                        || !token_envs.insert(principal.token_env.as_str())
                    {
                        return Err("principal token_env names must be valid and unique".into());
                    }
                    if principal.namespaces.is_empty() || principal.operations.is_empty() {
                        return Err(format!(
                            "principal '{}' needs explicit namespaces and operations",
                            principal.name
                        ));
                    }
                    let mut grants = HashSet::new();
                    for name in &principal.namespaces {
                        if !names.contains(name.as_str()) || !grants.insert(name) {
                            return Err(format!(
                                "principal '{}' references unknown or duplicate namespace '{name}'",
                                principal.name
                            ));
                        }
                    }
                    if principal.operations.iter().collect::<HashSet<_>>().len()
                        != principal.operations.len()
                    {
                        return Err(format!(
                            "principal '{}' has duplicate operations",
                            principal.name
                        ));
                    }
                }
            }
        }
        Ok(())
    }
}

impl Namespace {
    fn validate(&self, max_body: u64) -> Result<(), String> {
        let prefix = format!("namespace '{}'", self.name);
        for (name, value) in [
            ("max_key_bytes", u64::from(self.admission.max_key_bytes)),
            ("max_value_bytes", self.admission.max_value_bytes),
            ("max_entries", self.capacity.max_entries),
            ("max_total_bytes", self.capacity.max_total_bytes),
        ] {
            positive(&format!("{prefix}.{name}"), value)?;
        }
        if self.admission.max_value_bytes > max_body {
            return Err(format!(
                "{prefix}: max_value_bytes exceeds server.max_request_body_bytes"
            ));
        }
        let largest_entry = self
            .admission
            .max_value_bytes
            .checked_add(u64::from(self.admission.max_key_bytes))
            .ok_or_else(|| format!("{prefix}: entry size overflows byte accounting"))?;
        if largest_entry > self.capacity.max_total_bytes {
            return Err(format!(
                "{prefix}: max_total_bytes must fit one maximum-sized key and value"
            ));
        }
        if self.mode == StorageMode::Durable && self.capacity.on_full == OnFull::EvictOldest {
            return Err(format!(
                "{prefix}: evict_oldest is supported only for memory caches"
            ));
        }
        if let Some(default) = self.retention.default_ttl_seconds {
            positive(&format!("{prefix}.default_ttl_seconds"), default)?;
        }
        if let Some(maximum) = self.retention.max_ttl_seconds {
            positive(&format!("{prefix}.max_ttl_seconds"), maximum)?;
            if !self.retention.require_ttl {
                return Err(format!(
                    "{prefix}: max_ttl_seconds requires require_ttl = true so immortal writes cannot bypass the limit"
                ));
            }
            if self
                .retention
                .default_ttl_seconds
                .is_some_and(|default| default > maximum)
            {
                return Err(format!("{prefix}: default TTL exceeds maximum TTL"));
            }
        }
        Ok(())
    }
}

fn positive(name: &str, value: u64) -> Result<(), String> {
    if value == 0 {
        return Err(format!("{name} must be greater than zero"));
    }
    Ok(())
}

fn valid_name(name: &str) -> bool {
    (1..=64).contains(&name.len())
        && name
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || byte == b'_' || byte == b'-')
}

fn valid_env_name(name: &str) -> bool {
    let mut bytes = name.bytes();
    bytes
        .next()
        .is_some_and(|byte| byte.is_ascii_uppercase() || byte == b'_')
        && bytes.all(|byte| byte.is_ascii_uppercase() || byte.is_ascii_digit() || byte == b'_')
}
