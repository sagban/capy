# Security

Report a vulnerability by opening a private security advisory on this GitHub repository. Do not file a public issue for a secret, an auth bypass, or a way to read another person's diary.

Keys stay on the server. `USDA_FDC_API_KEY` and `API_ACCESS_TOKEN_SECRET` are Secret Manager secrets. Gemini is Vertex, not an API key in the app. `GoogleService-Info.plist` and `.env` files are gitignored. A pull request that adds one of those will not be merged.

`/mcp/` requires `Authorization: Bearer`. `/authenticate` only mints a one-hour token for the account that signed in. It does not store the password.
