"""Catalog of approved opportunity-intelligence sources.

The catalog is intentionally declarative: collection still goes through BaseCollector,
RawObservation, and the existing persistence/processing pipeline.
"""
from dataclasses import dataclass
from typing import Literal

Acquisition = Literal["official_api", "public_api", "rss", "manual_import", "disabled"]
SignalKind = Literal["problem_evidence", "product_market_evidence", "mixed"]

@dataclass(frozen=True)
class SourceDefinition:
    key: str
    name: str
    base_url: str
    group: str
    categories: tuple[str, ...]
    signal_kind: SignalKind
    reliability: float
    acquisition: Acquisition
    enabled_by_default: bool = False
    notes: str = ""


def _s(key, name, url, group, categories, kind, quality, acquisition="manual_import", enabled=False, notes=""):
    return SourceDefinition(key, name, url, group, tuple(categories), kind, quality, acquisition, enabled, notes)

SOURCES = (
    _s("producthunt", "Product Hunt", "https://www.producthunt.com", "Startup & Products", ["startup_discovery", "product_discovery"], "product_market_evidence", .70, "official_api", False, "Requires a Product Hunt access token; listings are supply signals, not customer proof."),
    _s("hackernews", "Hacker News", "https://news.ycombinator.com", "Communities", ["community_signal", "founder_signal", "trend_signal"], "mixed", .80, "public_api", True),
    _s("betalist", "BetaList", "https://betalist.com", "Startup & Products", ["startup_discovery", "product_discovery"], "product_market_evidence", .65),
    _s("betapage", "BetaPage", "https://betapage.co", "Startup & Products", ["startup_discovery", "product_discovery"], "product_market_evidence", .60),
    _s("launchingnext", "Launching Next", "https://www.launchingnext.com", "Startup & Products", ["startup_discovery", "product_discovery"], "product_market_evidence", .55),
    _s("uneed", "Uneed", "https://www.uneed.best", "Startup & Products", ["startup_discovery", "product_discovery"], "product_market_evidence", .60),
    _s("makersdev", "Makers.dev", "https://makers.dev", "Startup & Products", ["startup_discovery", "founder_signal"], "product_market_evidence", .55),
    _s("indiehackers", "Indie Hackers", "https://www.indiehackers.com", "Communities", ["community_signal", "founder_signal", "startup_discovery"], "mixed", .75),
    _s("microlaunch", "Microlaunch", "https://microlaunch.net", "Startup & Products", ["startup_discovery", "product_discovery"], "product_market_evidence", .55),
    _s("sideprojectors", "SideProjectors", "https://www.sideprojectors.com", "Startup & Products", ["startup_discovery", "product_discovery"], "product_market_evidence", .65),
    _s("pitchground", "PitchGround", "https://pitchground.com", "Startup & Products", ["product_discovery", "competitor_discovery"], "product_market_evidence", .60),
    _s("makerlog", "Makerlog", "https://getmakerlog.com", "Communities", ["founder_signal", "community_signal"], "mixed", .55),
    _s("wip", "WIP", "https://wip.co", "Communities", ["founder_signal", "startup_discovery"], "product_market_evidence", .55),
    _s("build_in_public", "Build in Public", "https://buildinpublic.com", "Communities", ["founder_signal", "community_signal"], "mixed", .55),
    _s("reddit", "Reddit", "https://www.reddit.com", "Communities", ["community_signal", "customer_pain", "founder_signal"], "problem_evidence", .90, "official_api", True, "Uses the existing credentialed Reddit collector; configure target subreddits in the query."),
    _s("devto", "DEV Community", "https://dev.to", "Communities", ["community_signal", "trend_signal", "founder_signal"], "mixed", .78, "public_api", True),
    _s("hackernoon", "HackerNoon", "https://hackernoon.com", "Communities", ["community_signal", "trend_signal"], "mixed", .65),
    _s("growthhackers", "GrowthHackers", "https://growthhackers.com", "Communities", ["community_signal", "trend_signal"], "mixed", .65),
    _s("startupbuffer", "Startup Buffer", "https://startupbuffer.com", "Startup & Products", ["startup_discovery"], "product_market_evidence", .50),
    _s("startupstash", "Startup Stash", "https://startupstash.com", "SaaS & Software", ["product_discovery", "competitor_discovery"], "product_market_evidence", .50),
    _s("appsumo", "AppSumo", "https://appsumo.com", "Startup & Products", ["product_discovery", "competitor_discovery"], "product_market_evidence", .60),
    _s("startup88", "StartUp88", "https://startup88.com", "Startup & Products", ["startup_discovery"], "product_market_evidence", .45),
    _s("startupbase", "StartupBase", "https://startupbase.io", "Startup & Products", ["startup_discovery"], "product_market_evidence", .50),
    _s("startuplister", "StartupLister", "https://startuplister.com", "Startup & Products", ["startup_discovery"], "product_market_evidence", .45),
    _s("startupranking", "Startup Ranking", "https://www.startupranking.com", "Startup & Products", ["startup_discovery", "b2b_market"], "product_market_evidence", .50),
    _s("favird", "Favird", "https://favird.com", "Startup & Products", ["product_discovery"], "product_market_evidence", .45),
    _s("saas_directory", "SaaS Directory", "https://saasdirectory.com", "SaaS & Software", ["competitor_discovery", "product_discovery"], "product_market_evidence", .50),
    _s("alternativeto", "AlternativeTo", "https://alternativeto.net", "SaaS & Software", ["competitor_discovery", "product_discovery"], "product_market_evidence", .75, "manual_import", False, "Use licensed/manual exports or explicit permission; alternatives are competition signals, not pain proof."),
    _s("submitco", "Submit.co", "https://submit.co", "SaaS & Software", ["startup_discovery", "product_discovery"], "product_market_evidence", .50),
    _s("dir_directory", "dir.directory", "https://dir.directory", "SaaS & Software", ["product_discovery", "competitor_discovery"], "product_market_evidence", .45),
    _s("productrant", "Product Rant", "https://productrant.com", "SaaS & Software", ["community_signal", "product_discovery"], "mixed", .55),
    _s("growthlist", "GrowthList", "https://growthlist.co", "SaaS & Software", ["product_discovery", "trend_signal"], "product_market_evidence", .50),
    _s("g2", "G2", "https://www.g2.com", "Customer Reviews", ["software_reviews", "customer_pain"], "problem_evidence", .95, "manual_import", False, "Use licensed API/export or user-provided review URLs; do not scrape protected review pages."),
    _s("capterra", "Capterra", "https://www.capterra.com", "Customer Reviews", ["software_reviews", "customer_pain"], "problem_evidence", .95, "manual_import", False, "Use licensed API/export or user-provided data."),
    _s("software_advice", "Software Advice", "https://www.softwareadvice.com", "Customer Reviews", ["software_reviews", "customer_pain"], "problem_evidence", .88, "manual_import"),
    _s("getapp", "GetApp", "https://www.getapp.com", "Customer Reviews", ["software_reviews", "customer_pain"], "problem_evidence", .88, "manual_import"),
    _s("trustradius", "TrustRadius", "https://www.trustradius.com", "Customer Reviews", ["software_reviews", "customer_pain"], "problem_evidence", .95, "manual_import"),
    _s("crozdesk", "Crozdesk", "https://crozdesk.com", "Customer Reviews", ["software_reviews", "customer_pain"], "problem_evidence", .82, "manual_import"),
    _s("softwaresuggest", "SoftwareSuggest", "https://www.softwaresuggest.com", "Customer Reviews", ["software_reviews", "customer_pain"], "problem_evidence", .78, "manual_import"),
    _s("financesonline", "FinancesOnline", "https://financesonline.com", "Customer Reviews", ["software_reviews", "customer_pain"], "problem_evidence", .72, "manual_import"),
    _s("clutch", "Clutch", "https://clutch.co", "B2B", ["b2b_market", "competitor_discovery", "software_reviews"], "product_market_evidence", .75, "manual_import"),
    _s("designrush", "DesignRush", "https://www.designrush.com", "B2B", ["b2b_market", "competitor_discovery"], "product_market_evidence", .65, "manual_import"),
    _s("saasworthy", "SaaSWorthy", "https://www.saasworthy.com", "B2B", ["b2b_market", "competitor_discovery", "product_discovery"], "product_market_evidence", .70, "manual_import"),
    _s("saashub", "SaaSHub", "https://www.saashub.com", "B2B", ["b2b_market", "competitor_discovery", "product_discovery"], "product_market_evidence", .70, "manual_import"),
    _s("taaft", "There's An AI For That", "https://theresanaiforthat.com", "AI", ["ai_market", "product_discovery", "trend_signal"], "product_market_evidence", .70, "manual_import", False, "Directory listings are supply signals only."),
    _s("futurepedia", "Futurepedia", "https://www.futurepedia.io", "AI", ["ai_market", "product_discovery", "trend_signal"], "product_market_evidence", .68, "manual_import"),
    _s("toolify", "Toolify", "https://www.toolify.ai", "AI", ["ai_market", "product_discovery"], "product_market_evidence", .62, "manual_import"),
    _s("futuretools", "Future Tools", "https://www.futuretools.io", "AI", ["ai_market", "product_discovery", "trend_signal"], "product_market_evidence", .65, "manual_import"),
    _s("aixploria", "Aixploria", "https://www.aixploria.com", "AI", ["ai_market", "product_discovery"], "product_market_evidence", .60, "manual_import"),
    _s("aitoolhunt", "AI Tool Hunt", "https://aitoolhunt.com", "AI", ["ai_market", "product_discovery"], "product_market_evidence", .58, "manual_import"),
)
SOURCE_BY_KEY = {source.key: source for source in SOURCES}

def get_source(key: str) -> SourceDefinition:
    try: return SOURCE_BY_KEY[key]
    except KeyError as error: raise KeyError(f"Unknown source '{key}'.") from error

