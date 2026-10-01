use anyhow::{Context, Result, bail};
use instantkv_core::model::{CheckpointReceipt, CheckpointRequest, Page, Restore, Usage};
use reqwest::{Client as HttpClient, Url};
use serde::de::DeserializeOwned;
use serde_json::Value;
use std::time::Duration;

#[derive(Clone)]
pub struct Client {
    http: HttpClient,
    base: Url,
    token: Option<String>,
}

impl Client {
    pub fn new(base: &str, token: Option<String>) -> Result<Self> {
        let base = Url::parse(base).context("invalid server URL")?;
        if !matches!(base.scheme(), "http" | "https")
            || base.host_str().is_none()
            || base.password().is_some()
            || !base.username().is_empty()
            || base.query().is_some()
            || base.fragment().is_some()
        {
            bail!("URL must be an HTTP(S) origin without credentials, query, or fragment");
        }
        let http = HttpClient::builder()
            .timeout(Duration::from_secs(30))
            .redirect(reqwest::redirect::Policy::none())
            .build()?;
        Ok(Self { http, base, token })
    }

    fn url(&self, segments: &[&str]) -> Result<Url> {
        let mut url = self.base.clone();
        let mut path = url
            .path_segments_mut()
            .map_err(|_| anyhow::anyhow!("URL cannot carry a path"))?;
        path.pop_if_empty();
        for segment in segments {
            path.push(segment);
        }
        drop(path);
        Ok(url)
    }

    fn request(
        &self,
        method: reqwest::Method,
        segments: &[&str],
    ) -> Result<reqwest::RequestBuilder> {
        let request = self.http.request(method, self.url(segments)?);
        Ok(if let Some(token) = &self.token {
            request.bearer_auth(token)
        } else {
            request
        })
    }

    async fn checked(response: reqwest::Response) -> Result<reqwest::Response> {
        if !response.status().is_success() {
            let status = response.status();
            let value: Value = response.json().await.unwrap_or_default();
            bail!(
                "HTTP {status}: {}",
                value
                    .pointer("/error/message")
                    .and_then(Value::as_str)
                    .unwrap_or("request rejected")
            );
        }
        Ok(response)
    }

    pub async fn health(&self) -> Result<Value> {
        Self::checked(
            self.request(reqwest::Method::GET, &["healthz"])?
                .send()
                .await?,
        )
        .await?
        .json()
        .await
        .context("invalid health response")
    }

    pub async fn put(
        &self,
        namespace: &str,
        key: &str,
        value: Vec<u8>,
        ttl: Option<u64>,
        revision: Option<u64>,
        absent: bool,
    ) -> Result<Value> {
        let mut request = self
            .request(
                reqwest::Method::PUT,
                &["v1", "namespaces", namespace, "records", key],
            )?
            .body(value);
        if let Some(ttl) = ttl {
            request = request.query(&[("ttl_seconds", ttl)]);
        }
        if let Some(revision) = revision {
            request = request.header("if-match", format!("\"{revision}\""));
        }
        if absent {
            request = request.header("if-none-match", "*");
        }
        Self::checked(request.send().await?)
            .await?
            .json()
            .await
            .context("invalid put response")
    }

    pub async fn get(&self, namespace: &str, key: &str) -> Result<(Vec<u8>, u64)> {
        let response = Self::checked(
            self.request(
                reqwest::Method::GET,
                &["v1", "namespaces", namespace, "records", key],
            )?
            .send()
            .await?,
        )
        .await?;
        let revision = response
            .headers()
            .get("etag")
            .context("missing ETag")?
            .to_str()?
            .trim_matches('"')
            .parse()?;
        Ok((response.bytes().await?.to_vec(), revision))
    }

    pub async fn list(
        &self,
        namespace: &str,
        prefix: &str,
        limit: usize,
        cursor: Option<&str>,
    ) -> Result<Page> {
        let mut request = self
            .request(
                reqwest::Method::GET,
                &["v1", "namespaces", namespace, "records"],
            )?
            .query(&[("prefix", prefix), ("limit", &limit.to_string())]);
        if let Some(cursor) = cursor {
            request = request.query(&[("cursor", cursor)]);
        }
        Self::checked(request.send().await?)
            .await?
            .json()
            .await
            .context("invalid list response")
    }

    pub async fn delete(&self, namespace: &str, key: &str, revision: Option<u64>) -> Result<()> {
        let mut request = self.request(
            reqwest::Method::DELETE,
            &["v1", "namespaces", namespace, "records", key],
        )?;
        if let Some(revision) = revision {
            request = request.header("if-match", format!("\"{revision}\""));
        }
        Self::checked(request.send().await?).await?;
        Ok(())
    }

    pub async fn stats(&self, namespace: &str) -> Result<Usage> {
        self.json_get(&["v1", "namespaces", namespace, "stats"])
            .await
    }
    pub async fn checkpoint(
        &self,
        namespace: &str,
        checkpoint: &CheckpointRequest,
    ) -> Result<CheckpointReceipt> {
        Self::checked(
            self.request(
                reqwest::Method::POST,
                &["v1", "namespaces", namespace, "checkpoints"],
            )?
            .json(checkpoint)
            .send()
            .await?,
        )
        .await?
        .json()
        .await
        .context("invalid checkpoint response")
    }
    pub async fn restore(&self, namespace: &str, id: &str, budget: usize) -> Result<Restore> {
        Self::checked(
            self.request(
                reqwest::Method::GET,
                &["v1", "namespaces", namespace, "checkpoints", id],
            )?
            .query(&[("max_bytes", budget)])
            .send()
            .await?,
        )
        .await?
        .json()
        .await
        .context("invalid restore response")
    }
    pub async fn restore_latest(
        &self,
        namespace: &str,
        agent: &str,
        session: &str,
        budget: usize,
    ) -> Result<Restore> {
        Self::checked(
            self.request(
                reqwest::Method::GET,
                &[
                    "v1",
                    "namespaces",
                    namespace,
                    "sessions",
                    agent,
                    session,
                    "latest",
                ],
            )?
            .query(&[("max_bytes", budget)])
            .send()
            .await?,
        )
        .await?
        .json()
        .await
        .context("invalid restore response")
    }
    async fn json_get<T: DeserializeOwned>(&self, segments: &[&str]) -> Result<T> {
        Self::checked(self.request(reqwest::Method::GET, segments)?.send().await?)
            .await?
            .json()
            .await
            .context("invalid response")
    }
}
