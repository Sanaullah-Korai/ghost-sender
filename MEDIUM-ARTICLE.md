# Your SPF, DKIM, and DMARC Are Useless If Exchange Online Is Misconfigured

## Most security teams set up email authentication and call it done. But Exchange Online has a default behavior that silently accepts mail from anywhere — completely skipping your gateway, your filters, and every authentication check. Here's how to find it and fix it.

---

Most organizations believe their email is protected. They've configured SPF, DKIM, and DMARC. They've invested in third-party gateways like Forcepoint, Proofpoint, or Mimecast. They've tuned DLP policies and attachment sandboxing.

None of that matters if an attacker skips every single one of those defenses with a single TCP connection.

### The Discovery

During a recent assessment, I noticed something in the mail flow configuration. The MX record pointed to a third-party gateway — but Exchange Online was sitting right behind it, accepting mail directly on its default endpoint.

I opened a terminal and typed:

```
openssl s_client -connect domain-com.mail.protection.outlook.com:25 -starttls smtp
```

The response came back immediately: `220 Microsoft ESMTP MAIL Service ready`. Exchange Online was listening. No authentication required. No IP allowlisting. Just an open door.

A minute later, I had delivered a spoofed email — from "the CEO" — straight to an internal mailbox. No external warning banner. The CEO's profile picture appeared next to the sender name. SPF failed. DKIM was absent. DMARC said `p=reject`. Exchange Online delivered it anyway.

### Why This Happens

This is the **Ghost Sender** vulnerability, disclosed by InfoGuard Labs in June 2026. It affects any Microsoft 365 tenant that uses an external MX record without a partner connector or transport rule.

Here's the normal mail flow:

```
Internet → MX Gateway (Forcepoint) → Exchange Online → Inbox
              ↑
        DLP, SPF, DKIM, DMARC,
        content filtering, attachment
        scanning all happen here
```

And here's what happens when an attacker skips the MX:

```
Attacker → Exchange Online → Inbox
              ↑
        None of the above.
        Exchange Online sees external MX
        configured and trusts the mail
        unconditionally.
```

Exchange Online assumes the third-party gateway already performed all security checks. It's a reasonable assumption — except there's no enforcement. No mechanism that says "only accept mail that actually came through the gateway." Without a partner connector or transport rule restricting inbound IPs, Exchange Online will accept mail from anyone, anywhere.

### What Gets Bypassed

Everything:

- **DLP** — Data Loss Prevention policies don't fire
- **Content filtering** — Keyword blocks, regex policies, all skipped
- **Attachment scanning** — No sandboxing, no file type restrictions
- **URL rewriting** — Links aren't rewritten or analyzed
- **SPF** — `-all` hard fail is ignored
- **DKIM** — No signature? No problem
- **DMARC** — `p=reject` policy is not enforced
- **External sender tagging** — No "CAUTION: External Sender" banner
- **Anti-spam, anti-phishing** — Never invoked

The email lands in the inbox looking like it came from the desk next door. The sender's profile photo resolves. It appears in the same conversation thread. For all practical purposes, it is an internal email.

### Real-World Impact

In practice, an attacker can:

- Send an email appearing to be from the CFO requesting an urgent wire transfer, complete with realistic signature formatting
- Deliver a password reset notification linking to an external portal — no URL rewriting, no warning
- Send attachments that would normally be blocked — the gateway never inspects them

### The Fix (10 Minutes)

If you're running Exchange Online behind a third-party gateway, open your Exchange Admin Center now and pick one:

**Option 1 — Partner Connector (Microsoft's recommendation):**
```
Mail Flow → Connectors → Add
From: Partner organization
Identify by: Sender IP address
IP ranges: [your gateway's IPs only — nothing else]
Security: Reject email not sent from these IPs
```

**Option 2 — Transport Rule:**
```
Mail Flow → Rules → New → Priority 0
If sender is external AND sender IP not in [gateway IPs]
Reject (5.7.1)
```

**Option 3 — Remove the external MX:**
```
Point MX directly to Exchange Online Protection
Domain-com.mail.protection.outlook.com
```

### How to Check Your Own Organization

```bash
# Check your MX
dig +short MX your-domain.com

# If the answer is NOT *.mail.protection.outlook.com,
# you have an external gateway.

# Test if M365 EOP is directly reachable:
echo "QUIT" | openssl s_client -connect \
  $(echo your-domain.com | tr '.' '-').mail.protection.outlook.com:25 \
  -starttls smtp -crlf -quiet 2>/dev/null | head -1
```

If you see `220 Microsoft ESMTP MAIL Service ready` — and you don't have a partner connector — you're vulnerable.

### The Bigger Picture

Email security relies on layered defenses. But those layers only work if every email flows through them. Exchange Online's default behavior — trusting inbound mail when an external MX exists — made sense when connectors were first introduced. Today, with attackers actively exploiting this gap, it needs to be addressed.

The fix takes ten minutes. The impact of leaving it open is significant.

---

*This article is for educational purposes. Test only systems you own or have written authorization to assess. The Ghost Sender tool referenced is available on GitHub for authorized security testing.*

**References:**
- [InfoGuard Labs — Ghost Sender](https://labs.infoguard.ch/posts/ghost-sender/)
- [Microsoft — Direct Send vs Sending Directly to Exchange Online](https://techcommunity.microsoft.com/blog/exchange/direct-send-vs-sending-directly-to-an-exchange-online-tenant/4439865)
- [PoC Tool on GitHub](https://github.com/Sanaullah-Korai/ghost-sender)
