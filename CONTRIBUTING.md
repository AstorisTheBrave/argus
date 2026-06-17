# Contributing to Argus

Thanks for your interest in improving Argus. This project is small and welcomes
focused pull requests.

## Ground rules

- Keep the seven architectural invariants intact (see the README and the
  module docstrings). In particular: `core` imports no adapter, and no
  `guild_id`/`user_id`/`channel_id` ever becomes a Prometheus label.
- Run the checks before opening a PR:

  ```bash
  ruff check .
  ruff format --check .
  mypy
  pytest --cov=argus
  ```

- Add or update tests for any behaviour change. Core coverage should stay at or
  above 90%.

## Licensing and the DCO

Argus is licensed under **AGPL-3.0-or-later**. By contributing, you agree that
your contributions are licensed under the same terms, and you certify the
[Developer Certificate of Origin](https://developercertificate.org/) (reproduced
below).

Sign off every commit with the `-s` flag, which appends a
`Signed-off-by: Your Name <your@email>` trailer:

```bash
git commit -s -m "feat: describe your change"
```

The sign-off must use a real name and a reachable email. PRs whose commits are
not signed off will be asked to amend.

> **Why the DCO?** It records that you have the right to submit the code under
> the project licence. It also keeps the door open to offering a commercial
> dual-licensing exception in the future without having to track down every
> past contributor. (This is project policy, not legal advice.)

### Developer Certificate of Origin 1.1

```
By making a contribution to this project, I certify that:

(a) The contribution was created in whole or in part by me and I
    have the right to submit it under the open source license
    indicated in the file; or

(b) The contribution is based upon previous work that, to the best
    of my knowledge, is covered under an appropriate open source
    license and I have the right under that license to submit that
    work with modifications, whether created in whole or in part
    by me, under the same open source license (unless I am
    permitted to submit under a different license), as indicated
    in the file; or

(c) The contribution was provided directly to me by some other
    person who certified (a), (b) or (c) and I have not modified
    it.

(d) I understand and agree that this project and the contribution
    are public and that a record of the contribution (including all
    personal information I submit with it, including my sign-off) is
    maintained indefinitely and may be redistributed consistent with
    this project or the open source license(s) involved.
```
