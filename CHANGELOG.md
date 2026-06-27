# Changelog

## [0.4.3](https://github.com/AstorisTheBrave/argus/compare/v0.4.2...v0.4.3) (2026-06-26)


### Features

* **api:** ergonomic timed / timer / count_exceptions / span wrappers ([#68](https://github.com/AstorisTheBrave/argus/issues/68)) ([46d4d15](https://github.com/AstorisTheBrave/argus/commit/46d4d150b48ab8a69b862e16401c13568e9f5c34))
* **dashboard:** Grafana-style panels, embedded board tabs, denser layout ([#74](https://github.com/AstorisTheBrave/argus/issues/74)) ([1037a45](https://github.com/AstorisTheBrave/argus/commit/1037a4550611b8cd25e3efccbafd7992134aa2c6))
* **dashboard:** Setup nav tab and auto-loading analytics ([#75](https://github.com/AstorisTheBrave/argus/issues/75)) ([0bc1dae](https://github.com/AstorisTheBrave/argus/commit/0bc1dae0a8179f9bf914911bdf319a0ad68836d7))
* **metrics:** process/runtime collectors, event-loop lag, ws rate-limit gauge ([#67](https://github.com/AstorisTheBrave/argus/issues/67)) ([bf2d1d9](https://github.com/AstorisTheBrave/argus/commit/bf2d1d9190a82665b89aba8cee6d8d23a7de0335))
* **ops:** durable inserts, safe asset serving, bounded timers, auth logging ([#69](https://github.com/AstorisTheBrave/argus/issues/69)) ([1cd0a16](https://github.com/AstorisTheBrave/argus/commit/1cd0a162f9fe984b093bfc6739b086b87d19572a))
* **setup:** no-code setup wizard in the dashboard SPA ([#72](https://github.com/AstorisTheBrave/argus/issues/72)) ([2d2ad13](https://github.com/AstorisTheBrave/argus/commit/2d2ad13cb702c8481ecedbb66fb33634048cb3f3))
* **tracing:** OpenTelemetry spans per command/interaction lifecycle ([#60](https://github.com/AstorisTheBrave/argus/issues/60)) ([a1fb3d0](https://github.com/AstorisTheBrave/argus/commit/a1fb3d0f2fd683e4ca1ba06218d6e79578de637f))


### Bug Fixes

* **ci:** make frontend native binding install deterministic ([#70](https://github.com/AstorisTheBrave/argus/issues/70)) ([94137a7](https://github.com/AstorisTheBrave/argus/commit/94137a7dddcd2c38df831523a61b442777233034))
* **compose:** require a Grafana password and enable dashboard embedding ([#77](https://github.com/AstorisTheBrave/argus/issues/77)) ([e87f821](https://github.com/AstorisTheBrave/argus/commit/e87f82108540c1bdc3c9cbac2d691b50f22b87d2))
* **dashboard:** allow embedding the configured Grafana in the page CSP ([#76](https://github.com/AstorisTheBrave/argus/issues/76)) ([b957171](https://github.com/AstorisTheBrave/argus/commit/b957171b41efe1e91d1f392709eb433cc9ce7827))
* **dashboard:** serve the bundled Nimble theme from /nimble ([#73](https://github.com/AstorisTheBrave/argus/issues/73)) ([6d26142](https://github.com/AstorisTheBrave/argus/commit/6d261426ada62db4cddb6cbd816c398063edfa3a))
* **deps:** pin aiohttp &gt;= 3.14.1 and add a ClickHouse-injection regression test ([#66](https://github.com/AstorisTheBrave/argus/issues/66)) ([c553531](https://github.com/AstorisTheBrave/argus/commit/c553531611e91c5d0b28102a21f7c048d171ddfb))

## [0.4.2](https://github.com/AstorisTheBrave/argus/compare/v0.4.1...v0.4.2) (2026-06-21)


### Features

* **config:** eager .env bootstrap and host-port auto-detect ([#54](https://github.com/AstorisTheBrave/argus/issues/54)) ([b6c57cf](https://github.com/AstorisTheBrave/argus/commit/b6c57cf1f90b03456de018bc01d96c02b10e8d67))
* **core:** fail-open metrics server, scrape isolation, and self-health ([#43](https://github.com/AstorisTheBrave/argus/issues/43)) ([cb421b6](https://github.com/AstorisTheBrave/argus/commit/cb421b6d1a6757627cc98131caf864e7ce44efcd))
* **dashboard:** harden the in-process bot server to match the fleet plane ([#44](https://github.com/AstorisTheBrave/argus/issues/44)) ([b96a838](https://github.com/AstorisTheBrave/argus/commit/b96a8386130f3748523e7e815f8f109bcf97f0d2))
* **dashboard:** optional bearer auth for the /metrics endpoint ([#56](https://github.com/AstorisTheBrave/argus/issues/56)) ([c1ad15c](https://github.com/AstorisTheBrave/argus/commit/c1ad15c496f0bdb6b5ce6b63c941510d1c09dc60))
* **fleet:** accept multiple tokens for zero-downtime rotation ([#40](https://github.com/AstorisTheBrave/argus/issues/40)) ([eb99c92](https://github.com/AstorisTheBrave/argus/commit/eb99c921e2a1981f107fd95107a2c3cb72c46f09))
* **fleet:** per-identity lease secrets (un-shareable, rotatable identity) ([#41](https://github.com/AstorisTheBrave/argus/issues/41)) ([92b4863](https://github.com/AstorisTheBrave/argus/commit/92b4863ce65f76f6aa69c1094793473b738cd307))
* **fleet:** read-side rate limit and optional audit log ([#42](https://github.com/AstorisTheBrave/argus/issues/42)) ([db2f5d1](https://github.com/AstorisTheBrave/argus/commit/db2f5d1b0e0759002e9b6306fae1892b7acabdb5))
* **history:** drop counter, resilient sink worker, idempotent Argus(bot) ([#45](https://github.com/AstorisTheBrave/argus/issues/45)) ([a2efd36](https://github.com/AstorisTheBrave/argus/commit/a2efd369a9f694e033e143179159b253a3e41f5c))
* **history:** sink circuit breaker drives live argus_subsystem_up{sink} ([#51](https://github.com/AstorisTheBrave/argus/issues/51)) ([7d5b2d2](https://github.com/AstorisTheBrave/argus/commit/7d5b2d2fd2f0fe317fd5e5acf68bfcf16a05ee1f))
* **logging:** opt-in JSON logging for the bot side ([#52](https://github.com/AstorisTheBrave/argus/issues/52)) ([692d903](https://github.com/AstorisTheBrave/argus/commit/692d903276db15570c787683dcd5b5da4dec3fe0))
* **observability:** optional Prometheus Pushgateway push (no inbound port) ([#58](https://github.com/AstorisTheBrave/argus/issues/58)) ([4819152](https://github.com/AstorisTheBrave/argus/commit/48191525bc8f2812bff188435baa81555ab065eb))
* **observability:** ship Prometheus alert/recording rules and a health dashboard ([#46](https://github.com/AstorisTheBrave/argus/issues/46)) ([9b9367c](https://github.com/AstorisTheBrave/argus/commit/9b9367c11ec169d1988f2b8dbf3d6a15c7307264))
* **observability:** SLO burn-rate alerts and a golden-signals dashboard row ([#53](https://github.com/AstorisTheBrave/argus/issues/53)) ([b9ec60c](https://github.com/AstorisTheBrave/argus/commit/b9ec60c8623ac7dce5d1f0edc139ca5993366713))


### Bug Fixes

* **fleet:** default member identity to cluster_id; fix copy-paste quickstart ([#38](https://github.com/AstorisTheBrave/argus/issues/38)) ([791c587](https://github.com/AstorisTheBrave/argus/commit/791c5879b1465a5ab61b63aabc5569dd15cc49dc))
* **fleet:** write state and identity files owner-only (0600) ([#39](https://github.com/AstorisTheBrave/argus/issues/39)) ([89f9fea](https://github.com/AstorisTheBrave/argus/commit/89f9feaecd0cb1f9fffe6b05228fcdfb0a7e25e2))


### Documentation

* clarify cluster_id is always distinct, ports only differ when co-located ([#36](https://github.com/AstorisTheBrave/argus/issues/36)) ([2d5d040](https://github.com/AstorisTheBrave/argus/commit/2d5d04019b315970bcc5596fe3738c1da937299d))
* **hosting:** recipes for Pterodactyl, PebbleHost, Ori, and Railway ([#55](https://github.com/AstorisTheBrave/argus/issues/55)) ([b90503d](https://github.com/AstorisTheBrave/argus/commit/b90503d7914aa424e318417a2fb241a849102e54))
* lead with push (no inbound port) for Docker bot hosts ([#57](https://github.com/AstorisTheBrave/argus/issues/57)) ([af21611](https://github.com/AstorisTheBrave/argus/commit/af21611adbcfb89d22e9f8e393c9d7736e9499de))
* **readme:** add a How Argus works section with an architecture diagram ([#49](https://github.com/AstorisTheBrave/argus/issues/49)) ([36c3dbf](https://github.com/AstorisTheBrave/argus/commit/36c3dbf47c303184130cf64d07567bfa6fecf12c))

## [0.4.1](https://github.com/AstorisTheBrave/argus/compare/v0.4.0...v0.4.1) (2026-06-21)


### Features

* **fleet:** add a shard tier under clusters ([#32](https://github.com/AstorisTheBrave/argus/issues/32)) ([aeafa51](https://github.com/AstorisTheBrave/argus/commit/aeafa51d487c3f75396e3d4194ff698080bf635e))
* **fleet:** per-guild analytics in the control-plane pane ([#33](https://github.com/AstorisTheBrave/argus/issues/33)) ([06b921f](https://github.com/AstorisTheBrave/argus/commit/06b921f70b7a74651cd91972747c044417a4397c))


### Documentation

* add llms.txt and production examples (every setup + dos/don'ts) ([#35](https://github.com/AstorisTheBrave/argus/issues/35)) ([0d5d323](https://github.com/AstorisTheBrave/argus/commit/0d5d323d396e69bd3e4eb1b082ffe0cf15aaaf09))
* **readme:** add Security and Examples sections, release-notes links ([#30](https://github.com/AstorisTheBrave/argus/issues/30)) ([e80f4ee](https://github.com/AstorisTheBrave/argus/commit/e80f4ee5f90eaab6bf27c4e5880a2b2ef1b54dce))

## [0.4.0](https://github.com/AstorisTheBrave/argus/compare/v0.3.1...v0.4.0) (2026-06-21)


### Features

* **core:** time prefix (text) command duration ([#28](https://github.com/AstorisTheBrave/argus/issues/28)) ([3c0a4e0](https://github.com/AstorisTheBrave/argus/commit/3c0a4e01bf76c0f628eefb59d6995e39b03cecf1))
* **fleet:** cluster drill-down trend history with sparklines ([#25](https://github.com/AstorisTheBrave/argus/issues/25)) ([23ae1a5](https://github.com/AstorisTheBrave/argus/commit/23ae1a5e2cafec3aacf543d0f81cf242c7b8ac3f))
* **fleet:** flap detection, source-failure resilience, fuzz/load tests + tutorials ([#21](https://github.com/AstorisTheBrave/argus/issues/21)) ([c680e4d](https://github.com/AstorisTheBrave/argus/commit/c680e4d5ee75db8e51d1e5a47119daef64c63c96))
* **fleet:** graceful shutdown, JSON logging, image hardening, k8s example ([#26](https://github.com/AstorisTheBrave/argus/issues/26)) ([153ad01](https://github.com/AstorisTheBrave/argus/commit/153ad01bf240db005af7601192e9075e4bb16832))
* **fleet:** hardening slice 1 - secure defaults, efficiency, reliability ([#16](https://github.com/AstorisTheBrave/argus/issues/16)) ([6f72a06](https://github.com/AstorisTheBrave/argus/commit/6f72a066d24deaa9e93089d2a8639edc28185c4c))
* **fleet:** hardening slice 2 - setup wizard, doctor, DX ([#17](https://github.com/AstorisTheBrave/argus/issues/17)) ([45bfb6c](https://github.com/AstorisTheBrave/argus/commit/45bfb6c29c9dfe60817309b63c027c5d790575ec))
* **fleet:** hardening slice 4 - rate limiting, retention, single-writer lock ([#19](https://github.com/AstorisTheBrave/argus/issues/19)) ([33d2ad7](https://github.com/AstorisTheBrave/argus/commit/33d2ad754021cb485d26b62c9c86dc538525f552))
* **fleet:** hardening slice 5 - Prometheus http_sd auto-discovery ([#20](https://github.com/AstorisTheBrave/argus/issues/20)) ([312ce8b](https://github.com/AstorisTheBrave/argus/commit/312ce8bc2ac3d35dc1a9e5a126511514d2006532))
* **fleet:** split ingest and viewer tokens ([#18](https://github.com/AstorisTheBrave/argus/issues/18)) ([b3c726e](https://github.com/AstorisTheBrave/argus/commit/b3c726e9c466a30e440fe2e494e00c8a405265f1))
* **fleet:** standalone Argus Fleet control plane ([#14](https://github.com/AstorisTheBrave/argus/issues/14)) ([79f4c2a](https://github.com/AstorisTheBrave/argus/commit/79f4c2acf099649a946d07573c5a9320b19649e3))
* **fleet:** trusted-proxy client IP, heartbeat jitter, view-build latency metric ([#24](https://github.com/AstorisTheBrave/argus/issues/24)) ([523dc7d](https://github.com/AstorisTheBrave/argus/commit/523dc7da0d48215f92aeaf21961ed4e4165f3055))


### Bug Fixes

* **fleet:** make the member client unconditionally fail-open ([#22](https://github.com/AstorisTheBrave/argus/issues/22)) ([7ee0d16](https://github.com/AstorisTheBrave/argus/commit/7ee0d16bae410572f23c9d61f828969ef73cd4de))
* **fleet:** resolve CodeQL log-injection and ineffectual-statement alerts ([#23](https://github.com/AstorisTheBrave/argus/issues/23)) ([7a89cbe](https://github.com/AstorisTheBrave/argus/commit/7a89cbe7d78511bf38d34dd650a6a9222db84896))

## [0.3.1](https://github.com/AstorisTheBrave/argus/compare/v0.3.0...v0.3.1) (2026-06-20)


### Bug Fixes

* **dashboard:** remember a ?token= link; docs: minimal setup in README ([#11](https://github.com/AstorisTheBrave/argus/issues/11)) ([7dd7cf0](https://github.com/AstorisTheBrave/argus/commit/7dd7cf0f3ab734ba4024afbc72325cb1e2be4801))

## [0.3.0](https://github.com/AstorisTheBrave/argus/compare/v0.2.1...v0.3.0) (2026-06-20)


### Features

* observability expansion, OTLP, analytics, dashboard, ops ([#9](https://github.com/AstorisTheBrave/argus/issues/9)) ([05dbd45](https://github.com/AstorisTheBrave/argus/commit/05dbd452ab5c9d3768357be07c4572a57310fbf0))

## [0.2.1](https://github.com/AstorisTheBrave/argus/compare/v0.2.0...v0.2.1) (2026-06-19)


### Bug Fixes

* **dashboard:** ship only subset Geist + Geist Mono, slim the wheel ([#7](https://github.com/AstorisTheBrave/argus/issues/7)) ([80c0282](https://github.com/AstorisTheBrave/argus/commit/80c02826c4d2830b13cd57b5b097ec29c42f66c1))

## [0.2.0](https://github.com/AstorisTheBrave/argus/compare/v0.1.0...v0.2.0) (2026-06-17)


### Features

* **adapters:** add Prometheus adapter with hybrid registry (invariant 4) ([efea3f0](https://github.com/AstorisTheBrave/argus/commit/efea3f05e58d09731221ed2335bde331e1132d6a))
* add ArgusCog and the one-line Argus(bot) integration ([43cb69a](https://github.com/AstorisTheBrave/argus/commit/43cb69a2642fda0486fff565fb289b611595c89c))
* **config:** add ArgusConfig with kwargs&gt;env&gt;defaults precedence ([f71f721](https://github.com/AstorisTheBrave/argus/commit/f71f7212b9aff4e9ab6f9ba1e2502968226c7447))
* **config:** add dashboard/history settings ([8966a8f](https://github.com/AstorisTheBrave/argus/commit/8966a8fd905c91a3894bad1273233518dd280dcb))
* **core:** add hooks + fail-open instrumentation (invariants 3, 5) ([5e47799](https://github.com/AstorisTheBrave/argus/commit/5e4779909b46e274a66b99dca8740b3e6d58e040))
* **core:** add neutral MetricRegistry and metric model ([b66fac2](https://github.com/AstorisTheBrave/argus/commit/b66fac2cb6a0cc0aa9201be8b3c6abdf35729ea0))
* **core:** define the v1 metric catalogue (spec sec.8) ([eb34c4c](https://github.com/AstorisTheBrave/argus/commit/eb34c4c79e123bf4395e10a710dc3ae3bd5d3c36))
* **dashboard:** add bearer-token auth middleware ([f9ddbdd](https://github.com/AstorisTheBrave/argus/commit/f9ddbdd3df5f446e13efc9be9ee09bd6bbce80bd))
* **dashboard:** analytics API (fail-closed) + ClickHouse wiring ([c72a3c8](https://github.com/AstorisTheBrave/argus/commit/c72a3c805fef4801ac06f4924939337f0e856823))
* **dashboard:** JSON metric snapshot ([913c840](https://github.com/AstorisTheBrave/argus/commit/913c840cf6b7c4b8d9cf38266dbdf9822e0842e5))
* **dashboard:** serve SPA shell + /api/config ([87128d3](https://github.com/AstorisTheBrave/argus/commit/87128d3ff7440c5066143ec3b10a7d6bae812d76))
* **dashboard:** SSE metric stream at /api/stream ([ca72b9f](https://github.com/AstorisTheBrave/argus/commit/ca72b9f1f96729507f5d2438d0c09674cb8174b7))
* **dashboard:** wire dashboard into ArgusCog ([8daa7b6](https://github.com/AstorisTheBrave/argus/commit/8daa7b6b6b50daaa261daec5cdef5f8c1c07cc89))
* **exposition:** aiohttp /metrics + /healthz on the bot loop ([7dc8e98](https://github.com/AstorisTheBrave/argus/commit/7dc8e9891c56d54464b0b2fa5b3399171522a066))
* **frontend:** metrics data layer ([5968f28](https://github.com/AstorisTheBrave/argus/commit/5968f282810c0ec516db38f5d7b114ab61291878))
* **frontend:** scaffold Vite+React+TS SPA with Nimble assets ([43e8dac](https://github.com/AstorisTheBrave/argus/commit/43e8dac73f9ffd9719d70d053e5f5de73f4dfbf9))
* **frontend:** sidebar hub with overview, interactions, gateway, grafana, analytics ([a3968d2](https://github.com/AstorisTheBrave/argus/commit/a3968d2b6dbb8f822b9aaafc8b4515693c487073))
* **history:** ClickHouse sink + analytics queries ([3ab9aca](https://github.com/AstorisTheBrave/argus/commit/3ab9aca422de25ed8386a3db23c81d4a473d5c32))
* **history:** EventSink ABC, NullSink and non-blocking BatchingSink ([a3b6e99](https://github.com/AstorisTheBrave/argus/commit/a3b6e9900213065a149a88206969843efadb1fc2))
* **history:** per-guild event capture behind enable_per_guild ([0f56009](https://github.com/AstorisTheBrave/argus/commit/0f5600986241d55b31c0f2052dcfb90555004a69))
* **stack:** add Grafana dashboards, provisioning, compose, scrape config ([3be5320](https://github.com/AstorisTheBrave/argus/commit/3be5320e6c3a7bd26213e98f9fea310a4b6e4c57))


### Bug Fixes

* clear CodeQL quality alerts ([e5fbe4e](https://github.com/AstorisTheBrave/argus/commit/e5fbe4e8122394175fb85c3fc365a321ae19ab66))


### Documentation

* **examples:** add basic and clustered bot examples ([b5bc3b2](https://github.com/AstorisTheBrave/argus/commit/b5bc3b2449db3c5dfb51a4d9e8ad7dc19e3f615d))
* write README and add MIT LICENSE (D11) ([5783c9f](https://github.com/AstorisTheBrave/argus/commit/5783c9f4638992ab7ee83a161e0bbf4ef7eda7b6))
