use crate::auth::{Auth, read_secrets};
use axum::{
    Extension, Json, Router,
    body::{Body, Bytes},
    extract::{DefaultBodyLimit, FromRequestParts, Path, Query, State},
    http::{HeaderMap, StatusCode, header},
    middleware::{self, Next},
    response::{IntoResponse, Response},
    routing::{get, post},
};
use instantkv_core::{
    Engine, Error,
    config::{Config, Operation, ValueKind},
    model::{CheckpointRequest, Condition},
};
use serde::Deserialize;
use serde_json::json;
use std::{
    path::Path as FilePath,
    sync::{
        Arc,
        atomic::{AtomicU64, Ordering},
    },
    time::Duration,
};
use tokio::sync::{OwnedSemaphorePermit, Semaphore};

type Permit = Arc<OwnedSemaphorePermit>;

#[derive(Clone)]
pub struct App {
    pub engine: Arc<Engine>,
    auth: Arc<Auth>,
    capacity: Arc<Semaphore>,
    requests: Arc<AtomicU64>,
    failures: Arc<AtomicU64>,
}

pub struct ApiError(StatusCode, &'static str, String);

impl From<Error> for ApiError {
    fn from(error: Error) -> Self {
        let (status, code) = match &error {
            Error::Invalid(_) => (StatusCode::BAD_REQUEST, "invalid_request"),
            Error::NotFound | Error::NamespaceNotFound => (StatusCode::NOT_FOUND, "not_found"),
            Error::Conflict => (StatusCode::CONFLICT, "conflict"),
            Error::Quota => (StatusCode::INSUFFICIENT_STORAGE, "quota_exceeded"),
            Error::Storage(_) => (StatusCode::SERVICE_UNAVAILABLE, "storage_unavailable"),
        };
        let message = if matches!(error, Error::Storage(_)) {
            tracing::error!(error = %error, "storage failure");
            "storage is unavailable; inspect server logs".into()
        } else {
            error.to_string()
        };
        Self(status, code, message)
    }
}

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        (self.0, Json(json!({"error": {"code": self.1, "message": self.2, "retryable": self.0 == StatusCode::SERVICE_UNAVAILABLE}}))).into_response()
    }
}

impl App {
    pub fn new(engine: Arc<Engine>, auth: Auth) -> Self {
        let capacity = Arc::new(Semaphore::new(
            engine.config.server.max_in_flight_requests as usize,
        ));
        Self {
            engine,
            auth: Arc::new(auth),
            capacity,
            requests: Arc::new(AtomicU64::new(0)),
            failures: Arc::new(AtomicU64::new(0)),
        }
    }
    fn authorize(
        &self,
        headers: &HeaderMap,
        namespace: Option<&str>,
        operation: Operation,
    ) -> Result<std::collections::HashSet<String>, ApiError> {
        self.auth
            .authorize(headers, namespace, operation)
            .map_err(|code| {
                if code == 401 {
                    ApiError(
                        StatusCode::UNAUTHORIZED,
                        "unauthorized",
                        "valid Bearer token required".into(),
                    )
                } else {
                    ApiError(
                        StatusCode::FORBIDDEN,
                        "forbidden",
                        "operation or namespace is outside your grants".into(),
                    )
                }
            })
    }
}

pub fn router(app: App) -> Router {
    let body_limit = app.engine.config.server.max_request_body_bytes as usize;
    Router::new()
        .route(
            "/healthz",
            get(|| async { Json(json!({"status":"ok", "version": env!("CARGO_PKG_VERSION")})) }),
        )
        .route("/metrics", get(metrics))
        .route("/v1/namespaces/{ns}/records", get(list))
        .route(
            "/v1/namespaces/{ns}/records/{*key}",
            get(read).put(write).delete(delete),
        )
        .route("/v1/namespaces/{ns}/stats", get(stats))
        .route("/v1/namespaces/{ns}/checkpoints", post(checkpoint))
        .route(
            "/v1/namespaces/{ns}/checkpoints/{id}",
            get(restore).delete(delete_checkpoint),
        )
        .route(
            "/v1/namespaces/{ns}/sessions/{agent}/{session}/latest",
            get(latest),
        )
        .fallback(|| async {
            ApiError(StatusCode::NOT_FOUND, "not_found", "route not found".into())
        })
        .layer(DefaultBodyLimit::max(body_limit))
        .layer(middleware::from_fn_with_state(app.clone(), gate))
        .with_state(app)
}

async fn gate(State(app): State<App>, mut request: axum::extract::Request, next: Next) -> Response {
    app.requests.fetch_add(1, Ordering::Relaxed);
    let permit = match app.capacity.clone().try_acquire_owned() {
        Ok(permit) => Arc::new(permit),
        Err(_) => {
            app.failures.fetch_add(1, Ordering::Relaxed);
            return ApiError(
                StatusCode::SERVICE_UNAVAILABLE,
                "overloaded",
                "server is at capacity; retry with backoff".into(),
            )
            .into_response();
        }
    };
    if request.uri().path().starts_with("/v1/namespaces/") {
        let (mut parts, body) = request.into_parts();
        let params = match Path::<std::collections::HashMap<String, String>>::from_request_parts(
            &mut parts, &app,
        )
        .await
        {
            Ok(Path(params)) => params,
            Err(_) => {
                return ApiError(
                    StatusCode::BAD_REQUEST,
                    "invalid_request",
                    "invalid route parameters".into(),
                )
                .into_response();
            }
        };
        let operation = match parts.method {
            axum::http::Method::PUT | axum::http::Method::POST => Operation::Put,
            axum::http::Method::DELETE => Operation::Delete,
            _ if parts.uri.path().ends_with("/stats") => Operation::Stats,
            _ if parts.uri.path().ends_with("/records") && !params.contains_key("key") => {
                Operation::List
            }
            _ => Operation::Get,
        };
        if let Err(error) = app.authorize(
            &parts.headers,
            params.get("ns").map(String::as_str),
            operation,
        ) {
            app.failures.fetch_add(1, Ordering::Relaxed);
            return error.into_response();
        }
        request = axum::extract::Request::from_parts(parts, body);
    }
    request.extensions_mut().insert(permit.clone());
    let result = tokio::time::timeout(
        Duration::from_secs(app.engine.config.server.request_timeout_seconds),
        next.run(request),
    )
    .await;
    let mut response = result.unwrap_or_else(|_| ApiError(StatusCode::GATEWAY_TIMEOUT, "timeout", "response deadline exceeded; a submitted write may still commit, inspect revision or retry checkpoint ID".into()).into_response());
    response.headers_mut().insert(
        header::CACHE_CONTROL,
        header::HeaderValue::from_static("no-store"),
    );
    if !response.status().is_success() {
        app.failures.fetch_add(1, Ordering::Relaxed);
    }
    response
}

async fn blocking<T: Send + 'static>(
    app: &App,
    permit: Permit,
    operation: impl FnOnce(Arc<Engine>) -> instantkv_core::Result<T> + Send + 'static,
) -> Result<T, ApiError> {
    let engine = app.engine.clone();
    tokio::task::spawn_blocking(move || {
        let _permit = permit;
        operation(engine)
    })
    .await
    .map_err(|_| {
        ApiError(
            StatusCode::INTERNAL_SERVER_ERROR,
            "internal_error",
            "storage task failed".into(),
        )
    })?
    .map_err(Into::into)
}

fn condition(headers: &HeaderMap) -> Result<Condition, ApiError> {
    let invalid = || {
        Error::Invalid("use exactly one of If-Match: \"revision\" or If-None-Match: *".into())
            .into()
    };
    match (
        headers.get(header::IF_MATCH),
        headers.get(header::IF_NONE_MATCH),
    ) {
        (None, None) => Ok(Condition::Any),
        (None, Some(value)) if value == "*" => Ok(Condition::Absent),
        (Some(value), None) => {
            let value = value.to_str().map_err(|_| invalid())?;
            let value = value
                .strip_prefix('"')
                .and_then(|value| value.strip_suffix('"'))
                .ok_or_else(invalid)?;
            let revision = value.parse::<u64>().map_err(|_| invalid())?;
            if revision == 0 {
                return Err(invalid());
            }
            Ok(Condition::Revision(revision))
        }
        _ => Err(invalid()),
    }
}

async fn read(
    State(app): State<App>,
    Extension(permit): Extension<Permit>,
    Path((ns, key)): Path<(String, String)>,
    headers: HeaderMap,
) -> Result<Response, ApiError> {
    app.authorize(&headers, Some(&ns), Operation::Get)?;
    let kind = app.engine.namespace(&ns)?.admission.value_kind.clone();
    let record = blocking(&app, permit, move |engine| engine.get(&ns, &key)).await?;
    let content_type = match kind {
        ValueKind::Bytes => "application/octet-stream",
        ValueKind::Utf8 => "text/plain; charset=utf-8",
        ValueKind::Json => "application/json",
    };
    Ok((
        [
            (header::CONTENT_TYPE, content_type.to_owned()),
            (header::ETAG, format!("\"{}\"", record.revision)),
        ],
        Body::from(record.value),
    )
        .into_response())
}

#[derive(Deserialize)]
struct WriteQuery {
    ttl_seconds: Option<u64>,
}
async fn write(
    State(app): State<App>,
    Extension(permit): Extension<Permit>,
    Path((ns, key)): Path<(String, String)>,
    Query(query): Query<WriteQuery>,
    headers: HeaderMap,
    bytes: Bytes,
) -> Result<Json<serde_json::Value>, ApiError> {
    app.authorize(&headers, Some(&ns), Operation::Put)?;
    let condition = condition(&headers)?;
    let record = blocking(&app, permit, move |engine| {
        engine.put(&ns, &key, bytes.to_vec(), query.ttl_seconds, condition)
    })
    .await?;
    Ok(Json(
        json!({"revision": record.revision, "bytes": record.value.len(), "written_at_ms": record.written_at_ms, "expires_at_ms": record.expires_at_ms}),
    ))
}

async fn delete(
    State(app): State<App>,
    Extension(permit): Extension<Permit>,
    Path((ns, key)): Path<(String, String)>,
    headers: HeaderMap,
) -> Result<StatusCode, ApiError> {
    app.authorize(&headers, Some(&ns), Operation::Delete)?;
    let condition = condition(&headers)?;
    blocking(&app, permit, move |engine| {
        engine.delete(&ns, &key, condition)
    })
    .await?;
    Ok(StatusCode::NO_CONTENT)
}

#[derive(Deserialize)]
struct ListQuery {
    #[serde(default)]
    prefix: String,
    #[serde(default = "default_limit")]
    limit: usize,
    cursor: Option<String>,
}
fn default_limit() -> usize {
    100
}
async fn list(
    State(app): State<App>,
    Extension(permit): Extension<Permit>,
    Path(ns): Path<String>,
    Query(query): Query<ListQuery>,
    headers: HeaderMap,
) -> Result<Json<instantkv_core::model::Page>, ApiError> {
    app.authorize(&headers, Some(&ns), Operation::List)?;
    Ok(Json(
        blocking(&app, permit, move |engine| {
            engine.list(&ns, &query.prefix, query.cursor.as_deref(), query.limit)
        })
        .await?,
    ))
}

async fn stats(
    State(app): State<App>,
    Extension(permit): Extension<Permit>,
    Path(ns): Path<String>,
    headers: HeaderMap,
) -> Result<Json<instantkv_core::model::Usage>, ApiError> {
    app.authorize(&headers, Some(&ns), Operation::Stats)?;
    Ok(Json(
        blocking(&app, permit, move |engine| engine.usage(&ns)).await?,
    ))
}

async fn checkpoint(
    State(app): State<App>,
    Extension(permit): Extension<Permit>,
    Path(ns): Path<String>,
    headers: HeaderMap,
    Json(request): Json<CheckpointRequest>,
) -> Result<Json<instantkv_core::model::CheckpointReceipt>, ApiError> {
    app.authorize(&headers, Some(&ns), Operation::Put)?;
    for reference in &request.references {
        app.authorize(&headers, Some(&reference.namespace), Operation::Get)?;
    }
    Ok(Json(
        blocking(&app, permit, move |engine| engine.checkpoint(&ns, &request)).await?,
    ))
}

async fn delete_checkpoint(
    State(app): State<App>,
    Extension(permit): Extension<Permit>,
    Path((ns, id)): Path<(String, String)>,
    headers: HeaderMap,
) -> Result<StatusCode, ApiError> {
    app.authorize(&headers, Some(&ns), Operation::Delete)?;
    blocking(&app, permit, move |engine| {
        engine.delete_checkpoint(&ns, &id)
    })
    .await?;
    Ok(StatusCode::NO_CONTENT)
}

#[derive(Deserialize)]
struct RestoreQuery {
    #[serde(default = "default_budget")]
    max_bytes: usize,
}
fn default_budget() -> usize {
    32768
}
async fn restore(
    State(app): State<App>,
    Extension(permit): Extension<Permit>,
    Path((ns, id)): Path<(String, String)>,
    Query(query): Query<RestoreQuery>,
    headers: HeaderMap,
) -> Result<Json<instantkv_core::model::Restore>, ApiError> {
    let allowed = app.authorize(&headers, Some(&ns), Operation::Get)?;
    let disabled = app.auth.disabled();
    Ok(Json(
        blocking(&app, permit, move |engine| {
            engine.restore(
                &ns,
                &id,
                query.max_bytes,
                if disabled { None } else { Some(&allowed) },
            )
        })
        .await?,
    ))
}
async fn latest(
    State(app): State<App>,
    Extension(permit): Extension<Permit>,
    Path((ns, agent, session)): Path<(String, String, String)>,
    Query(query): Query<RestoreQuery>,
    headers: HeaderMap,
) -> Result<Json<instantkv_core::model::Restore>, ApiError> {
    let allowed = app.authorize(&headers, Some(&ns), Operation::Get)?;
    let disabled = app.auth.disabled();
    Ok(Json(
        blocking(&app, permit, move |engine| {
            engine.restore_latest(
                &ns,
                &agent,
                &session,
                query.max_bytes,
                if disabled { None } else { Some(&allowed) },
            )
        })
        .await?,
    ))
}

async fn metrics(State(app): State<App>, headers: HeaderMap) -> Result<Response, ApiError> {
    app.authorize(&headers, None, Operation::Stats)?;
    let text = format!(
        "# TYPE instantkv_http_requests_total counter\ninstantkv_http_requests_total {}\n# TYPE instantkv_http_failures_total counter\ninstantkv_http_failures_total {}\n",
        app.requests.load(Ordering::Relaxed),
        app.failures.load(Ordering::Relaxed)
    );
    Ok(([(header::CONTENT_TYPE, "text/plain; version=0.0.4")], text).into_response())
}

pub async fn serve(config: Config, secrets_path: &FilePath) -> anyhow::Result<()> {
    let secrets = read_secrets(secrets_path)?;
    let auth = Auth::load(&config, &secrets)?;
    let bind = config.server.bind;
    let engine = Arc::new(tokio::task::spawn_blocking(move || Engine::open(config)).await??);
    let app = App::new(engine.clone(), auth);
    let listener = tokio::net::TcpListener::bind(bind).await?;
    let worker_app = app.clone();
    let cleanup = tokio::spawn(async move {
        let mut interval = tokio::time::interval(Duration::from_secs(
            worker_app.engine.config.storage.cleanup_interval_seconds,
        ));
        loop {
            interval.tick().await;
            if let Ok(permit) = worker_app.capacity.clone().try_acquire_owned() {
                let engine = worker_app.engine.clone();
                let result = tokio::task::spawn_blocking(move || {
                    let _permit = permit;
                    engine.cleanup()
                })
                .await;
                if !matches!(result, Ok(Ok(_))) {
                    tracing::error!("expiry cleanup failed");
                }
            }
        }
    });
    tracing::info!(address = %bind, "instantKV ready");
    let result = axum::serve(listener, router(app))
        .with_graceful_shutdown(shutdown())
        .await;
    cleanup.abort();
    result?;
    Ok(())
}

async fn shutdown() {
    #[cfg(unix)]
    {
        match tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate()) {
            Ok(mut terminate) => {
                tokio::select! { _ = tokio::signal::ctrl_c() => {}, _ = terminate.recv() => {} }
            }
            Err(_) => {
                let _ = tokio::signal::ctrl_c().await;
            }
        }
    }
    #[cfg(not(unix))]
    {
        let _ = tokio::signal::ctrl_c().await;
    }
}
