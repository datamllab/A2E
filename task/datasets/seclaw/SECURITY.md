# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in SeClaw, please report it responsibly.

**Do not open a public GitHub issue for security vulnerabilities.**

Contact the project maintainers privately using the security contact listed by the repository owner, and include:

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix, if available

## Scope

This policy covers:

- The benchmark framework code (`benchmark/` and `scripts/`)
- Task fixture code (`tasks/`)
- Configuration handling and secret management

## Safety Notice

This project contains adversarial prompts, prompt-injection payloads, and simulated attack scenarios for security evaluation purposes. These are intentional and expected. Please do not report the presence of adversarial content in task definitions as a vulnerability.
