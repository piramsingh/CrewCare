"""Citations behind the four modelled figures -- data only, no rendering.

Mirrors the structure of METHODOLOGY.md's four models plus the worker overlay
in risk.py: each entry says what it actually informs, not just that it exists.
Three entries carry `url: None` because the citation as given had no specific
source URL (a domain-only mention, or "referenced via multiple outlets") --
render these as plain text rather than inventing a link.
"""

from __future__ import annotations

# Each figure maps to one of charts.THEME's four series colors by index
# (0=blue, 1=orange, 2=green, 3=amber), matching the dashboard's own palette.
FIGURES: list[dict] = [
    {
        "id": "pm25", "bullet": "PM", "name": "PM2.5", "series_index": 0,
        "formula": "C_in = C_out + ΔC — street level plus what the trains add",
        "description": "PM2.5 accounts for 90 percent of all PM10 data, which has shown to have adverse effects on health. "
        "As we do not have exact PM2.5 data, we have pulled the air quality index of the outside and modeled for subway data "
        "by accounting for PM2.5 released by trains, buildup, etc.",
        "climate": "PM2.5 increases as the number of wildfires and floods increase. With the increase of heatwaves and floods in NYC, "
        "these events create small particles in the air, skyrocketing the count.",
        "groups": [
            {"title": "Field measurement studies", "items": [
                {"name": "NYU/DOT National Transportation Library — Comprehensive PM2.5 Analysis of the NYC Subway System (1-sec interval, 341 platforms)",
                 "tag": "rosap.ntl.bts.gov", "url": "https://rosap.ntl.bts.gov",
                 "note": "The closest thing to ground truth for this model's ΔC output — and the reference METHODOLOGY.md checks itself against, where it reads ~2× low."},
                {"name": "PLOS ONE — Exposure to fine particulate matter in the NYC subway during home–work commute",
                 "tag": "journals.plos.org", "url": "https://journals.plos.org",
                 "note": "Independent confirmation that platform PM2.5 is a real, elevated commuter exposure, not a modelling artifact."},
                {"name": "ScienceDirect — Particulate matter concentration and composition in the NYC subway (Chillrud et al. lineage)",
                 "tag": "sciencedirect.com", "url": "https://www.sciencedirect.com",
                 "note": "The chemistry showing subway PM2.5 is iron-rich wheel/brake dust, not combustion soot — why the model treats trains as a mechanical wear source."},
                {"name": "NYU Grossman School of Medicine — 71-station, multi-city subway air study",
                 "tag": "no source URL given", "url": None,
                 "note": "Cross-system context for how NYC's modelled levels compare to other subways."},
                {"name": "Columbia Climate School capstone — in-train PM2.5 decay dynamics",
                 "tag": "sps.columbia.edu", "url": "https://sps.columbia.edu",
                 "note": "A ~3-minute half-life after doors close — evidence for how fast ventilation clears a car, informing the ACH assumption."},
                {"name": "CDC / stacks.cdc.gov — the “river-tunnel effect” on NYC subway PM2.5",
                 "tag": "stacks.cdc.gov", "url": "https://stacks.cdc.gov",
                 "note": "Documents particulate concentrating along tunnel “rivers” of airflow — a mechanism this model's single well-mixed box can't represent."},
            ]},
            {"title": "Indoor mass-balance formulas", "items": [
                {"name": "eScholarship (LBNL lineage) — governing equation for indoor particle dynamics",
                 "tag": "escholarship.org", "url": "https://escholarship.org",
                 "note": "This is literally where C_in = C_out + ΔC comes from: a source term against a ventilation sink."},
                {"name": "APO — HealthyHousing2016 conference paper, steady-state indoor PM2.5 prediction",
                 "tag": "apo.org.au", "url": "https://apo.org.au",
                 "note": "The same source-and-sink shape, applied to a room — indoor.py's methodology in miniature."},
            ]},
            {"title": "Ventilation & air exchange (ACH)", "items": [
                {"name": "Björling — tracer-gas air exchange study, underground train station",
                 "tag": "diva-portal.org", "url": "https://www.diva-portal.org",
                 "note": "Real measured ACH in a station — what the model's 4.0 / 12.0 ACH constants are a judgment call against."},
                {"name": "NSF/PAR — CFD analysis of train piston-effect particle distribution",
                 "tag": "par.nsf.gov", "url": "https://par.nsf.gov",
                 "note": "The physical mechanism ACH stands in for: a moving train pumping air through the platform box."},
                {"name": "Modares — 3D numerical analysis of train-induced tunnel flow",
                 "tag": "mme.modares.ac.ir", "url": "https://mme.modares.ac.ir",
                 "note": "A second data point on piston-effect ventilation, from a different tunnel geometry."},
                {"name": "Brookhaven National Lab — S-SAFE subway air-quality study (Q&A)",
                 "tag": "bnl.gov — results not public", "url": "https://www.bnl.gov",
                 "note": "Listed as a lead, not a source of numbers: the study exists but its findings aren't published."},
                {"name": "CUNY CREST — real-time CO2 / PM2.5 / heat-index research poster",
                 "tag": "crest.cuny.edu", "url": "https://crest.cuny.edu",
                 "note": "Direct platform instrumentation — the kind of measurement that would let this model be calibrated instead of assumed."},
            ]},
        ],
    },
    {
        "id": "heat", "bullet": "T°", "name": "Temperature", "series_index": 1,
        "formula": "T_in = (C_vent·T_out + UA·T_ground + Q_internal) / (C_vent + UA)",
        "description": "Every time a train brakes, its kinetic energy has to go somewhere -- that's heat. We modeled the "
        "platform as a heat balance: heat coming in from braking, air conditioning, and people, versus heat leaving "
        "through ventilation and into the surrounding ground. We calibrated the ground temperature against one real "
        "anchor point (a quiet station reading 55°F on the coldest day) instead of guessing it.",
        "climate": "This model is driven by a rolling average of outdoor temperature, so as NYC's summers get hotter "
        "and heat waves get more frequent, the street-level input this formula starts from keeps climbing -- and "
        "because platforms track a fixed share of that outdoor temperature, hotter summers mean hotter platforms, "
        "directly and predictably.",
        "groups": [
            {"title": "Field reports", "items": [
                {"name": "NYC DCAS / Mayor's Office press release — 96°F at Brooklyn Bridge–City Hall",
                 "tag": "nyc.gov", "url": "https://www.nyc.gov",
                 "note": "The reference anecdote for how hot platforms get in summer — an anchor for sanity-checking the model's own output."},
                {"name": "Gothamist — MTA's RFI for geothermal / heat-capture cooling at 168th & 181st St",
                 "tag": "gothamist.com", "url": "https://gothamist.com",
                 "note": "Official acknowledgment from the MTA itself that platform heat is bad enough to engineer around."},
                {"name": "Regional Plan Association — platform temperature data, 94–104°F on 86°F days",
                 "tag": "referenced via multiple outlets — no single source URL given", "url": None,
                 "note": "An independent range the model's own “Resulting platform temperatures” table can be checked against."},
                {"name": "Mass Transit Magazine — coverage of MTA heat reporting",
                 "tag": "trade press — no source URL given", "url": None,
                 "note": "How the transit industry itself frames the same problem this dashboard models."},
            ]},
            {"title": "Heat-balance modeling literature", "items": [
                {"name": "arXiv — heat balance model for subway tunnel thermal regime",
                 "tag": "arxiv.org", "url": "https://arxiv.org",
                 "note": "The same source-vs-sink structure (ventilation vs. ground conduction) thermal.py implements."},
                {"name": "ScienceDirect — analytical tunnel-temperature model coupling thermal mass and ventilation",
                 "tag": "sciencedirect.com", "url": "https://www.sciencedirect.com",
                 "note": "Backs the “tunnel shell as thermal flywheel” idea behind using a 31-day trailing outdoor mean instead of the live reading."},
                {"name": "ScienceDirect — STESS, subway thermal environment simulation software",
                 "tag": "sciencedirect.com", "url": "https://www.sciencedirect.com",
                 "note": "A full research-grade simulator — this app's one closed-form equation is a deliberately simplified stand-in for tools like it."},
            ]},
        ],
    },
    {
        "id": "humidity", "bullet": "RH", "name": "Humidity & mold", "series_index": 2,
        "formula": "Dew point conserved street→platform; RH derived last from modelled T_in",
        "description": "Underground air doesn't get dehumidified, so we assumed the actual amount of moisture in the "
        "air -- not the percentage, which changes with temperature -- stays the same from street to platform. We "
        "calculate relative humidity last, after modeling the platform's temperature, since RH is just how much "
        "water the air is holding relative to how much it could hold at that temperature.",
        "climate": "Warmer air holds more moisture, so as NYC warms, the baseline humidity carried down from the "
        "street rises too. Paired with the heavier rainstorms climate change is bringing, that means more days "
        "where conditions cross into the range where mold can actually start growing.",
        "groups": [
            {"title": "Mold & dust resuspension", "items": [
                {"name": "PMC / NIH — airborne mold and endotoxin concentrations after New Orleans flooding",
                 "tag": "PMC1570051", "url": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC1570051",
                 "note": "The evidence base behind the 24–48h drying-window threshold flood.py's mold classifier uses."},
                {"name": "Science.gov — road dust resuspension emission buildup model",
                 "tag": "science.gov", "url": "https://www.science.gov",
                 "note": "The general pattern for how settled particulate re-enters the air — relevant to platform dust as much as mold."},
                {"name": "PMC / NIH — geochemical and health-risk characterization of road dust",
                 "tag": "PMC7084894", "url": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7084894",
                 "note": "Supports treating platform dust as its own exposure pathway, distinct from ambient PM2.5."},
                {"name": "ResearchGate — Madrid road dust resuspension implementation study",
                 "tag": "researchgate.net", "url": "https://www.researchgate.net",
                 "note": "A worked example of the same resuspension modeling approach, outside NYC."},
            ]},
        ],
    },
    {
        "id": "flood", "bullet": "FL", "name": "Flood risk", "series_index": 3,
        "formula": "Pluvial exceedance (rainfall vs. sewer capacity) scored; fluvial (river) kept as separate context",
        "description": "We didn't build a physics model for this one -- flooding either happens or it doesn't, and "
        "mold either grows or it doesn't, so we used a threshold system instead. If rainfall crosses NYC's official "
        "storm-sewer design capacity (1.75 in/hr) and the area doesn't dry out within 24-48 hours, we flag it as a "
        "mold risk, based on public health drying-window guidance.",
        "climate": "Climate change is making heavy rainstorms more frequent and more intense in NYC, so the sewer "
        "system gets overwhelmed more often -- not because the sewers are getting worse, but because the storms "
        "are. That means more of the rainfall events that start this whole flooding-to-mold chain in the first place.",
        "groups": [
            {"title": "", "items": [
                {"name": "NYC Stormwater Flood Maps",
                 "tag": "data.cityofnewyork.us · 9i7c-xyvv", "url": "https://data.cityofnewyork.us/d/9i7c-xyvv",
                 "note": "The city's own pluvial-flood mapping — the same rainfall-vs-drainage logic flood.py's exceedance check encodes."},
                {"name": "MTA Climate Resilience briefing",
                 "tag": "mta.info/document/124996", "url": "https://www.mta.info/document/124996",
                 "note": "Direct source of the 1.75 in/hr sewer-capacity threshold, plus real storms (Ida, Elsa, Ophelia) that exceeded it and flooded stations."},
                {"name": "NPCC4 — NYC's official climate-health assessment",
                 "tag": "climateassessment.nyc", "url": "https://climateassessment.nyc",
                 "note": "The civic context the flood/mold thresholds sit inside."},
                {"name": "Washington Post — analysis of MTA flood-incident data (200 of 472 stations)",
                 "tag": "washingtonpost.com", "url": "https://www.washingtonpost.com",
                 "note": "An outside check on how widespread station flooding actually is, independent of MTA's own reporting."},
            ]},
        ],
    },
    {
        "id": "worker", "bullet": "W", "name": "Worker overlay & precautions", "series_index": None,
        "formula": "+1 level for a worker whose condition crosses a documented mechanism on the relevant axis",
        "description": "This isn't a new formula -- it's a simple rule layered on top of the other three. If a "
        "worker has a condition (like asthma) that makes them more sensitive to something the station is already "
        "flagging, we bump their personal risk level up by one, capped so it can never exceed Severe.",
        "climate": "This layer doesn't respond to climate change directly, but it inherits everything above it -- "
        "as PM2.5, heat, and mold risk all climb with a warming climate, more workers end up crossing their own "
        "uplift threshold more often, even without changing this rule at all.",
        "groups": [
            {"title": "", "items": [
                {"name": "NIOSH — Criteria for a Recommended Standard: Occupational Exposure to Heat and Hot Environments",
                 "tag": "cdc.gov/niosh", "url": "https://www.cdc.gov/niosh",
                 "note": "Source of the work/rest-by-the-hour framing risk.py's precaution text points to directly, rather than a bare temperature cutoff."},
            ]},
        ],
    },
]

CONTEXT_GROUPS: list[dict] = [
    {"title": "MTA operational & safety datasets", "items": [
        {"name": "MTA Subway Entrances and Exits: 2024", "tag": "data.ny.gov · i9wp-a4ja",
         "url": "https://data.ny.gov/d/i9wp-a4ja",
         "note": "Per-station entrance counts — a possible ventilation-exposure proxy, unused today."},
        {"name": "NYC Open Data — Subway Entrances", "tag": "data.cityofnewyork.us · drex-xx56",
         "url": "https://data.cityofnewyork.us/d/drex-xx56",
         "note": "A second, city-side entrance dataset covering the same ground."},
        {"name": "MTA NYCT Safety Data: Beginning 2019", "tag": "data.ny.gov · uf7t-sfzu",
         "url": "https://data.ny.gov/d/uf7t-sfzu",
         "note": "System-wide safety incidents — background, not linked to any station score."},
        {"name": "MTA Subway and Bus Lost Time Accidents: Beginning 2021", "tag": "data.ny.gov · 8vjt-4zv4",
         "url": "https://data.ny.gov/d/8vjt-4zv4",
         "note": "Worker injury data — the closest existing dataset to validating the worker overlay against real outcomes."},
        {"name": "MTA Subway Hourly Ridership: 2017–2019", "tag": "data.ny.gov · t69i-h2me",
         "url": "https://data.ny.gov/d/t69i-h2me",
         "note": "Real per-station, per-hour service — what would replace the flat route_count × 9 trains/hour assumption."},
        {"name": "MTA Subway Hourly Ridership: 2020–2024", "tag": "data.ny.gov · wujg-7c2s",
         "url": "https://data.ny.gov/d/wujg-7c2s",
         "note": "Same series, continued through the post-pandemic recovery."},
        {"name": "MTA Subway Hourly Ridership: Beginning 2025", "tag": "data.ny.gov · 5wq4-mkjj",
         "url": "https://data.ny.gov/d/5wq4-mkjj",
         "note": "The current window of the same series."},
        {"name": "MTA GTFS-realtime API", "tag": "api.mta.info", "url": "https://api.mta.info",
         "note": "Live train positions — METHODOLOGY.md names GTFS stop_times.txt as “the highest-value data addition available.”"},
    ]},
    {"title": "Heat vulnerability & neighborhood context", "items": [
        {"name": "NYC Heat Vulnerability Index Rankings", "tag": "data.cityofnewyork.us · 4mhf-duep",
         "url": "https://data.cityofnewyork.us/d/4mhf-duep",
         "note": "Neighborhood-level heat risk — context for which station areas sit in already-vulnerable neighborhoods."},
        {"name": "NYCCAS Air Pollution Rasters", "tag": "data.cityofnewyork.us · q68s-8qxv",
         "url": "https://data.cityofnewyork.us/d/q68s-8qxv",
         "note": "Street-level pollution at finer resolution than Open-Meteo's ~11km grid — a plausible upgrade path for the outdoor PM2.5 input."},
        {"name": "NYC Community Air Survey (NYCCAS) reports", "tag": "nyccas.cityofnewyork.us",
         "url": "https://nyccas.cityofnewyork.us",
         "note": "The program's own published findings, for reading the raster data in context."},
    ]},
]

LIVE_APIS: list[dict] = [
    {"name": "Open-Meteo Air Quality API", "url": "https://open-meteo.com/en/docs/air-quality-api",
     "note": "Street-level PM2.5 — the C_out term every platform PM2.5 figure is built on."},
    {"name": "Open-Meteo Weather Forecast API", "url": "https://open-meteo.com/en/docs",
     "note": "Temperature, humidity, dew point, pressure and precipitation — T_out, RH_out, and the pluvial-flood check."},
    {"name": "Open-Meteo Flood API", "url": "https://open-meteo.com/en/docs/flood-api",
     "note": "Daily river discharge — the fluvial context figure, kept separate from the mold-risk score."},
]
