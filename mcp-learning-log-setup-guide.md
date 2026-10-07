# MCP Learning Log — Full Setup Guide

A complete walkthrough for setting up, running, and connecting the `learning-log` MCP server (https://github.com/shreyap2702/learning-log) to Claude Desktop on Windows.

---

## 1. Prerequisites

Install `uv` (Python package/dependency manager):

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Verify it installed correctly:

```powershell
Get-Command uv
```

If not found on PATH, locate it directly:

```powershell
Test-Path "$env:USERPROFILE\.local\bin\uv.exe"
```

---

## 2. Clone the repo

```powershell
git clone https://github.com/shreyap2702/learning-log.git
cd learning-log
uv sync
```

---

## 3. Branch structure

The project is built incrementally across branches — each one adds a new piece:

| Branch | Adds |
|---|---|
| `step-0-setup` | project scaffold, no server code yet |
| `step-1-first-tool` | `add_learning` tool |
| `step-2-second-tool` | `search_learnings` tool |
| `step-3-resource` | `learnings://all` resource |
| `step-4-prompt` | `summarize_week` prompt |
| `step-5-claude-desktop` | Claude Desktop connection config |
| `step-6-github-push` | `push_to_github` tool |

Switch branches with:

```powershell
git checkout <branch-name>
uv sync
```

**Note:** you can `git pull` or `git checkout` from any PowerShell window without stopping a running server — but the server won't pick up new code until it's restarted (or Claude Desktop is fully quit and reopened).

---

## 4. Testing each branch locally (MCP Inspector)

Run this after checking out any branch to test it standalone before wiring it to Claude Desktop:

```powershell
uv run mcp dev server.py
```

This opens the **MCP Inspector** in your browser. Use it to:
- **Tools tab** → run `add_learning`, `search_learnings`, `push_to_github`
- **Resources tab** → view `learnings://all`
- **Prompts tab** → run `summarize_week`

---

## 5. Connecting to Claude Desktop (from step-5 onward)

### 5a. Find your project's absolute path

```powershell
(Get-Location).Path
```

### 5b. Find your uv.exe path

```powershell
Get-Command uv
```
or
```powershell
Test-Path "$env:USERPROFILE\.local\bin\uv.exe"
```

### 5c. Open Claude Desktop's config file

```powershell
notepad "$env:APPDATA\Claude\claude_desktop_config.json"
```

### 5d. Config code (`mcpServers` block)

Replace the `mcpServers` section with:

```json
"mcpServers": {
  "MCP-SERVER": {
    "command": "C:\\Users\\<your-username>\\.local\\bin\\uv.exe",
    "args": [
      "--directory",
      "D:\\learning-log",
      "run",
      "server.py"
    ]
  }
},
```

- Use **double backslashes** (`\\`) in all Windows paths inside JSON.
- `"command"` should be the full path to `uv.exe` (a bare `"uv"` often fails because Claude Desktop doesn't launch with your shell's PATH).
- `"--directory"` should point to wherever you cloned the repo (adjust the drive/path to match your machine).
- The key `"MCP-SERVER"` is just a display name — it can be anything, but avoid spaces (use `-` or `_`).

### 5e. Restart Claude Desktop

1. Right-click the Claude icon in the **system tray** → **Quit** (closing the window alone is not enough)
2. Reopen Claude Desktop
3. Click the 🔌 icon in the chat input → confirm **MCP-SERVER** is listed with its tools

---

## 6. Step 6 — GitHub push setup

### 6a. Checkout the branch

```powershell
git checkout step-6-github-push
uv sync
```

### 6b. Create a GitHub Personal Access Token

1. GitHub → profile photo → **Settings**
2. **Developer settings** → **Personal access tokens** → **Tokens (classic)**
3. **Generate new token (classic)**
4. Name it (e.g. `learning-log-mcp`), set an expiration
5. Check the **`repo`** scope
6. Generate and copy the token immediately (shown only once)

### 6c. Create your `.env` file

```powershell
copy .env.example .env
notepad .env
```

`.env` structure:

```dotenv
GITHUB_TOKEN=your_token_here
GITHUB_REPO=yourusername/yourrepo
```

- `.env.example` is the committed **template** — never put real secrets in it.
- `.env` is your **real, local-only file** — excluded by `.gitignore`, holds your actual token.
- `GITHUB_REPO` uses the format `owner/repo-name` (not a full URL).

### 6d. Test in Inspector before Claude Desktop

```powershell
uv run mcp dev server.py
```

Tools tab → run `push_to_github` → check for a success message → verify the file actually appeared on GitHub.

### 6e. Test live in Claude Desktop

Restart Claude Desktop (quit via system tray, reopen), then in a chat:

```
Use push_to_github to push my learnings to GitHub.
```

Confirm the tool call succeeds and check your GitHub repo to see the updated `learnings.md`.

---

## 7. Useful test prompts (Claude Desktop)

**Log a learning:**
```
Use add_learning to log that I learned how MCP servers connect tools, resources, and prompts to Claude Desktop.
```

**Log casually:**
```
Log this: I learned that .env files hold real secrets while .env.example is just a template.
```

**Search:**
```
Use search_learnings to find anything I've logged about MCP.
```

**Read the resource:**
```
Show me everything in learnings://all
```

**Run the summary prompt:**
```
Use the summarize_week prompt to summarize what I've learned this week.
```

**Chain logging + pushing:**
```
Log that I learned how to test an MCP tool safely in Inspector before wiring it to Claude Desktop, then push my learnings to GitHub.
```

---

## 8. Troubleshooting checklist

- **No 🔌 icon / MCP-SERVER missing:** check `%APPDATA%\Claude\logs\mcp*.log` for errors.
- **uv command fails silently:** use the full path to `uv.exe`, not just `"uv"`.
- **Wrong branch:** run `git branch` — the branch with `*` is active. Steps are cumulative, so `step-6-github-push` includes everything from steps 1–5.
- **push_to_github fails (404):** the repo name in `GITHUB_REPO` doesn't exist on GitHub yet — create it first.
- **push_to_github fails (401/403):** token is invalid, expired, or missing the `repo` scope — regenerate it.
- **Security:** if your token is ever pasted somewhere it could be exposed (chat, screenshot, public repo), regenerate it immediately via GitHub → Settings → Developer settings → Personal access tokens.

---

## 9. Full pipeline summary

```
git checkout step-6-github-push
   → uv sync
   → uv run mcp dev server.py   (test in Inspector)
   → configure Claude Desktop's claude_desktop_config.json
   → quit + reopen Claude Desktop
   → confirm MCP-SERVER connected via 🔌 icon
   → test add_learning / search_learnings / learnings://all / summarize_week / push_to_github
   → verify pushed file on GitHub
```
