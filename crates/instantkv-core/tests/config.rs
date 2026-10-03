use instantkv_core::config::{AuthMode, Config, OnFull, StorageMode};

const AGENT: &str = include_str!("../../../config/instantkv.example.toml");
const CACHE: &str = include_str!("../../../config/local-cache.toml");
const SWARM: &str = include_str!("../../../config/swarm.toml");
const LOCAL: &str = include_str!("../../../config/local.toml");

#[test]
fn local_profile_bounds_resources_without_expiring_durable_memory() {
    let config = Config::parse(LOCAL).unwrap();
    assert_eq!(config.auth.mode, AuthMode::ApiKey);
    assert!(config.server.bind.ip().is_loopback());
    assert_eq!(config.storage.cache_size_bytes, Some(8 * 1024 * 1024));
    assert!(
        Config::parse(&LOCAL.replace("cache_size_bytes = 8388608", "cache_size_bytes = 0"))
            .is_err()
    );
    assert_eq!(Config::parse(AGENT).unwrap().storage.cache_size_bytes, None);
    for namespace in config
        .namespaces
        .iter()
        .filter(|ns| ns.mode == StorageMode::Durable)
    {
        assert_eq!(namespace.capacity.on_full, OnFull::Reject);
        assert!(!namespace.retention.require_ttl);
        assert!(namespace.retention.default_ttl_seconds.is_none());
    }
    let scratch = config
        .namespaces
        .iter()
        .find(|ns| ns.name == "scratch")
        .unwrap();
    assert_eq!(scratch.capacity.max_total_bytes, 4 * 1024 * 1024);
}

#[test]
fn swarm_grants_reject_ambiguous_or_invalid_permissions() {
    let config = Config::parse(SWARM).unwrap();
    assert_eq!(config.namespaces.len(), 5);
    for input in [
        SWARM.replacen("token_env = \"INSTANTKV_ALPHA_TOKEN\"", "token_env = \"INSTANTKV_ALPHA_TOKEN\"\nnamespaces = [\"shared\"]\noperations = [\"put\"]", 1),
        SWARM.replacen("namespace = \"shared\"", "namespace = \"unknown\"", 1),
        SWARM.replacen("namespace = \"alpha\"", "namespace = \"shared\"", 1),
        SWARM.replacen("operations = [\"get\", \"list\"]", "operations = []", 1),
        SWARM.replacen("operations = [\"get\", \"list\"]", "operations = [\"get\", \"get\"]", 1),
    ] {
        assert!(Config::parse(&input).is_err(), "accepted invalid grants");
    }
}

#[test]
fn agent_profile_preserves_knowledge_and_checkpoints() {
    let config = Config::parse(AGENT).unwrap();
    assert_eq!(config.auth.mode, AuthMode::ApiKey);
    for name in ["knowledge", "checkpoints"] {
        let namespace = config.namespaces.iter().find(|ns| ns.name == name).unwrap();
        assert_eq!(namespace.mode, StorageMode::Durable);
        assert_eq!(namespace.capacity.on_full, OnFull::Reject);
        assert!(namespace.retention.default_ttl_seconds.is_none());
        assert!(namespace.retention.max_ttl_seconds.is_none());
    }
}

#[test]
fn local_cache_profile_is_loopback_and_disposable() {
    let config = Config::parse(CACHE).unwrap();
    assert_eq!(config.auth.mode, AuthMode::Disabled);
    assert!(config.server.bind.ip().is_loopback());
    assert_eq!(config.namespaces[0].mode, StorageMode::Memory);
}

#[test]
fn unknown_fields_and_enum_values_fail_closed() {
    for malformed in [
        CACHE.replacen("version = 1", "version = 1\nunknown_policy = true", 1),
        CACHE.replace("max_key_bytes", "max_kye_bytes"),
        CACHE.replace("\"evict_oldest\"", "\"silently_drop\""),
        CACHE.replace("value_kind = \"bytes\"", "value_kind = \"anything\""),
    ] {
        assert!(Config::parse(&malformed).is_err());
    }
}

#[test]
fn contradictory_policies_are_rejected() {
    let cases = [
        (CACHE.replace("version = 1", "version = 2"), "version"),
        (CACHE.replace("127.0.0.1:8080", "0.0.0.0:8080"), "loopback"),
        (CACHE.replace("127.0.0.1:8080", "[::]:8080"), "loopback"),
        (
            CACHE.replace("max_entries = 10000", "max_entries = 0"),
            "greater than zero",
        ),
        (
            CACHE.replace("default_ttl_seconds = 300", "default_ttl_seconds = 4000"),
            "exceeds maximum",
        ),
        (
            CACHE.replace("require_ttl = true", "require_ttl = false"),
            "requires require_ttl",
        ),
        (
            CACHE.replace("max_value_bytes = 65536", "max_value_bytes = 65537"),
            "max_request_body_bytes",
        ),
        (
            CACHE.replace("max_total_bytes = 67108864", "max_total_bytes = 65536"),
            "maximum-sized key and value",
        ),
        (
            CACHE.replace("mode = \"memory\"", "mode = \"durable\""),
            "only for memory",
        ),
        (
            AGENT.replace("namespaces = [\"knowledge\"]", "namespaces = [\"missing\"]"),
            "unknown or duplicate namespace",
        ),
        (
            AGENT.replace("INSTANTKV_READER_TOKEN", "INSTANTKV_APP_TOKEN"),
            "token_env",
        ),
        (
            AGENT.replace("INSTANTKV_READER_TOKEN", "bad-token"),
            "token_env",
        ),
        (
            AGENT.replace("operations = [\"get\", \"list\"]", "operations = []"),
            "explicit namespaces and operations",
        ),
    ];
    for (input, expected_error) in cases {
        let error = Config::parse(&input).unwrap_err();
        assert!(
            error.contains(expected_error),
            "expected '{expected_error}', got '{error}'"
        );
    }
}

#[test]
fn duplicate_namespace_cannot_create_ambiguous_grants() {
    let mut config = Config::parse(AGENT).unwrap();
    config.namespaces[1].name = config.namespaces[0].name.clone();
    assert!(config.validate().unwrap_err().contains("must be unique"));
}

#[test]
fn explicit_ttl_without_default_is_valid_when_required() {
    let input = CACHE.replace("default_ttl_seconds = 300\n", "");
    let config = Config::parse(&input).unwrap();
    assert!(config.namespaces[0].retention.require_ttl);
    assert!(config.namespaces[0].retention.default_ttl_seconds.is_none());
}
#[test]
fn memory_query_budgets_default_for_old_configs_and_reject_invalid_bounds() {
    let mut config = instantkv_core::config::Config::parse(include_str!(
        "../../../config/instantkv.example.toml"
    ))
    .unwrap();
    assert_eq!(config.memory.max_candidates, 1000);
    assert_eq!(config.memory.max_search_postings, 20000);
    assert_eq!(config.memory.max_result_bytes, 65536);
    config.memory.max_search_postings = 0;
    assert!(config.validate().is_err());
    config.memory.max_search_postings = 1_000_001;
    assert!(config.validate().is_err());
    config.memory.max_search_postings = 20000;
    config.memory.max_candidates = 0;
    assert!(config.validate().is_err());
    config.memory.max_candidates = 100;
    config.memory.max_scan_bytes = 1;
    assert!(config.validate().is_err());
    config.memory.max_scan_bytes = 65536;
    config.memory.max_result_bytes = 1048577;
    assert!(config.validate().is_err());
}
