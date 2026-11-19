# Security policy

## Supported versions

Only the latest release gets security fixes.

## Reporting a vulnerability

Please don't open a public issue. Use GitHub's private reporting instead: **Security → Report a vulnerability** on the repository page. You'll get a reply within a week. Once a fix is released, the advisory is published with credit to you unless you'd rather stay anonymous.

## Scope

:py runs the code you type with your user's permissions, so running untrusted code in it is not a vulnerability in itself. Things that are in scope include:

- :py executing code you didn't ask it to run (for example from a file it reads at startup that isn't yours, or from the history database)
- the installer (`install.sh`) installing something other than the verified release
- secrets from your session ending up somewhere unexpected (logs, crash reports, history files with wrong permissions)
