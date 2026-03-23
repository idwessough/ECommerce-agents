# Smoke Test Checklist

This guide is the fastest way to confirm that the scaffold boots correctly and that the first agent flow is reachable through both the ADK web UI and the ADK API server. If you prefer shorter commands, you can use `scripts/adk.ps1` on Windows or `scripts/adk.sh` on macOS and Linux.

## Prerequisites

Before starting, confirm the following:

- Docker Desktop is running
- a valid `.env` file exists at the project root for live analysis
- the `.env` file contains a valid `GOOGLE_API_KEY` before you send real analysis requests

The simplest starting point is to copy `.env.example` to `.env`, then replace the placeholder value with a real Gemini API key.

## 0. Optional preflight check

Before the first boot, validate the compose configuration:

```bash
docker compose config
```

This should render the full compose file. It works even if `.env` has not been created yet because the compose file provides safe defaults for local validation.

## 1. First web UI boot

Start the native ADK web UI:

```bash
docker compose --profile web up --build market-analysis-web
```

Open:

```text
http://localhost:8001
```

### What success looks like

You should be able to:

- open the ADK web interface in the browser
- select `ecommerce_agents`
- create a session
- send a message such as `Analyze Dyson V15`
- inspect state and event history

### If something goes wrong

- for code changes: `docker compose restart market-analysis-web`
- for dependency changes: rerun with `--build`

## 2. First API boot

Start the ADK API server:

```bash
docker compose up --build market-analysis-agent
```

Base URL:

```text
http://localhost:8000
```

## 3. Create a session

Use the ADK session endpoint:

```bash
curl -X POST http://localhost:8000/apps/ecommerce_agents/users/u_123/sessions/s_123 \
  -H "Content-Type: application/json" \
  -d @examples/api/create-session-state.json
```

### What success looks like

You should receive a JSON session object containing:

- `id`
- `appName`
- `userId`
- `state`

## 4. Send the first analysis request

Run the analysis request:

```bash
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d @examples/api/run-analysis.json
```

### What success looks like

You should receive a JSON array of events.

The event stream should show:

1. the user message
2. agent activity and tool usage
3. a final synthesized response

## 5. Run the test container

Run the provider and tool tests inside Docker:

```bash
docker compose --profile test run --rm market-analysis-test
```

### What success looks like

Pytest should complete with passing tests for:

- mock providers
- tool wrappers
- README presence

## 6. Recommended first debugging order

If the smoke test fails, debug in this order:

1. `.env` is present and the API key is valid
2. Docker Desktop is running
3. the web UI service boots
4. the API service boots
5. the tests pass
6. the first `/run` request returns events

## 7. Fast daily workflow

Use this sequence during development:

1. `market-analysis-web` for live iteration
2. `market-analysis-agent` for API validation
3. `market-analysis-test` for quick verification
4. rebuild only when dependencies change

