# Backup and Restore

Use this before any hosted promotion that can affect the primary Postgres database, especially schema migrations.

## Before promotion

1. Identify the target database and environment.
2. Confirm the current application commit and the migration head expected by that release.
3. Take one of the following before deploy:
   - managed-provider snapshot
   - logical dump with `pg_dump`
4. Record where the backup lives and who can restore it.
5. Link that backup reference in the promotion PR or release handoff.

## Minimum backup standard

- backup taken after the final integration candidate is chosen
- backup timestamp recorded
- backup maps to the exact database being promoted
- restore path tested or at least documented for that provider

## Example logical backup

```bash
pg_dump "$DATABASE_URL" --format=custom --file traders-cockpit-predeploy.dump
```

Store the resulting dump in your approved backup location. Do not commit it to the repo.

## Example restore

Restore only into a controlled recovery target, not over a live production database without an incident decision.

```bash
pg_restore --clean --if-exists --no-owner --dbname "$RECOVERY_DATABASE_URL" traders-cockpit-predeploy.dump
```

## Provider snapshots

If your host supports managed Postgres snapshots, a provider snapshot is acceptable instead of `pg_dump` as long as:

- the snapshot timestamp is recorded
- the snapshot is tied to the exact target database instance
- the restore path is documented for the operator on call

## After restore

1. Run the health endpoints:
   - `/health/live`
   - `/health/ready`
   - `/health/deps`
2. Run post-deploy or recovery smoke before reopening operator access.
3. Record the restore event in `docs/handoffs/` or the incident follow-up.
