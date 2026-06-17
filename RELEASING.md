# Releasing

Releases are driven by [release-please](https://github.com/googleapis/release-please)
from [Conventional Commits](https://www.conventionalcommits.org/), and published
to PyPI via [Trusted Publishing](https://docs.pypi.org/trusted-publishers/) (OIDC,
no stored token).

## Normal flow

1. Land changes on `main` with conventional commit messages (`feat:`, `fix:`,
   `feat!:`/`BREAKING CHANGE:` for majors). release-please opens and maintains a
   "release" PR that bumps the version in `src/argus/__init__.py` + the manifest
   and updates `CHANGELOG.md`.
2. Merge the release PR. (Branch protection requires status checks; a
   release-please PR carries none because it is authored by `GITHUB_TOKEN`, so
   merge it with admin: `gh pr merge <n> --squash --admin`.)
3. release-please then creates the tag and GitHub Release, and **the same
   workflow run builds the wheel/sdist and publishes to PyPI** (the `publish`
   job, gated on `release_created`). The build runs with Node so the dashboard
   SPA is bundled into the wheel.
4. `pip install argus-dpy` serves the new version once PyPI indexes it.

## Manual fallback

If a publish run fails (e.g. a transient PyPI error), re-run it:

- Actions -> **publish** -> Run workflow, optionally passing a tag like `v0.2.0`.

It is idempotent (`skip-existing: true`), so re-running will not error on files
that already uploaded.

## Trusted publisher setup (important)

PyPI matches a trusted publisher on the **workflow filename**, so each workflow
that publishes needs its own entry. On pypi.org -> project `argus-dpy` ->
Settings -> Publishing, ensure both exist (owner `AstorisTheBrave`, repo
`argus`, environment `pypi`):

- `release-please.yml` — the automatic release path (**add this one**; the
  auto-publish job runs from here).
- `publish.yml` — the manual fallback (already configured).

The GitHub environment named `pypi` already exists.
