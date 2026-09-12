import asyncio
from idea_hunter.db.session import session_scope
from idea_hunter.db.models import HardProblem, TechShift

async def seed():
    async with session_scope() as session:
        hp = HardProblem(
            title="B2B Cross-Border Payments",
            description="Sending large sums of money across borders between businesses takes 3-5 days and costs 3% in hidden FX fees.",
            industry="Fintech",
            why_it_is_hard="Legacy SWIFT network, fragmented banking infrastructure, regulatory compliance."
        )
        session.add(hp)

        ts = TechShift(
            name="Stablecoins (USDC)",
            description="Programmable, instantly settled digital dollars that run on public blockchains with near-zero transaction fees.",
            category="Fintech"
        )
        session.add(ts)

        await session.commit()
        print("Seeded 1 HardProblem and 1 TechShift!")

if __name__ == "__main__":
    asyncio.run(seed())
