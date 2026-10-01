use anyhow::{Context, Result, bail};
use axum::http::HeaderMap;
use instantkv_core::config::{AuthMode, Config, Operation};
use sha2::{Digest, Sha256};
use std::{
    collections::{HashMap, HashSet},
    path::Path,
};
use subtle::ConstantTimeEq;

pub struct Auth {
    disabled: bool,
    principals: Vec<Principal>,
}
struct Principal {
    digest: [u8; 32],
    grants: HashMap<String, HashSet<Operation>>,
}

pub fn read_secrets(path: &Path) -> Result<HashMap<String, String>> {
    if !path.exists() {
        return Ok(HashMap::new());
    }
    let contents = std::fs::read_to_string(path).context("cannot read secrets file")?;
    let mut secrets = HashMap::new();
    for line in contents
        .lines()
        .map(str::trim)
        .filter(|line| !line.is_empty() && !line.starts_with('#'))
    {
        let (key, value) = line
            .split_once('=')
            .context("secrets file requires NAME=value lines")?;
        if secrets
            .insert(key.trim().to_owned(), value.trim().to_owned())
            .is_some()
        {
            bail!("duplicate name in secrets file");
        }
    }
    Ok(secrets)
}

impl Auth {
    pub fn load(config: &Config, secrets: &HashMap<String, String>) -> Result<Self> {
        config.validate().map_err(anyhow::Error::msg)?;
        let mut principals = Vec::new();
        let mut digests = HashSet::new();
        for principal in &config.auth.principals {
            let token = std::env::var(&principal.token_env)
                .ok()
                .or_else(|| secrets.get(&principal.token_env).cloned())
                .with_context(|| format!("missing secret {}", principal.token_env))?;
            if token.len() < 32 {
                bail!(
                    "{} must contain at least 32 bytes of a high-entropy token",
                    principal.token_env
                );
            }
            let digest: [u8; 32] = Sha256::digest(token.as_bytes()).into();
            if !digests.insert(digest) {
                bail!("principal credentials must have unique values");
            }
            principals.push(Principal {
                digest,
                grants: principal
                    .namespace_grants()
                    .into_iter()
                    .map(|grant| (grant.namespace, grant.operations.into_iter().collect()))
                    .collect(),
            });
        }
        Ok(Self {
            disabled: config.auth.mode == AuthMode::Disabled,
            principals,
        })
    }

    pub fn authorize(
        &self,
        headers: &HeaderMap,
        namespace: Option<&str>,
        operation: Operation,
    ) -> std::result::Result<HashSet<String>, u16> {
        if self.disabled {
            return Ok(HashSet::new());
        }
        let token = headers
            .get("authorization")
            .and_then(|value| value.to_str().ok())
            .and_then(|value| value.strip_prefix("Bearer "))
            .ok_or(401u16)?;
        let digest: [u8; 32] = Sha256::digest(token.as_bytes()).into();
        let principal = self
            .principals
            .iter()
            .find(|principal| bool::from(principal.digest.ct_eq(&digest)))
            .ok_or(401u16)?;
        let allowed = match namespace {
            Some(namespace) => principal
                .grants
                .get(namespace)
                .is_some_and(|operations| operations.contains(&operation)),
            None => principal
                .grants
                .values()
                .any(|operations| operations.contains(&operation)),
        };
        if !allowed {
            return Err(403);
        }
        Ok(principal
            .grants
            .iter()
            .filter(|(_, operations)| operations.contains(&Operation::Get))
            .map(|(namespace, _)| namespace.clone())
            .collect())
    }

    pub fn disabled(&self) -> bool {
        self.disabled
    }
}
