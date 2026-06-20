<!-- Conventional Commit title, e.g. "feat(adapters): add Datadog adapter". -->

## What

<!-- What this change does and why. -->

## Checklist

- [ ] Commits use Conventional Commits and are signed off (`git commit -s`, DCO).
- [ ] `ruff check .`, `ruff format --check .`, `mypy`, and `pytest` pass.
- [ ] Frontend (if touched): `npm run build` and `npm test` pass.
- [ ] No `guild_id`/`user_id`/`channel_id` added as a Prometheus label (invariant 2).
- [ ] Tests added/updated for the change.
