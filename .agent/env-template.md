# .env Files Required — Nelson Freight
# DO NOT put actual values here. This is a TEMPLATE.
# Actual .env files are NEVER committed to Git.

## TelegramBot/.env
```
BOT_TOKEN=<telegram bot token>
GEMINI_API_KEY=<google gemini key>
ADMIN_CHAT_ID=<nelson telegram chat id>
NELSON_CHAT_ID=<same as above>
```

## webapp/.env.local
```
AUTH_SECRET=<64 char random string>
USERS=nelson:<password>:admin
API_URL=http://localhost:8100
```

## Sync checklist
- [ ] All .env present on PC Home
- [ ] All .env present on Laptop VP
- [ ] All .env present on VPS
- [ ] .gitignore blocks all .env files
