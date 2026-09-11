#!/usr/bin/env python3
"""SimGear probe: which technique does each effect end up with?

Effect::chooseTechnique takes the first technique that both validates and
matches the requested scheme.  The instrument faces stay black, so something
in that chain fails - the predicate, or the scheme.  Log both, once per
effect, with SG_TECHNIQUE_PROBE=1.

  python3 sg_technique_probe.py [simgear-source-root]
"""
import os
import sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser('~/simgear-2020.3.19')

p = os.path.join(ROOT, 'simgear/scene/material/Technique.cxx')
s = open(p).read()
old = '''    if (_validExpression->getValue(&binding))
        newVal = VALID;
    contextInfo.valid.compareAndSwap(oldVal, newVal);
'''
new = '''    if (_validExpression->getValue(&binding))
        newVal = VALID;
    {
        static const int probe = (::getenv("SG_TECHNIQUE_PROBE") != 0) ? 1 : 0;
        if (probe)
            SG_LOG(SG_GL, SG_ALERT, "TECHPROBE validate scheme=[" << getScheme()
                   << "] -> " << (newVal == VALID ? "VALID" : "INVALID"));
    }
    contextInfo.valid.compareAndSwap(oldVal, newVal);
'''
if new in s:
    print('  schon aktuell: Technique.cxx')
else:
    assert s.count(old) == 1, 'Anker validateInContext'
    s = s.replace(old, new)
    open(p, 'w').write(s)
    print('geaendert Technique.cxx')

p2 = os.path.join(ROOT, 'simgear/scene/material/Effect.cxx')
s = open(p2).read()
# chooseTechnique: line based, the indentation differs between trees
lines = s.split('\n')
if any('TECHPROBE effect' in l for l in lines):
    print('  schon aktuell: Effect.cxx')
else:
    k = next(i for i, l in enumerate(lines) if 'Effect::chooseTechnique' in l)
    body = next(i for i, l in enumerate(lines) if i > k and 'for (auto& technique : techniques)' in l)
    cond = next(i for i, l in enumerate(lines) if i > body and 'technique->valid(info)' in l)
    ret = next(i for i, l in enumerate(lines) if i > cond and 'return technique.get();' in l)
    lines[body:ret+1] = [
        '    static const int probe = (::getenv("SG_TECHNIQUE_PROBE") != 0) ? 1 : 0;',
        '    int probeN = 0;',
        '    for (auto& technique : techniques) {',
        '        const Technique::Status st = technique->valid(info);',
        '        if (probe)',
        '            SG_LOG(SG_GL, SG_ALERT, "TECHPROBE effect=[" << getName() << "] technique "',
        '                   << probeN << " status=" << (int)st << " scheme=[" << technique->getScheme()',
        '                   << "] wanted=[" << scheme << "]");',
        '        ++probeN;',
        '        if (st == Technique::VALID && technique->getScheme() == scheme)',
        '            return technique.get();',
    ]
    s = '\n'.join(lines)
    open(p2, 'w').write(s)
    print('geaendert Effect.cxx')

print('fertig')
