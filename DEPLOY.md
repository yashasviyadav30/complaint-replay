# Hosting Complaint Replay

The hosted service takes complaints and starts replays in each team's GitHub Actions. It runs no browser, so a
small free instance is enough.

## Render (free)

1. On render.com: New > Blueprint > this repo. It reads `render.yaml` and builds `Dockerfile.server`.
2. Fill `PUBLIC_URL` (the service's https address), `ADMIN_LOGIN` (your GitHub username), `NEBIUS_API_KEY`, and
   `DATABASE_URL` from a free Postgres (Neon or Supabase). The image already includes the Postgres driver.
3. Open `PUBLIC_URL/setup/github-app`: GitHub creates the App from a manifest in one click. On a host that
   restarts from scratch, copy the saved values into `GITHUB_APP_ID`, `GITHUB_APP_SLUG`, `GITHUB_APP_PRIVATE_KEY`,
   `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET`, then redeploy.
4. Sign in on the dashboard, create a project, and follow its Set Up page.

Free instances sleep after 15 minutes without traffic; the first request after that takes about a minute.

## Any machine with Docker

`docker compose up` runs everything on one machine, including the built-in demo shop with a browser.
Keep it bound to 127.0.0.1, or put it behind HTTPS with GitHub login turned on.
