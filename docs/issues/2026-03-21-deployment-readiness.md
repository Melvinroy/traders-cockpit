# Deployment Readiness

## Goal
Prepare `traders-cockpit` for a real hosted staging/preview setup instead of local-only runtime.

## Scope
- Add production-oriented Dockerfiles for frontend and backend.
- Add a Render blueprint for backend, Postgres, and Redis.
- Add a hosted environment validation script.
- Document the recommended hosted topology and environment requirements.

## Acceptance
- A contributor can understand how to host:
  - frontend on Vercel
  - backend on Render or another container host
  - Postgres and Redis as managed services
- Docker builds exist for frontend and backend.
- Hosted env variables are documented and can be validated locally before deployment.
