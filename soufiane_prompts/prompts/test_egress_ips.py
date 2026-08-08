#!/usr/bin/env python3
"""Does this machine leave the network from MORE THAN ONE public IP?

That is the open question in the ip_not_authorized incident: some batches were
accepted and others rejected within the same minute, from the same key. A batch's
IP is checked against the allowlist per BATCH, using the connection that created
it — so if different connections leave from different public IPs, some batches
pass and some fail, at random.

Run this from WINDOWS (the same python that runs run_prompts.py), ideally WHILE a
submission run is going:

    python test_egress_ips.py            # 40 fresh connections
    python test_egress_ips.py 200        # more samples

If it prints ONE ip  -> the machine has a stable egress; look elsewhere.
If it prints TWO+    -> that is the cause, proven, and worth showing management.
"""
import sys, ssl, json, socket, datetime, collections
import http.client
import concurrent.futures as cf

HOST, PATH = 'api.ipify.org', '/'
N = int(sys.argv[1]) if len(sys.argv) > 1 else 40


def fresh_connection_ip(_):
    """One brand-new TCP connection per call — no pooling, no reuse."""
    try:
        conn = http.client.HTTPSConnection(HOST, 443, timeout=15,
                                           context=ssl.create_default_context())
        conn.request('GET', PATH)
        ip = conn.getresponse().read().decode().strip()
        local = conn.sock.getsockname()[0]      # which interface we went out on
        conn.close()
        return ip, local
    except Exception as e:
        return f'ERROR {type(e).__name__}: {e}', '-'


stamp = datetime.datetime.now().isoformat(timespec='seconds')
with cf.ThreadPoolExecutor(10) as ex:
    results = list(ex.map(fresh_connection_ip, range(N)))

pub = collections.Counter(r[0] for r in results)
loc = collections.Counter(r[1] for r in results)

print(f'\n=== EGRESS IP TEST — {stamp} — {N} fresh connections ===\n')
print('PUBLIC IP seen by the outside world:')
for k, v in pub.most_common():
    print(f'   {v:>4}x  {k}')
print('\nLOCAL interface used:')
for k, v in loc.most_common():
    print(f'   {v:>4}x  {k}')

distinct = [k for k in pub if not k.startswith('ERROR')]
print()
if len(distinct) > 1:
    print('*** MORE THAN ONE PUBLIC IP ***')
    print('    This machine does not have a stable egress address. With an IP')
    print('    allowlist on the OpenAI key, some batches WILL be rejected at')
    print('    random while others succeed. This is the cause.')
elif len(distinct) == 1:
    print('single stable public IP at this moment:', distinct[0])
    print('    Does not rule the cause out — the address can change over time.')
    print('    Re-run this during and after a submission run to compare.')
else:
    print('no successful probe — check outbound connectivity.')

with open('IP_LOG.txt', 'a', encoding='utf-8') as fh:
    fh.write(f'{stamp}\t{json.dumps(dict(pub))}\n')
print('\nappended to IP_LOG.txt')
