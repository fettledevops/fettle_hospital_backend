Runtime configuration files that are copied into images during build live here.

Expected files:

- `config/livekit/livekit.yaml`
- `config/livekit/sip.yaml`
- `config/tls/fullchain.pem`
- `config/tls/privkey.pem`

Secrets should stay in `.env.dev` or `.env.prod` where supported by the service.
