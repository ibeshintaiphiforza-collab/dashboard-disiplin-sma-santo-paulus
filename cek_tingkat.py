import sys
sys.path.insert(0, '.')

import sqlite3
from core import analytics, analytics_charts as ac

conn = sqlite3.connect('data/disiplin.db')
jurnal = analytics.load_jurnal()
tingkat = analytics.analisis_per_tingkat(jurnal)
print(tingkat.to_string())
print()
print('tingkat values:', list(tingkat['tingkat']))
print('tingkat types:', [type(t).__name__ for t in tingkat['tingkat']])
fig = ac.fig_tingkat(tingkat)
for t in fig.data:
    print('trace', t.name, 'x=', list(t.x))
