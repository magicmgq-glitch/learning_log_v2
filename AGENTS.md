# AGENTS.md

## Project
This is a Django project that is currently running in production.
The code was developed earlier with AI assistance, and the current maintainer is re-learning the project.
Goal: understand the existing codebase first, then gradually separate frontend and backend.

## Working Rules
- Read and explain before editing.
- Do not make large refactors in one step.
- Prefer small, reversible changes.
- Keep the current Django site working unless explicitly asked otherwise.
- When adding APIs, add new endpoints first before replacing template-based views.
- Explain affected files before making changes.
- After each code change, provide verification steps.

## Priorities
1. Re-understand the project structure
2. Identify existing APIs and template-rendered pages
3. Find low-risk features to convert into APIs
4. Preserve production behavior
5. Prepare for future iOS and Android clients
