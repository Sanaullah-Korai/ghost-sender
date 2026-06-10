I spent hours reviewing a client's email setup last week. SPF, DKIM, DMARC — all correct. MX pointing to their gateway. Everything was in order.

Then I tried something simple. One openssl command directly to Exchange Online.

The email went straight to the inbox. No authentication. No filtering. No warning.

But Exchange Online also accepts mail directly on port 25 — from any IP, with no authentication. If no partner connector or transport rule is configured, Microsoft assumes the gateway already filtered everything and delivers the mail as-is.

Result: an email sent directly to Exchange Online — bypassing the gateway entirely — lands in the inbox. No SPF check. No DKIM check. No DMARC enforcement. No DLP. No content filtering. No external banner. The sender's profile photo even resolves.

This is the Ghost Sender vulnerability, disclosed by InfoGuard Labs in June 2026. Their research found over 20% of tested domains were vulnerable. Microsoft confirmed active exploitation.

How to check your organization:

dig +short MX your-domain.com
# If it doesn't return *.mail.protection.outlook.com — you're using an external gateway

echo "QUIT" | openssl s_client -connect \
  $(echo your-domain.com | tr '.' '-').mail.protection.outlook.com:25 \
  -starttls smtp -crlf -quiet 2>/dev/null | head -1
# If you see "220 Microsoft ESMTP" — Exchange Online is reachable directly

The fix in Exchange Admin Center — pick one:

1. Partner Organization Connector — restrict inbound mail to your gateway's IP ranges
2. Transport Rule at priority 0 — reject mail not from gateway IPs
3. Point MX directly to Exchange Online Protection

Full writeup and PoC tool on GitHub — link in the comments.

If your MX doesn't point to Microsoft, take five minutes to verify. The gap between "we have a gateway" and "the gateway actually protects us" is smaller than most teams realize.

#CyberSecurity #EmailSecurity #ExchangeOnline #Microsoft365
