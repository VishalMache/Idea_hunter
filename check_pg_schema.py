import asyncio, asyncpg

async def check():
    conn = await asyncpg.connect('postgresql://ideahunter:ideahunter@localhost:5432/ideahunter')
    tables = await conn.fetch("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
    print('Tables:', [r['tablename'] for r in tables])
    for tbl in ['sources', 'observations', 'problems', 'opportunity_scores', 'research_runs']:
        cols = await conn.fetch(f"SELECT column_name FROM information_schema.columns WHERE table_name='{tbl}' ORDER BY ordinal_position")
        print(f'  {tbl}: {[c["column_name"] for c in cols]}')
    await conn.close()

asyncio.run(check())
