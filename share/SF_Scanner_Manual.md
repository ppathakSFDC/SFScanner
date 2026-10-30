# SF Scanner — User Manual

**Version 1.0 | October 2026**

---

## What is SF Scanner?

SF Scanner is an AI-powered Salesforce org analysis and management tool. It connects to your Salesforce org and provides:

- Security and compliance scanning
- Org health reports
- AI agents for CRM queries and Revenue Cloud product creation
- GDPR data management
- Org-to-org comparison and migration assistance

The app runs entirely on your local machine — no data is sent to any third-party server other than Salesforce and the AI provider you configure.

---

## What's in this folder?

```
sfscanner       — the application (self-contained, no installation needed)
env.example     — configuration template
SF_Scanner_Manual.md  — this file
```

---

## Step 1 — Prerequisites

| Requirement | Details |
|---|---|
| **macOS** | 11 Big Sur or later (Apple Silicon or Intel) |
| **Salesforce org** | Any org with API access enabled |
| **Salesforce Connected App** | See Step 2 below |
| **AI API key** | Anthropic (claude) — see Step 3 below |

> **Windows / Linux**: The executable in this folder is macOS-only.
> Ask your administrator for the Windows or Linux build.

---

## Step 2 — Create a Salesforce Connected App

You need a Connected App in your Salesforce org to allow SF Scanner to authenticate.

1. In Salesforce, go to **Setup → App Manager → New Connected App**
2. Fill in:
   - **Connected App Name**: SF Scanner
   - **API Name**: SF_Scanner
   - **Contact Email**: your email
3. Under **API (Enable OAuth Settings)**:
   - Check **Enable OAuth Settings**
   - **Callback URL**: `http://localhost:8080/auth/callback`
   - **Selected OAuth Scopes**: add these two:
     - `Access and manage your data (api)`
     - `Perform requests on your behalf at any time (refresh_token, offline_access)`
4. Click **Save** — wait 2–10 minutes for it to activate
5. From the Connected App detail page, copy:
   - **Consumer Key** → this is your `SF_CLIENT_ID`
   - **Consumer Secret** → this is your `SF_CLIENT_SECRET`

---

## Step 3 — Get an Anthropic API Key

1. Go to **console.anthropic.com**
2. Sign in or create a free account
3. Go to **API Keys → Create Key**
4. Copy the key (starts with `sk-ant-...`) → this is your `ANTHROPIC_API_KEY`

> A free-tier account includes enough credits to get started.

---

## Step 4 — Configure the app

1. Open the `env.example` file in any text editor (TextEdit, VS Code, etc.)
2. Fill in your values:

```
SF_CLIENT_ID=your_consumer_key_from_step_2
SF_CLIENT_SECRET=your_consumer_secret_from_step_2
SF_REDIRECT_URI=http://localhost:8080/auth/callback
SF_LOGIN_URL=https://login.salesforce.com

ANTHROPIC_API_KEY=sk-ant-your_key_from_step_3

SESSION_SECRET=any-long-random-string-you-make-up
```

3. Save the file as **`.env`** (with a dot at the start, no `.example`) in the **same folder** as the `sfscanner` executable.

> **Sandbox orgs**: change `SF_LOGIN_URL` to `https://test.salesforce.com`

---

## Step 5 — Run the app

1. Open **Terminal** (press `Cmd + Space`, type `Terminal`, press Enter)
2. Navigate to the folder containing the `sfscanner` file:
   ```bash
   cd ~/Downloads/share
   ```
   *(adjust the path to wherever you saved the folder)*

3. On first run, remove the macOS security restriction:
   ```bash
   xattr -d com.apple.quarantine sfscanner
   ```

4. Start the app:
   ```bash
   ./sfscanner
   ```

5. Open your browser and go to:
   ```
   http://localhost:8080
   ```

6. To stop the app, press **Ctrl + C** in Terminal.

---

## Features Guide

### Home
The landing page shows your connected org's health summary — object counts, recent activity, and quick-access cards to each feature.

---

### Settings (bottom of sidebar)
Connect your Salesforce org here first before using any other feature.
- Click **Connect Org**
- Log in with your Salesforce credentials
- Authorize the Connected App
- You'll be redirected back automatically with a green "Org Connected" indicator

---

### Scanner
Scans your org's Apex code for issues:
- Security vulnerabilities (SOQL injection, FLS bypass, hardcoded IDs)
- Code quality problems
- Performance anti-patterns

**How to use**: Click **Run Scan**, wait for results, then click any finding to see details and a suggested fix.

---

### Org Scan
A full org health check covering:
- Object and field counts
- Apex class and trigger inventory
- Installed packages
- API usage

Results can be exported to CSV.

---

### Migrate
Assists with moving metadata or data between two orgs.
- Connect a source org and a target org
- Select what to migrate
- Preview changes before applying

---

### Info
Displays detailed metadata about your connected org:
- Objects and their field lists
- Record counts
- Relationships between objects

Click any object name to drill into its fields.

---

### Security
Runs a GDPR / SOC2 / HIPAA compliance checklist against your org:
- Permission set analysis
- Profile risk assessment
- Encryption and audit trail checks
- Findings table with severity ratings (Critical / High / Medium / Low)

Export findings to CSV for audit documentation.

---

### Compliance (GDPR)
An AI-powered GDPR compliance agent:
- Find contacts with no activity for X years (right to erasure candidates)
- Export all data for a specific contact (Subject Access Request)
- Detect PII fields across objects
- Anonymise or delete records after confirmation

---

### Professor
An AI assistant specialising in Salesforce architecture and Apex code:
- Ask questions about your org's code
- Get best-practice recommendations
- Explain complex Salesforce concepts

> The Professor answers questions about code and architecture. For live CRM record queries, use the CRM Agent instead.

---

### CRM Agent
A live AI agent with direct access to your Salesforce data:
- **"Show me my 5 most recent open Cases"**
- **"Find all Accounts in New York with no Activity in 90 days"**
- **"What Contacts are linked to Acme Corp?"**

The agent runs SOQL queries against your org in real time and presents the results conversationally.

---

### RC Builder (Revenue Cloud Product Builder)
An AI agent for creating Revenue Cloud / Product Catalog Management records:
- **"Create a Home Insurance product with coverages for Building, Outbuilding and Contents"**
- **"Set up a ProductSellingModel for monthly subscription"**
- **"Create a ProductClassification for Property products"**

The agent understands the PCM dependency order (Attributes → Classification → Catalog → Selling Models → Product → Bundle → Pricing) and creates records in the correct sequence.

---

### Compare Orgs
Side-by-side comparison of two Salesforce orgs:
- Spot missing objects, fields, or Apex classes
- Identify configuration drift between sandbox and production

---

## Model Selector

Each AI agent page shows a **model dropdown** in the top-right of the chat header. You can switch between:

| Model | Best for |
|---|---|
| Opus 4.5 — Most capable | Complex Revenue Cloud builds, multi-step reasoning |
| Sonnet 4.5 — Balanced | General use, CRM queries, code questions |
| Haiku 4.5 — Fast | Quick lookups, simple questions |

Your selection is saved automatically and persists between sessions.

---

## Troubleshooting

| Problem | Solution |
|---|---|
| "cannot be opened because the developer cannot be verified" | Run: `xattr -d com.apple.quarantine sfscanner` in Terminal |
| App starts but browser shows nothing | Make sure you're opening `http://localhost:8080` (not https) |
| "No AI provider configured" | Check your `.env` file has `ANTHROPIC_API_KEY` set correctly |
| "Not authenticated" in an agent | Go to **Settings** and reconnect your org |
| Blank screen after login | Clear browser cache and reload |
| Port 8080 already in use | Add `PORT=8081` to your `.env` file and open `http://localhost:8081` |
| Sandbox org not connecting | Set `SF_LOGIN_URL=https://test.salesforce.com` in `.env` |

---

## Security & Privacy

- Your Salesforce credentials are **never stored** — only the OAuth session token is kept in memory while the app is running
- Your `.env` file stays on your machine — never share it or commit it to version control
- All AI queries go directly from your machine to the Anthropic API — no intermediary server
- The app has no telemetry or analytics

---

## Stopping and restarting

To stop: press **Ctrl + C** in the Terminal window running `sfscanner`

To restart: run `./sfscanner` again — no reboot or reinstall needed

---

*SF Scanner — Built for Salesforce professionals*
