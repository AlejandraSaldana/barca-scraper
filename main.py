from fastapi import FastAPI
from bs4 import BeautifulSoup
import requests
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware
from zoneinfo import ZoneInfo

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


def get_next_matches(url: str, tag: str, class_name: str, category: str, limit: int = 2):
    """
    Scrape los próximos `limit` partidos de una URL del Barça.
    Devuelve lista de dicts con: category, datetime, home_team, away_team, competition, venue.
    """
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except Exception as e:
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    fixtures = soup.find_all(tag, class_=class_name)

    results = []
    now_ts = datetime.now(tz=MADRID_TZ).timestamp() * 1000  # milisegundos

    for fixture in fixtures:
        if len(results) >= limit:
            break

        # Fecha del partido
        date_div = fixture.find("div", class_="fixture-result-list__fixture-date")
        if not date_div or not date_div.get("data-fixture-date"):
            continue

        timestamp = int(date_div["data-fixture-date"])

        # Solo partidos futuros
        if timestamp < now_ts:
            continue

        match_dt = datetime.fromtimestamp(timestamp / 1000, tz=MADRID_TZ)

        # Equipos
        teams = fixture.find_all("span", class_="fixture-result-list__team-name")
        home_team = teams[0].get_text(strip=True) if len(teams) > 0 else "FC Barcelona"
        away_team = teams[1].get_text(strip=True) if len(teams) > 1 else "Rival"

        # Competición
        competition_tag = fixture.find("span", class_="fixture-result-list__competition-name")
        competition = competition_tag.get_text(strip=True) if competition_tag else "Competición"

        # Estadio
        venue_tag = fixture.find("span", class_="fixture-result-list__venue")
        venue = venue_tag.get_text(strip=True) if venue_tag else "Por confirmar"

        # ID único basado en timestamp + categoría
        fixture_id = f"{category}-{timestamp}"

        results.append({
            "fixture_id": fixture_id,
            "category": category,
            "datetime": match_dt.isoformat(),
            "home_team": home_team,
            "away_team": away_team,
            "competition": competition,
            "venue": venue,
        })

    return results


@app.get("/")
def root():
    return {"status": "Barca scraper API"}


@app.get("/next-game")
def get_next():
    """Próximo partido global (el más cercano entre varonil y femenil)."""
    var_matches = get_next_matches(VAR_URL, "a", "fixture-result-list__fixture-link", "varonil", limit=1)
    fem_matches = get_next_matches(FEM_URL, "li", "fixture-result-list__fixture", "femenil", limit=1)

    if not var_matches and not fem_matches:
        return {"error": "No se encontraron partidos"}

    candidates = var_matches + fem_matches
    next_match = min(candidates, key=lambda m: m["datetime"])
    return next_match


@app.get("/next-matches")
def get_next_matches_hub():
    """
    Devuelve los próximos 2 partidos varoniles y 2 femeniles.
    Usado por el WatchPartyHUB para mostrar opciones al crear sala.
    """
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