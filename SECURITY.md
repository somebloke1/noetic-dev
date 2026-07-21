# Security policy

## Secrets

- Never commit credentials, tokens, passwords, generated bearer values, private keys, or secret-bearing environment files.
- Refer to secrets by environment-variable name only.
- Never print, log, persist, upload, or include secret values in tool output, issues, PRs, fixtures, or CI artifacts.
- If a secret is exposed, stop dependent work, revoke/rotate it, and report the exposure privately.

## Reporting

For this private bootstrap repository, report vulnerabilities privately to the repository owner. Do not create a public issue containing exploitable details or secrets.
