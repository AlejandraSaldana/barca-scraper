from fastapi import FastAPI
from bs4 import BeautifulSoup
import requests
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware
from zoneinfo import ZoneInfo
import cloudscraper
from fastapi.responses import Response

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://localhost:5173",
        "http://localhost:5173",
        "http://localhost:5174",
    ],
    allow_methods=["GET"],
    allow_headers=["*"],
)

VAR_URL = "https://www.fcbarcelona.es/es/futbol/primer-equipo/calendario"
FEM_URL = "https://www.fcbarcelona.es/es/futbol/femenino/calendario"
MADRID_TZ = ZoneInfo("Europe/Madrid")


def parse_fixture(fixture, category):
    """Extrae los datos de un elemento fixture del HTML."""
    date_div = fixture.find("div", class_="fixture-result-list__fixture-date")
    if not date_div or not date_div.get("data-fixture-date"):
        return None

    timestamp = int(date_div["data-fixture-date"])
    match_dt = datetime.fromtimestamp(timestamp / 1000, tz=MADRID_TZ)

    # Los nombres de equipo usan clases distintas según varonil/femenil
    # Varonil: fixture-result-list__team-name
    # Femenil: fixture-info__name
    teams = fixture.find_all("span", class_="fixture-result-list__team-name")
    if not teams:
        teams_divs = fixture.find_all("div", class_="fixture-info__name")
        home = teams_divs[0].get_text(strip=True) if len(teams_divs) > 0 else "FC Barcelona"
        away = teams_divs[1].get_text(strip=True) if len(teams_divs) > 1 else "Rival"
    else:
        home = teams[0].get_text(strip=True) if len(teams) > 0 else "FC Barcelona"
        away = teams[1].get_text(strip=True) if len(teams) > 1 else "Rival"

    competition_tag = fixture.find("div", class_="fixture-result-list__fixture-competition")
    competition = competition_tag.get_text(strip=True) if competition_tag else "Competición"

    return {
        "fixture_id": f"{category}-{timestamp}",
        "category": category,
        "datetime": match_dt.isoformat(),
        "home_team": home,
        "away_team": away,
        "competition": competition,
    }


def get_next_matches(url, tag, class_name, category, limit=2):
    """
    Igual que tu función original pero devuelve una lista
    con datos extra del partido.
    """
    try:
        soup = BeautifulSoup(requests.get(url, timeout=10).text, "html.parser")
    except Exception:
        return []

    now_ts = datetime.now(tz=MADRID_TZ).timestamp() * 1000
    results = []

    for fixture in soup.find_all(tag, class_=class_name):
        if len(results) >= limit:
            break

        date_div = fixture.find("div", class_="fixture-result-list__fixture-date")
        if not date_div or not date_div.get("data-fixture-date"):
            continue

        # Ignorar partidos pasados (igual que tu versión original)
        if int(date_div["data-fixture-date"]) < now_ts:
            continue

        data = parse_fixture(fixture, category)
        if data:
            results.append(data)

    return results


@app.get("/")
def root():
    return {"status": "Barca scraper API"}


@app.get("/next-game")
def get_next():
    """Próximo partido global — el más cercano entre varonil y femenil."""
    var_matches = get_next_matches(VAR_URL, "a", "fixture-result-list__fixture-link", "varonil", limit=1)
    fem_matches = get_next_matches(FEM_URL, "li", "fixture-result-list__fixture", "femenil", limit=1)

    candidates = var_matches + fem_matches
    if not candidates:
        return {"error": "No se encontraron partidos"}

    return min(candidates, key=lambda m: m["datetime"])


@app.get("/next-matches")
def get_next_matches_hub():
    """Próximos 2 varoniles y 2 femeniles — para el WatchPartyHUB."""
    var_matches = get_next_matches(VAR_URL, "a", "fixture-result-list__fixture-link", "varonil", limit=2)
    fem_matches = get_next_matches(FEM_URL, "li", "fixture-result-list__fixture", "femenil", limit=2)

    return {
        "varonil": var_matches,
        "femenil": fem_matches,
        "total": len(var_matches) + len(fem_matches),
    }


@app.get("/next-fem")
def get_fem():
    """Próximos 2 partidos femeniles."""
    return get_next_matches(FEM_URL, "li", "fixture-result-list__fixture", "femenil", limit=2)


@app.get("/next-var")
def get_var():
    """Próximos 2 partidos varoniles."""
    return get_next_matches(VAR_URL, "a", "fixture-result-list__fixture-link", "varonil", limit=2)

@app.get("/rss/{category}")
def get_rss(category: str):
    try:
        url = f"https://carpetasfcb.com/rss/cat/{category}"

        scraper = cloudscraper.create_scraper()
        response = scraper.get(url, timeout=15)

        content = response.text

        # Detect Cloudflare block
        if "Just a moment" in content:
            return {"error": "Blocked by Cloudflare"}

        return Response(content=content, media_type="application/xml")

    except Exception as e:
        return {"error": str(e)}