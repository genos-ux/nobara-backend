# Data Encryption at Rest

Sensitive database fields are encrypted by the application before they are
written and decrypted when they are read. The database and its backups only
contain ciphertext, so a stolen database dump does not expose the values.

Credentials are unchanged: passwords remain one-way bcrypt hashes, not
encrypted values.

---

## What Is Encrypted

| Table | Fields | Scheme |
|-------|--------|--------|
| `users` | `email` | Deterministic (AES-SIV) |
| `users` | `full_name` | Randomized (Fernet) |
| `persons` | `email` | Deterministic (AES-SIV) |
| `persons` | `name` | Randomized (Fernet) |
| `activities` | `staff_name`, `subject`, `description` | Randomized (Fernet) |
| `audit_logs` | `actor_email`, `detail`, `ip_address` | Randomized (Fernet) |
| `notifications` | `title`, `message` | Randomized (Fernet) |

Email addresses use deterministic encryption so equality lookups
(`WHERE email = ?`), unique indexes, login, invitations, and contact-form
person matching keep working. This leaks equality: the database can tell that
two rows contain the same email address. Uniqueness already exposes that.

Public post content, IDs, timestamps, statuses, and role/permission names are
stored in plaintext.

---

## Configuration

`ENCRYPTION_KEY` is required and must be a Fernet key. Generate one with:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Set it in the environment or `.env`:

```dotenv
ENCRYPTION_KEY=<generated-key>
```

The AES-SIV key used for emails is derived from this key with HKDF-SHA256; no
second variable is needed.

> Back up the key in a secrets manager, separately from database backups.
> Losing it makes encrypted fields unrecoverable.

---

## Database Migration

Encryption is applied to existing rows by an Alembic migration:

```bash
uv run alembic upgrade head
```

Run the migration **before** deploying the new application code. Old plaintext
values cannot be decrypted by the new code, and ciphertext may exceed the old
`VARCHAR(255)` columns on PostgreSQL.

The migration requires `ENCRYPTION_KEY` to be set. It is idempotent: values
that already carry a ciphertext prefix are skipped. The downgrade path decrypts
values back to plaintext and restores the original column types.

---

## Key Rotation

Only a single key is supported today. To rotate:

1. Keep the old key configured while running a one-off decrypt/re-encrypt
   migration with the new key.
2. Verify the data, then remove the old key.

Changing `ENCRYPTION_KEY` without re-encrypting existing rows makes those rows
unreadable.

---

## Scope & Limitations

- **Threat model:** protects database files and backups. It does not protect
  against an attacker who has the application process or its environment
  variables; those can decrypt.
- **Logs:** request logging and application logs may still contain plaintext
  emails or message content. Encryption only covers database storage.
- **Search:** encrypted values cannot be searched or sorted in SQL. `/v1/users`
  search decrypts users in Python and filters there, which is fine for a
  staff-sized table but not for very large datasets.
- **External tools:** ad-hoc SQL, reporting dashboards, and CSV exports that
  read encrypted columns directly will see ciphertext.
- **Admin dashboard:** SQLAdmin decrypts fields for display and encrypts edits.
  Sorting on encrypted columns sorts ciphertext, so it is not meaningful.
