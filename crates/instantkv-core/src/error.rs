#[derive(Debug, thiserror::Error)]
pub enum Error {
    #[error("{0}")]
    Invalid(String),
    #[error("namespace not found")]
    NamespaceNotFound,
    #[error("record not found or expired")]
    NotFound,
    #[error("revision or checkpoint conflict")]
    Conflict,
    #[error("namespace quota exceeded")]
    Quota,
    #[error("storage unavailable: {0}")]
    Storage(String),
}

pub type Result<T> = std::result::Result<T, Error>;

pub(crate) fn storage(error: impl std::fmt::Display) -> Error {
    Error::Storage(error.to_string())
}
