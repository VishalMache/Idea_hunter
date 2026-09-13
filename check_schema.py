import sqlite3
c = sqlite3.connect('ideahunter.db')
tables = c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print('Tables:', [t[0] for t in tables])
for tbl in [t[0] for t in tables if t[0] != 'alembic_version']:
    cols = [r[1] for r in c.execute(f'PRAGMA table_info({tbl})').fetchall()]
    print(f'  {tbl}: {cols}')
