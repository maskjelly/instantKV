use std::time::{Instant, SystemTime, UNIX_EPOCH};

pub trait Clock: Send + Sync {
    fn unix_ms(&self) -> u64;
    fn tick_ms(&self) -> u64;
}

pub struct SystemClock(Instant);

impl Default for SystemClock {
    fn default() -> Self {
        Self(Instant::now())
    }
}

impl Clock for SystemClock {
    fn unix_ms(&self) -> u64 {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_millis()
            .min(u128::from(u64::MAX)) as u64
    }
    fn tick_ms(&self) -> u64 {
        self.0.elapsed().as_millis().min(u128::from(u64::MAX)) as u64
    }
}
