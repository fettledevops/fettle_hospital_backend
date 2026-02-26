# Asterisk Configuration for CloudConnect + LiveKit SIP

## 1. /etc/asterisk/pjsip.conf
```ini
[global]
type=global
user_agent=Asterisk PBX

[transport-udp]
type=transport
protocol=udp
bind=0.0.0.0:5060

; CloudConnect SIP Trunk Registration
[cloudconnect-trunk]
type=registration
outbound_auth=cloudconnect-auth
server_uri=sip:sbc.cloudconnect.in
client_uri=sip:Fettle@sbc.cloudconnect.in
retry_interval=60
expiration=3600

[cloudconnect-auth]
type=auth
auth_type=userpass
password=FuYs3dNnXa2
username=Fettle

[cloudconnect-aor]
type=aor
contact=sip:sbc.cloudconnect.in

[cloudconnect-endpoint]
type=endpoint
context=from-cloudconnect
disallow=all
allow=ulaw,alaw
outbound_auth=cloudconnect-auth
aors=cloudconnect-aor
direct_media=no

[cloudconnect-identify]
type=identify
endpoint=cloudconnect-endpoint
match=sbc.cloudconnect.in

; LiveKit SIP Endpoint
[livekit-sip]
type=aor
contact=sip:127.0.0.1:5061 ; Assuming LiveKit SIP is on 5061

[livekit-sip]
type=endpoint
context=to-livekit
disallow=all
allow=ulaw,alaw
aors=livekit-sip
```

## 2. /etc/asterisk/extensions.conf
```ini
[from-cloudconnect]
; Inbound calls from CloudConnect
exten => _.,1,NoOp(Inbound Call from CloudConnect)
same => n,Dial(PJSIP/livekit-sip/sip:amor-inb-final@livekit) ; Route to amor-inb-final agent

[to-livekit]
; Routing to LiveKit SIP Participants
exten => _.,1,NoOp(Routing to LiveKit)
same => n,Dial(PJSIP/livekit-sip/${EXTEN})
```

## 3. Required Ports (AWS Security Group)
- **UDP 5060:** SIP Signaling (Asterisk)
- **UDP 5061:** SIP Signaling (LiveKit SIP)
- **UDP 10000-20000:** RTP Audio (Standard)
- **UDP 50000-60000:** RTP Audio (Asterisk Config)
