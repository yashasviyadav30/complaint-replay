# Security

Complaint Replay handles user complaints, repository tokens and pull requests, so we take reports seriously.

## Reporting a vulnerability

Please report it privately through GitHub: **Security > Report a vulnerability** on this repository. Do not open a
public issue. Include the steps to reproduce and what an attacker could do. You will get a reply within a week.

## What the design already does

- Fixes land only on a new branch and a pull request, and only on the repository's own `origin`. Nothing is merged
  automatically.
- The fixer may not edit tests, CI files, build configuration or secret files; a patch that tries is rejected.
- The app under test runs without your repository secrets.
- Action callbacks to the server are signed per case and expire; a reporter can read only their own case's status.
- Emails, phone numbers, card and account numbers, PAN and Aadhaar are masked before storage and before any model
  sees them. The widget never sends what users type into your forms.
- Projects can restrict which sites may send complaints and set how long complaints are kept.

## Supported versions

Only the latest commit on `main` receives fixes while the project is in alpha.
