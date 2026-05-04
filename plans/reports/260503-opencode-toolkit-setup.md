# OpenCode Toolkit Setup Guide
**Date:** 2026-05-03
**Purpose:** Prepare strong toolchain for OpenCode before download

---

## 1. Quick Install

```bash
# Primary (Linux/macOS)
curl -fsSL https://opencode.ai/install | bash

# Windows (PowerShell)
iwr https://opencode.ai/install -OutFile install.ps1
.\install.ps1

# Verify
opencode --version
```

---

## 2. Config File Structure

**Location:** `~/.opencode.json` (global) or `./.opencode.json` (project)

```json
{
  "provider": "local",
  "providers": {
    "minimax": {
      "name": "MiniMax M2.7",
      "apiKey": "sk-cp-xxx",
      "endpoint": "https://api.minimax.chat/v1",
      "model": "M2.7"
    }
  },
  "agents": {
    "coder": {
      "model": "minimax",
      "maxTokens": 8192,
      "temperature": 0.7
    }
  },
  "shell": {
    "path": "/bin/bash"
  },
  "mcpServers": {}
}
```

---

## 3. Recommended MCP Servers

```json
{
  "mcpServers": {
    "filesystem": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "."]
    },
    "github": {
      "type": "stdio", 
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"]
    },
    "git": {
      "type": "stdio",
      "command": "uvx",
      "args": ["mcp-server-git", "--repository", "."]
    }
  }
}
```

**Install common MCP servers:**
```bash
npx -y @modelcontextprotocol/server-filesystem .
npx -y @modelcontextprotocol/server-github
uvx mcp-server-git --repository .
uvx mcp-server-bash
```

---

## 4. Custom Commands Setup

**Location:** `~/.opencode/commands/` (global) or `.opencode/commands/` (project)

### 4.1 Project-Level Commands

```markdown
# .opencode/commands/init-frontend.md
RUN npm create vite@latest $PROJECT_NAME -- --template react-ts
RUN cd $PROJECT_NAME && npm install
RUN npm install -D tailwindcss postcss autoprefixer
RUN npx tailwindcss init -p

# .opencode/commands/init-backend.md
RUN mkdir -p $PROJECT_NAME/src/{routes,middleware,models}
RUN cd $PROJECT_NAME && npm init -y
RUN npm install express cors helmet dotenv

# .opencode/commands/run-tests.md
RUN npm test -- --coverage --watchAll=false
RUN echo "Coverage report generated"
```

### 4.2 Full-Stack Commands

```markdown
# .opencode/commands/deploy-vercel.md
RUN vercel --prod
RUN echo "Deployment URL: $DEPLOY_URL"

# .opencode/commands/db-migrate.md
RUN prisma migrate dev --name $MIGRATION_NAME
RUN prisma generate

# .opencode/commands/docker-build.md
RUN docker build -t $IMAGE_NAME .
RUN docker run -p 3000:3000 $IMAGE_NAME
```

---

## 5. Custom Agents

**Location:** `~/.opencode/agents/` or `.opencode/agents/`

### 5.1 JSON Agent Definition

```json
// .opencode/agents/frontend-dev.json
{
  "name": "frontend-dev",
  "type": "task",
  "description": "Frontend development specialist - React, Vue, Tailwind",
  "instructions": "You are a frontend developer. Focus on:\n- Component structure\n- Responsive design\n- State management\n- Performance optimization",
  "tools": {
    "read": "allow",
    "edit": "allow",
    "glob": "allow",
    "grep": "allow",
    "bash": "allow",
    "task": "deny"
  }
}

// .opencode/agents/backend-dev.json
{
  "name": "backend-dev", 
  "type": "task",
  "description": "Backend development specialist - FastAPI, Node, Python",
  "instructions": "You are a backend developer. Focus on:\n- API design\n- Database schema\n- Authentication\n- Error handling",
  "tools": {
    "read": "allow",
    "edit": "allow", 
    "glob": "allow",
    "grep": "allow",
    "bash": "allow",
    "task": "deny"
  }
}

// .opencode/agents/reviewer.json
{
  "name": "reviewer",
  "type": "task", 
  "description": "Code reviewer - best practices, security, performance",
  "instructions": "You are a code reviewer. Check for:\n- Security vulnerabilities\n- Performance issues\n- Code smells\n- Test coverage",
  "tools": {
    "read": "allow",
    "edit": "deny",
    "glob": "allow",
    "grep": "allow",
    "bash": "ask",
    "task": "deny"
  }
}
```

### 5.2 Built-in Agents

| Agent | Purpose | Access |
|-------|---------|--------|
| `build` | Full development | Read/Edit/Bash all allowed |
| `plan` | Read-only exploration | Bash ask-permission |
| `@general` | Parallel multi-task | Full tools, no todo |

---

## 6. AGENTS.md for Full-Stack Projects

**Location:** Project root, auto-created via `/init`

```markdown
# Project Context

## Stack
- Frontend: React 18 + TypeScript + Vite
- Backend: FastAPI (Python) + Uvicorn
- Database: PostgreSQL + Prisma
- Styling: Tailwind CSS
- Deployment: Vercel (FE) + Railway (BE)

## Project Structure
```
/
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   └── utils/
│   └── package.json
├── backend/
│   ├── src/
│   │   ├── routes/
│   │   ├── models/
│   │   └── middleware/
│   └── main.py
└── README.md
```

## Commands
- Frontend: `cd frontend && npm run dev`
- Backend: `cd backend && uvicorn main:app --reload`
- DB: `prisma studio`

## Conventions
- Use TypeScript strict mode
- API responses: `{ data, error }` format
- CSS: Tailwind utility classes only
- Commit: conventional commits

## Permissions
- Backend port: 8000
- Frontend port: 3000
- Prisma studio: 5555
```

---

## 7. Recommended MCP Servers for Full-Stack

| MCP Server | Purpose | Install |
|-----------|---------|---------|
| `@modelcontextprotocol/server-filesystem` | File operations | `npx -y @modelcontextprotocol/server-filesystem .` |
| `@modelcontextprotocol/server-github` | GitHub integration | `npx -y @modelcontextprotocol/server-github` |
| `mcp-server-git` | Git operations | `uvx mcp-server-git --repository .` |
| `mcp-server-bash` | Shell commands | `uvx mcp-server-bash` |
| `@modelcontextprotocol/server-memory` | Persistent memory | `npx -y @modelcontextprotocol/server-memory` |

---

## 8. MiniMax M2.7 Config

```json
{
  "providers": {
    "minimax": {
      "name": "MiniMax M2.7",
      "apiKey": "sk-cp-your-key-here",
      "endpoint": "https://api.minimax.chat/v1",
      "model": "M2.7",
      "maxTokens": 8192,
      "temperature": 0.7
    }
  },
  "agents": {
    "coder": {
      "model": "minimax",
      "maxTokens": 8192,
      "temperature": 0.7
    }
  }
}
```

**Note:** OpenCode uses `local` provider type for OpenAI-compatible APIs. Set `endpoint` to MiniMax's base URL.

---

## 9. Workflow Comparison

| Task | Claude Code + mm-claude.sh | OpenCode |
|------|---------------------------|----------|
| Single file edit | ✅ | ✅ |
| Multi-file refactor | ✅ | ✅ |
| Code review | ✅ | ✅ (via reviewer agent) |
| Architecture planning | ✅ | ✅ (plan mode) |
| Parallel tasks | ✅ (multi-terminal) | ✅ (multi-session, native) |
| Autonomous loop | ✅ (ck:autoresearch) | ❌ |
| Sidecar LLM | ✅ (mm-claude.sh) | ❌ |
| Privacy-first | ❌ | ✅ |
| Open source | ❌ | ✅ |
| LSP support | ❌ | ✅ |

---

## 10. Toolchain Checklist

### Pre-Download (do now)
- [ ] Backup current Claude Code config
- [ ] Prepare MiniMax API key
- [ ] List MCP servers needed

### Post-Install (after download)
- [ ] `opencode --version`
- [ ] Configure `~/.opencode.json` with MiniMax
- [ ] Create `~/.opencode/commands/` directory
- [ ] Create `~/.opencode/agents/` directory
- [ ] Install MCP servers
- [ ] Test: `opencode --agent plan "Explain this codebase"`
- [ ] Test: Create custom command
- [ ] Test: Invoke custom agent

### Project Setup
- [ ] `opencode --init` in project
- [ ] Configure AGENTS.md
- [ ] Create project-level commands
- [ ] Test multi-session

---

## 11. MiniMax-Specific Considerations

| Aspect | Status | Notes |
|--------|--------|-------|
| API compatibility | ✅ | OpenAI-compatible endpoint works |
| Vision | ⚠️ | Model-dependent |
| Function calling | ⚠️ | Standard format, MiniMax may differ |
| Token efficiency | ❓ | No benchmark available |
| Rate limits | ❓ | Check MiniMax dashboard |

---

## 12. Recommended First Test

```bash
# 1. Install
curl -fsSL https://opencode.ai/install | bash

# 2. Configure MiniMax
cat > ~/.opencode.json << 'EOF'
{
  "providers": {
    "minimax": {
      "name": "MiniMax M2.7",
      "apiKey": "YOUR_KEY",
      "endpoint": "https://api.minimax.chat/v1"
    }
  },
  "agents": {
    "coder": { "model": "minimax" }
  }
}
EOF

# 3. Test basic
opencode --agent plan "What files are in this directory?"

# 4. Test custom command
mkdir -p ~/.opencode/commands
cat > ~/.opencode/commands/hello.md << 'EOF'
RUN echo "Hello from OpenCode!"
RUN echo "Current directory: $(pwd)"
EOF
# Invoke: /hello

# 5. Test full-stack task
mkdir ~/test-fullstack && cd $_
opencode --init
# Then ask: "Create a simple React + FastAPI app"
```

---

## 13. Known Issues & Workarounds

| Issue | Workaround |
|-------|------------|
| Fish shell issues | Set `"shell": { "path": "/bin/bash" }` |
| 4.5K open issues | Check recent issues before reporting |
| Connection failures | Check OpenCode status page |
| AGENTS.md 404 docs | Use GitHub README as reference |
| MiniMax not in provider list | Use `local` with custom endpoint |

---

## 14. Success Metrics

| Metric | Target |
|--------|--------|
| Install success | < 5 minutes |
| MiniMax config | Works on first try |
| Basic task completion | < 10 minutes |
| Custom command creation | < 5 minutes |
| Multi-session spawn | Works |
| Full-stack task | Benchmarked vs Claude Code |

---

## Sources
- [OpenCode GitHub](https://github.com/anomalyco/opencode)
- [OpenCode Config Schema](https://raw.githubusercontent.com/anomalyco/opencode/refs/heads/main/opencode-schema.json)
- [OpenCode Agents Docs](https://opencode.ai/docs/agents)
- [OpenCode Commands Docs](https://opencode.ai/docs/commands)
