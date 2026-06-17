# Changelog

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
