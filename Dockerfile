ARG BUILD_SOURCE=source-build
FROM rust:1.98-bookworm AS source-build
WORKDIR /build
COPY Cargo.toml Cargo.lock ./
COPY crates ./crates
COPY config ./config
RUN cargo build --release --locked --jobs 2 -p instantkv && cp target/release/instantkv /instantkv

FROM scratch AS prebuilt
COPY dist/instantkv /instantkv

FROM ${BUILD_SOURCE} AS build

FROM debian:bookworm-slim
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin instantkv \
    && mkdir /state && chown instantkv:instantkv /state
COPY --from=build /instantkv /usr/local/bin/instantkv
USER 10001:10001
WORKDIR /state
VOLUME ["/state"]
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD ["instantkv", "doctor"]
ENTRYPOINT ["instantkv"]
CMD ["serve", "--bind", "0.0.0.0:8080"]
