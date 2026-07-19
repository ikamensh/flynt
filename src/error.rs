//! Port of src/flynt/exceptions.py.

#[derive(Debug)]
pub enum FlyntError {
    /// Transformation is possible but refused (edge case we don't support).
    ConversionRefused(String),
    /// String nesting too deep to inline.
    StringEmbeddingTooDeep,
    /// Generic flynt error (Python: FlyntException).
    Generic(String),
}

impl std::fmt::Display for FlyntError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            FlyntError::ConversionRefused(msg) => write!(f, "conversion refused: {msg}"),
            FlyntError::StringEmbeddingTooDeep => write!(f, "string embedding too deep"),
            FlyntError::Generic(msg) => write!(f, "{msg}"),
        }
    }
}

impl FlyntError {
    /// The human-facing explanation, without the error-kind prefix — used for
    /// `-v` diagnostics where the surrounding `file:line:` already signals
    /// that a conversion was skipped.
    pub fn reason(&self) -> String {
        match self {
            FlyntError::ConversionRefused(msg) | FlyntError::Generic(msg) => msg.clone(),
            FlyntError::StringEmbeddingTooDeep => "string nesting too deep to inline".to_string(),
        }
    }
}

impl std::error::Error for FlyntError {}
