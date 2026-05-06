# BLS AI — Functional Overview

> A business-friendly description of every feature available in the application.
> Technical details are intentionally kept light. Replace the
> `![screenshot](...)` placeholders with real screenshots before sharing.

---

## 1. Introduction

**BLS AI** (white‑label name configurable per customer) is an enterprise AI
assistant platform that lets organisations:

- Chat with AI agents that are grounded in their own internal knowledge.
- Curate and manage that knowledge in a structured, permissioned way.
- Configure the AI brain (LLM models, agents, prompts, variables, credentials).
- Manage users, roles, and fine‑grained page/feature access.

The whole product can be re‑branded for any customer (logo, name, colours,
favicon, page titles, social preview image) by changing a few environment
variables — no code change required.

![Login screen placeholder](./docs/screenshots/login.png)

---

## 2. Authentication & Branding

### 2.1 Sign‑in
- Secure email + password sign‑in.
- Branded login screen showing the customer logo, product name, and tagline.
- Session persists across page refreshes.

### 2.2 White‑label branding
The following are driven by environment variables and propagate everywhere
(top bar, login page, browser tab title, social share previews, footers):

| Setting | Purpose |
|---|---|
| Brand name | e.g. "BLS", "Acme" |
| Brand suffix | e.g. "AI" |
| Logo initial | The single letter shown in the logo tile |
| Company name | Legal name in footers |
| Tagline | Marketing line under the logo |
| Product title | Browser tab and social preview title |
| Description | Meta description for SEO and social sharing |
| OG image | Social share image |
| Favicon | Browser tab icon |

![Branded header placeholder](./docs/screenshots/branding.png)

---

## 3. Chat

The Chat module is the primary end‑user experience.

### 3.1 Conversations
- Start a new conversation or resume any previous one from the left sidebar.
- Each conversation is bound to one **AI Agent** (the persona/skill set).
- Conversations are auto‑titled from the first message and can be renamed or
  deleted.
- Search across past conversations.

### 3.2 Sending messages
- Multi‑line input with send‑on‑Enter (Shift+Enter for newline).
- Welcome screen greets the user by brand name when no conversation is open.
- Optional starter prompts to help users get going.

### 3.3 Streaming responses
Replies stream token‑by‑token in real time. While the AI is working, the user
sees:

- **Status notifications** (e.g. *"Searching knowledge base…"*, *"Thinking…"*)
  shown next to the loading indicator so users always know what is happening.
- **Live text** that appears as the model generates it.
- **Citations / Sources** automatically attached to the answer when the AI
  used internal documents to respond.

### 3.4 Source citations (RAG)
When the agent retrieves information from the knowledge base, the answer
includes a **Sources** panel showing:

- The source document name and link.
- The knowledge base it came from.
- A similarity / match percentage indicating how relevant the chunk was.
- Reference numbers (`#1`, `#2`, …) so users can map citations to the answer.

### 3.5 Switching agents
Users can change the active agent at any time; subsequent messages are
answered by the newly selected agent.

![Chat module placeholder](./docs/screenshots/chat.png)

---

## 4. Knowledge Base

The Knowledge Base (KB) is where business teams curate the content the AI is
allowed to read.

### 4.1 Knowledge Bases
- Create multiple knowledge bases (e.g. *HR Policies*, *Product Catalog*,
  *Compliance*).
- Each KB has a name, description, and access permissions.
- KBs can be searched, edited, and deleted.

### 4.2 Knowledge Items
Inside each KB, users can add **Knowledge Items** of different types:

- **Documents** — PDFs, Word docs, text files uploaded directly.
- **URLs / Web pages** — content fetched from a public link.
- **Plain text / notes** — typed‑in content.

For each item the user can set the title, description, source, and tags.

### 4.3 Embedding (making content searchable by AI)
Before the AI can use a document it must be **embedded** (converted into
vector representations). The UI offers:

- **Embed** — process a single new item.
- **Re‑Embed** — refresh embeddings for one item (e.g. after editing).
- **Re‑Embed All** — bulk refresh every item in a KB.
- A live status indicator shows whether items are *Pending*, *Embedding*,
  *Ready*, or *Failed*.

### 4.4 Item actions (inline)
Each row exposes the most important actions directly without extra clicks:

- **Access Control** — restrict which roles can use the item.
- **Re‑Embed** — refresh the embedding.
- **Delete** — remove the item.
- **Edit** — change metadata.

![Knowledge base placeholder](./docs/screenshots/knowledge-base.png)

---

## 5. Settings

The **Settings** area is the control room for administrators.

### 5.1 Agents
Agents are the AI personas users chat with.

For each agent you can configure:

- **Name, description, avatar**.
- **System prompt** — the instructions that shape the agent's tone, role,
  and behaviour.
- **LLM model** — which underlying AI model the agent uses.
- **Knowledge bases** the agent is allowed to read from.
- **Tools / API integrations** the agent may call.
- **Global variables** the agent can substitute into prompts.
- **Access Control** — which roles may chat with the agent (button shown
  directly on the card, next to **Edit**).

Admins can create, duplicate, edit, and delete agents.

![Agents page placeholder](./docs/screenshots/agents.png)

### 5.2 LLM Configuration
Manage the AI models available across the platform.

- Register multiple providers and models (OpenAI, Anthropic, Azure, Gemini,
  local, etc.).
- Configure provider keys, base URLs, model name, temperature, and max tokens.
- Mark models as active / inactive.
- Apply **Access Control** so only allowed roles can use a given model.

![LLM configuration placeholder](./docs/screenshots/llm.png)

### 5.3 API Configuration
Define external APIs that agents can call as tools (e.g. ticketing system,
inventory lookup, CRM).

For each API endpoint you can set:

- Name, description, base URL, HTTP method.
- Path, query and header parameters with default values.
- Request body schema.
- Linked **API Credential** (see below) for authentication.
- Test runner to verify the endpoint works.
- Access Control per API.

![API configuration placeholder](./docs/screenshots/api-config.png)

### 5.4 API Credentials
Centralised, reusable credentials for those external APIs.

- Authorization types supported: **Basic**, **Bearer Token**, **OAuth /
  custom token endpoint**, **Custom Headers**.
- For token endpoints: configure the auth URL, HTTP method, JSON payload
  template (with variable substitution like `{{SYS_USER_EMAIL}}`), and the
  JSON path to extract the token from the response.
- Add custom headers to be sent with every request.
- Credentials are stored securely and shared between API definitions.
- Access Control per credential.

![API credentials placeholder](./docs/screenshots/api-credentials.png)

### 5.5 Global Variables
Reusable values available across prompts, API calls and tools.

- **Types**: text, integer, select (dropdown), secret (masked).
- Variables can be referenced anywhere with `{{VARIABLE_NAME}}` syntax.
- Useful for values like company name, support email, default region,
  fallback URLs.
- Access Control per variable.

![Global variables placeholder](./docs/screenshots/variables.png)

---

## 6. User Management

### 6.1 Users
- View all users with name, email, assigned roles, and status (active /
  inactive).
- Search across name and email.
- **Add User** — create a new user; the system shows a generated temporary
  password that can be copied to share with the user.
- **Edit User** — change display name and assigned roles.
- **Access Control** — apply per‑user overrides.
- **Delete User** — with self‑deletion protection (you cannot delete
  yourself).

![Users page placeholder](./docs/screenshots/users.png)

### 6.2 Roles
- Create roles such as *Administrator*, *Knowledge Curator*, *Sales*,
  *Read‑Only*.
- Each role has a name and description.
- Roles are assigned to users and used everywhere Access Control is offered.

![Roles page placeholder](./docs/screenshots/roles.png)

### 6.3 Pages & Permissions
- Lists every page/module in the application.
- For each page, set whether it requires authentication and which roles may
  view it.
- Search by module, name, or description to quickly find a page.

![Pages permissions placeholder](./docs/screenshots/pages.png)

---

## 7. Access Control (cross‑cutting)

Access Control is a shared component that appears on every resource that
supports permissions: **Knowledge Items, Agents, LLM models, APIs, API
Credentials, Global Variables, Users, Pages.**

It always offers the same simple model:

- **Public** — anyone authenticated can use the resource.
- **Restricted** — only selected **Roles** and/or **Users** can use it.
- A search box helps quickly find roles/users in larger organisations.
- Selections are shown as removable chips for clarity.

This consistency means once a business user learns Access Control on one
screen, they know how to use it everywhere.

![Access control dialog placeholder](./docs/screenshots/access-control.png)

---

## 8. Navigation & Shell

- **Top bar** — brand logo, product name, current page title, signed‑in
  user menu (profile, sign out).
- **Left sidebar** — primary navigation grouped into *Chat*, *Knowledge
  Base*, *Settings*, *User Management*. Collapsible on smaller screens.
- **Sub‑navigation** — secondary tabs inside Settings and User Management
  for quick switching between related pages.
- **Route progress bar** — thin bar at the top of the screen during page
  transitions for instant feedback.
- **Breadcrumb / page title** — every page has a clear title and short
  description so users always know where they are.

![App shell placeholder](./docs/screenshots/app-shell.png)

---

## 9. Notifications & Feedback

- **Toasts** appear in the top‑right for successes, warnings, and errors
  (e.g. "Item embedded", "Failed to save credential").
- **Confirmation dialogs** appear before destructive actions (delete user,
  delete KB item, delete role).
- **Inline validation** in forms highlights missing or invalid fields with
  helpful messages.

---

## 10. Security & Privacy

- All sessions are authenticated; unauthenticated users are sent to the
  login page.
- Roles are stored in a dedicated, server‑validated table — they cannot be
  manipulated from the browser.
- Secrets (API keys, passwords, secret variables) are stored masked and
  never displayed in plain text once saved.
- Every protected resource is gated by the Access Control model described
  in section 7.

---

## 11. Customisation Summary

To roll the product out for a new customer, only the following needs to
change — no code edits:

1. Brand environment variables (name, logo letter, company, tagline,
   favicon, social image, page title).
2. Initial admin user.
3. Optional: pre‑seeded knowledge bases, agents, and global variables.

Everything else (UI flows, permissions model, settings) is identical
across customers, which keeps support, training, and documentation simple.

---

## 12. Roadmap Placeholders

> Use this section to capture upcoming functional improvements as they are
> agreed with the business.

- [ ] Conversation export (PDF / DOCX)
- [ ] Per‑agent analytics dashboard
- [ ] Scheduled re‑embedding of knowledge items
- [ ] SSO / SAML authentication
- [ ] Multi‑language UI

---

*Document owner: Product Team — last updated: 2026‑05‑06.*
