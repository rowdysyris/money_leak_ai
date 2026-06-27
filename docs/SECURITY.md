# Security Notes

- Auth uses JWT Bearer tokens with configurable secret, algorithm, and expiry.
- Passwords are hashed with passlib/bcrypt and never returned in API responses.
- Login failures use generic messages.
- Finance endpoints require `current_user` and filter data by `user_id`.
- File uploads validate extension, size, magic bytes, filename traversal, and parse errors.
- API errors use a safe envelope and do not expose stack traces.
- Request middleware emits `X-Request-ID` and applies lightweight in-memory rate limits to auth and upload endpoints.
- Production CORS must use exact origins. Wildcards and localhost are rejected in production settings.
- `.env`, local databases, virtualenvs, node modules, build output, caches, and model artifacts are ignored.

