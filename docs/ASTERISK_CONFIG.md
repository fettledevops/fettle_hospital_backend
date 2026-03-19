# Asterisk and CloudConnect SIP Configuration

Updated for the current infrastructure direction on 2026-03-19.

## Scope

This document is a template reference for configuring Asterisk when bridging:

- CloudConnect SIP
- LiveKit SIP
- the Fettle backend voice workflow

It is intentionally placeholder-based. Do not commit real production secrets, IPs, DIDs, or credentials into this file.

## Important Notes Before You Apply It

- the backend repository is moving toward containerized deployment and CI/CD
- Asterisk may remain host-managed even if Django, Celery, and LiveKit are containerized
- values below must be replaced with your actual environment values
- validate all provider requirements with CloudConnect before applying in production

## Required Runtime Values

Replace these placeholders before rollout:

- `<CLOUDCONNECT_HOST>`
- `<CLOUDCONNECT_PORT>`
- `<CLOUDCONNECT_USERNAME>`
- `<CLOUDCONNECT_PASSWORD>`
- `<PUBLIC_DID>`
- `<PUBLIC_HOST_OR_IP>`
- `<LIVEKIT_SIP_HOST>`
- `<LIVEKIT_AGENT_NAME>`

## `/etc/asterisk/pjsip.conf`

```ini
[global]
type=global
user_agent=Asterisk PBX

[transport-udp]
type=transport
protocol=udp
bind=0.0.0.0:<CLOUDCONNECT_PORT>

; Registration with CloudConnect
[cloudconnect-trunk]
type=registration
outbound_auth=cloudconnect-auth
server_uri=sip:<CLOUDCONNECT_HOST>:<CLOUDCONNECT_PORT>
client_uri=sip:<CLOUDCONNECT_USERNAME>@<CLOUDCONNECT_HOST>:<CLOUDCONNECT_PORT>
retry_interval=60
expiration=3600

[cloudconnect-auth]
type=auth
auth_type=userpass
username=<CLOUDCONNECT_USERNAME>
password=<CLOUDCONNECT_PASSWORD>

[cloudconnect-aor]
type=aor
contact=sip:<CLOUDCONNECT_HOST>:<CLOUDCONNECT_PORT>

[cloudconnect-endpoint]
type=endpoint
context=from-cloudconnect
disallow=all
allow=ulaw,alaw
outbound_auth=cloudconnect-auth
aors=cloudconnect-aor
direct_media=no
from_user=<PUBLIC_DID>
from_domain=<CLOUDCONNECT_HOST>

[cloudconnect-identify]
type=identify
endpoint=cloudconnect-endpoint
match=<CLOUDCONNECT_HOST>

; LiveKit SIP bridge
[livekit-sip-aor]
type=aor
contact=sip:<LIVEKIT_SIP_HOST>

[livekit-sip-endpoint]
type=endpoint
context=to-livekit
disallow=all
allow=ulaw,alaw
aors=livekit-sip-aor
direct_media=no
```

## `/etc/asterisk/extensions.conf`

```ini
[from-cloudconnect]
exten => _.,1,NoOp(Inbound Call to ${EXTEN})
same => n,Dial(PJSIP/livekit-sip-endpoint/sip:<LIVEKIT_AGENT_NAME>@<LIVEKIT_SIP_HOST>)

[to-livekit]
exten => _.,1,NoOp(Outbound Call via CloudConnect)
same => n,Set(PJSIP_HEADER(add,Contact)=<sip:<PUBLIC_DID>@<PUBLIC_HOST_OR_IP>:<CLOUDCONNECT_PORT>>)
same => n,Dial(PJSIP/cloudconnect-endpoint/sip:${EXTEN}@<CLOUDCONNECT_HOST>:<CLOUDCONNECT_PORT>)
```

## `/etc/asterisk/rtp.conf`

```ini
[general]
rtpstart=10000
rtpend=40000
```

## Firewall / Security Group Guidance

At minimum, validate these ranges against your actual deployment:

- SIP signaling port for CloudConnect
- RTP media port range for Asterisk
- LiveKit HTTP / signaling port
- LiveKit RTC TCP port
- LiveKit SIP port
- any provider-specific IP allowlists

If you are following the current `.env.prod` defaults in this repo, pay attention to:

- `LIVEKIT_HTTP_PORT=7880`
- `LIVEKIT_RTC_TCP_PORT=7881`
- `LIVEKIT_SIP_PORT=5060`
- `LIVEKIT_SIP_RTP_PORT_RANGE_START=10000`
- `LIVEKIT_SIP_RTP_PORT_RANGE_END=20000`
- `LIVEKIT_RTC_PORT_RANGE_START=50000`
- `LIVEKIT_RTC_PORT_RANGE_END=60000`

## Deployment Guidance

Recommended ownership split:

- Asterisk: host-managed
- Django, Celery, Redis, LiveKit server, LiveKit SIP: container-managed

That split keeps SIP/PBX operations explicit while still allowing CI/CD for the application stack.

## Validation Checklist

After applying config:

- Asterisk registration to CloudConnect succeeds
- inbound calls reach the LiveKit SIP bridge
- outbound calls can traverse from LiveKit to CloudConnect
- audio flows in both directions
- caller ID and contact headers are accepted by the provider
- no firewall rule blocks RTP or SIP signaling

## Security Reminder

Never leave real credentials in tracked markdown files. Use placeholders here and inject actual values through secure operational runbooks or secret stores.
