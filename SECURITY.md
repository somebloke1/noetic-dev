# Security policy

## Secrets

- Never commit credentials, tokens, passwords, generated bearer values, private keys, or secret-bearing environment files.
- Refer to secrets by environment-variable name only.
- Never print, log, persist, upload, or include secret values in tool output, issues, PRs, fixtures, or CI artifacts.
- If a secret is exposed, stop dependent work, revoke/rotate it, and report the exposure privately.

## Non-interactive sudo

When elevated access is genuinely necessary:

1. Check whether `USER_SUPPLIED_PASSWORD` is present without displaying it.
2. If present, supply it only through non-interactive standard input to the narrowest required `sudo` command; suppress password prompts and never trace the command.
3. If absent or rejected, record the concrete blocker.
4. Never ask the user for the password, open a GUI authentication dialog, or start an interactive password prompt.

Prefer unprivileged alternatives and repository-local environments. Sudo is not a convenience mechanism.

## Reporting

For this private bootstrap repository, report vulnerabilities privately to the repository owner. Do not create a public issue containing exploitable details or secrets.
