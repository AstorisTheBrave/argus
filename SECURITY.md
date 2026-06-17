# Security policy

## Supported versions

Argus is pre-1.0; only the latest released version receives security fixes.

## Reporting a vulnerability

Please report security issues privately. Do not open a public issue.

- Preferred: open a private advisory via GitHub
  (Security tab -> Report a vulnerability), or
- Email: callmeSage0@proton.me

You will get an acknowledgement within a few days. Once a fix is available it
will be released and the advisory published with credit, if you want it.

## Notes

- The metrics endpoint and the built-in dashboard expose operational data to
  anyone who can reach the port. Set `dashboard_auth_token` and bind to
  localhost or sit behind a reverse proxy for anything public. The per-guild
  analytics path fails closed without a token.
