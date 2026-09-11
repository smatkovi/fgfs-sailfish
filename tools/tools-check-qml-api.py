#!/usr/bin/env python3
"""Every method QML calls on ctl (ControlSender) or rt (FgRuntime) must be a
public slot or Q_INVOKABLE of that class, and every property it reads must be
a Q_PROPERTY.  C++ compiles happily without them; the call only fails at run
time, silently.  (0.10.2 lost setPaused and the tutorial slots that way.)"""
import re, glob, sys
W='/home/defaultuser/fgfs-work/fgview/'
cpp=open(W+'src/harbour-fgview.cpp').read(); rth=open(W+'src/fgruntime.h').read()
def class_body(src, name):
    i=src.index('class %s ' % name) if ('class %s ' % name) in src else src.index('class %s\n' % name)
    depth=0; j=src.index('{', i)
    for k in range(j, len(src)):
        if src[k]=='{': depth+=1
        elif src[k]=='}':
            depth-=1
            if depth==0: return src[j:k]
def api(body):
    slots=set(); props=set(); section=None
    for line in body.split('\n'):
        t=line.strip()
        if re.match(r'(public|private|protected)( slots| Q_SLOTS)?\s*:', t) or t=='signals:':
            section=t.rstrip(':'); continue
        m=re.match(r'Q_PROPERTY\(\s*[\w:<>]+\s+(\w+)', t)
        if m: props.add(m.group(1))
        m=re.match(r'(?:Q_INVOKABLE\s+)?(?:static\s+)?(?:[\w:<>&*]+\s+)+(\w+)\s*\(', t)
        if m and (section=='public slots' or 'Q_INVOKABLE' in t): slots.add(m.group(1))
    return slots, props
cs=api(class_body(cpp,'ControlSender')); fr=api(class_body(rth,'FgRuntime'))
bad=0
for q in sorted(glob.glob(W+'qml/**/*.qml', recursive=True)):
    txt=open(q).read()
    for obj,(slots,props) in (('ctl',cs),('rt',fr)):
        for m in set(re.findall(r'\b%s\.(\w+)\s*\(' % obj, txt)):
            if m not in slots: print('FEHLT  %-18s %s.%s()' % (q.split('/')[-1], obj, m)); bad+=1
        for m in set(re.findall(r'\b%s\.(\w+)\b(?!\s*\()' % obj, txt)):
            if m not in props and m not in slots and not m.startswith('on'):
                print('FEHLT  %-18s %s.%s (Eigenschaft)' % (q.split('/')[-1], obj, m)); bad+=1
print('ControlSender: %d Slots, %d Eigenschaften; FgRuntime: %d Slots, %d Eigenschaften; %d Luecken' % (len(cs[0]),len(cs[1]),len(fr[0]),len(fr[1]),bad))
sys.exit(1 if bad else 0)
