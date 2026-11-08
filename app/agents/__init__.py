from app.agents.proposal_agent import proposal_agent
from app.agents.matching_agent import matching_agent
from app.agents.sponsor_discovery_agent import sponsor_discovery_agent
from app.agents.sponsor_scraper_agent import sponsor_scraper_agent
from app.agents.email_drafting_agent import email_drafting_agent
from app.agents.email_dispatch_agent import email_dispatch_agent
from app.agents.access_control_agent import access_control_agent
from app.agents.scheduler_agent import scheduler_agent

ALL_AGENTS = [
    proposal_agent,
    matching_agent,
    sponsor_discovery_agent,
    sponsor_scraper_agent,
    email_drafting_agent,
    email_dispatch_agent,
    access_control_agent,
    scheduler_agent
]
