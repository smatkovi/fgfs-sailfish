#!/usr/bin/env python3
"""Engine-start test without the app: start fgfs the way harbour-fgview
does, send the very Nasal script the app's startEngine() sends (read out
of harbour-fgview.cpp, so the test cannot drift from the app), and watch
/engines/engine[N]/running over the telnet channel.

  python3 enginetest.py <aircraft> [seconds] [airport]"""
import os, re, socket, subprocess, sys, time

aircraft = sys.argv[1]
budget = int(sys.argv[2]) if len(sys.argv) > 2 else 300
airport = sys.argv[3] if len(sys.argv) > 3 else 'LOWW'
HOME = os.path.expanduser('~')
AC = HOME + '/.local/share/harbour-fgview/aircraft'

# --- the script, verbatim from the app ---------------------------------
src = open(HOME + '/fgfs-work/fgview/src/harbour-fgview.cpp').read()
body = src[src.index('void startEngine()'):]
body = body[body.index('sendNasal(') + len('sendNasal('):]
body = body[:body.index('_cranking = true')]
pieces = re.findall(r'"((?:[^"\\]|\\.)*)"', body)
script = ''.join(p.encode().decode('unicode_escape') for p in pieces)
assert 'starter' in script and '##EOF##' not in script

def telnet(cmds, wait=2.0):
    s = socket.create_connection(('127.0.0.1', 5401), timeout=5)
    s.settimeout(wait)
    for c in cmds:
        s.sendall((c + '\r\n').encode())
    out = b''
    try:
        while True:
            d = s.recv(65536)
            if not d: break
            out += d
    except socket.timeout:
        pass
    s.close()
    return out.decode(errors='replace')

def getprop(p):
    for attempt in range(3):
        o = telnet(['get ' + p])
        m = re.search(re.escape(p.split('/')[-1]) + r"\s*=\s*'([^']*)'", o)
        if m: return m.group(1)
        if 'nil' in o or 'ERR' in o: return None
        time.sleep(1)
    return None

log = open('/tmp/enginetest-%s.log' % aircraft, 'w')
proc = subprocess.Popen(['/opt/fgfs/bin/fgfs-run', '--backend=gles3', '--aircraft=' + aircraft,
                         '--airport=' + airport, '--disable-sound', '--timeofday=noon',
                         '--disable-ai-models', '--disable-ai-traffic', '--disable-terrasync',
                         '--fg-aircraft=' + AC, '--telnet=5401', '--allow-nasal-from-sockets',
                         '--prop:/sim/menubar/visibility=false'],
                        stdout=log, stderr=subprocess.STDOUT)
t0 = time.time()
loaded = False
while time.time() - t0 < budget:
    time.sleep(5)
    if proc.poll() is not None:
        print('fgfs beendet, exit', proc.returncode); sys.exit(1)
    try:
        if getprop('/sim/sceneryloaded') == 'true':
            loaded = True; break
    except OSError:
        pass
print('%s: geladen nach %.0f s' % (aircraft, time.time() - t0), flush=True)
if not loaded:
    proc.terminate(); print('nicht geladen'); sys.exit(1)
time.sleep(10)
n = 0
# ls does not create nodes; a telnet "get" on a missing property would
n = 0
for i in range(8):
    o = telnet(['ls /engines/engine[%d]' % i])
    m = re.search(r'^running\s*=\s*\S+\s*\((\w+)\)', o, re.M)
    if m and m.group(1) != 'none': n = i + 1
print('Triebwerke mit running-Knoten:', n, flush=True)
before = [getprop('/engines/engine[%d]/running' % i) for i in range(max(n, 1))]  # after the count, so nothing is created first
print('running vorher:', before, flush=True)
telnet(['nasal'] + script.split('\n') + ['##EOF##'], wait=1.0)
t1 = time.time()
while time.time() - t1 < budget - (t1 - t0):
    time.sleep(15)
    st = []
    for i in range(max(n, 1)):
        r = getprop('/engines/engine[%d]/running' % i)
        n2 = getprop('/engines/engine[%d]/n2' % i) or getprop('/engines/engine[%d]/rpm' % i)
        stt = getprop('/controls/engines/engine[%d]/starter' % i)
        st.append('%d:%s n=%s st=%s' % (i, r, (n2 or '?')[:5], stt))
    print('t+%3.0f s  %s' % (time.time() - t1, '  '.join(st)), flush=True)
    if n and all(getprop('/engines/engine[%d]/running' % i) == 'true' for i in range(n)):
        print('ALLE LAUFEN nach %.0f s' % (time.time() - t1)); break
proc.terminate()
try: proc.wait(10)
except subprocess.TimeoutExpired: proc.kill()
