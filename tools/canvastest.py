#!/usr/bin/env python3
"""Canvas check without the app: start fgfs like harbour-fgview, wait for
the scenery, send the app's engine-start script (it powers the aircraft up,
so the displays come on), then dump frames from /dev/shm/fgfs-frame every
few seconds.  python3 canvastest.py <aircraft> <prefix> [seconds]"""
import os, re, subprocess, sys, time, socket

aircraft, prefix = sys.argv[1], sys.argv[2]
budget = int(sys.argv[3]) if len(sys.argv) > 3 else 600
HOME = os.path.expanduser('~'); AC = HOME + '/.local/share/harbour-fgview/aircraft'
src = open(HOME + '/fgfs-work/fgview/src/harbour-fgview.cpp').read()
body = src[src.index('void startEngine()'):]; body = body[body.index('sendNasal(') + len('sendNasal('):]
body = body[:body.index('_cranking = true')]
script = ''.join(p.encode().decode('unicode_escape') for p in re.findall(r'"((?:[^"\\]|\\.)*)"', body))

def telnet(cmds, wait=2.0):
    s = socket.create_connection(('127.0.0.1', 5401), timeout=5); s.settimeout(wait)
    for c in cmds: s.sendall((c + '\r\n').encode())
    out = b''
    try:
        while True:
            d = s.recv(65536)
            if not d: break
            out += d
    except socket.timeout: pass
    s.close(); return out.decode(errors='replace')

log = open('/tmp/canvastest-%s.log' % aircraft, 'w')
proc = subprocess.Popen(['/opt/fgfs/bin/fgfs-run', '--backend=gles3', '--aircraft=' + aircraft, '--airport=LOWW',
                         '--disable-sound', '--timeofday=noon', '--disable-ai-models', '--disable-ai-traffic',
                         '--disable-terrasync', '--fg-aircraft=' + AC, '--telnet=5401', '--allow-nasal-from-sockets',
                         '--prop:/sim/menubar/visibility=false'], stdout=log, stderr=subprocess.STDOUT)
t0 = time.time(); loaded = False
while time.time() - t0 < budget:
    time.sleep(5)
    if proc.poll() is not None: print('fgfs beendet, exit', proc.returncode); sys.exit(1)
    try:
        if "'true'" in telnet(['get /sim/sceneryloaded']): loaded = True; break
    except OSError: pass
print('%s: geladen nach %.0f s' % (aircraft, time.time() - t0), flush=True)
if not loaded: proc.terminate(); sys.exit(1)
time.sleep(8)
subprocess.call(['python3', HOME + '/fgfs-work/shmdump.py', '/tmp/%s-0.png' % prefix, '--flip'])
telnet(['nasal'] + script.split('\n') + ['##EOF##'], wait=1.0)
t1 = time.time(); k = 1
while time.time() - t1 < budget - (time.time() - t0) - 20:
    time.sleep(30)
    subprocess.call(['python3', HOME + '/fgfs-work/shmdump.py', '/tmp/%s-%d.png' % (prefix, k), '--flip']); k += 1
    r = [telnet(['get /engines/engine[%d]/running' % i]).strip().split('\n')[0] for i in range(2)]
    print('t+%3.0f s  %s' % (time.time() - t1, ' | '.join(r)), flush=True)
proc.terminate()
try: proc.wait(10)
except subprocess.TimeoutExpired: proc.kill()
print('shGLES-Meldungen im Log:', sum(1 for l in open('/tmp/canvastest-%s.log' % aircraft, errors='replace') if 'shGLES' in l))
