from fastapi import FastAPI
from bs4 import BeautifulSoup
import requests
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173",
                   "http://localhost:5174"],
    allow_methods=["GET"],
)

VAR_URL  = "https://www.fcbarcelona.es/es/futbol/primer-equipo/calendario"
FEM_URL = "https://www.fcbarcelona.es/es/futbol/femenino/calendario"

# funcion para buscar un contenedor en un url
# regresa datetime del partido
def get_next_match_date(url, tag, class_name):
    soup = BeautifulSoup(requests.get(url).text, "html.parser")
    match = soup.find(tag, class_= class_name)
    if not match:
        return None
    timestamp = int(match.find("div", class_="fixture-result-list__fixture-date")["data-fixture-date"])
    return datetime.fromtimestamp(timestamp / 1000)

@app.get("/")
def root():
    return "API scraper"

@app.get("/next-game")
def get_next():
    var   = get_next_match_date(VAR_URL,   "a",  "fixture-result-list__fixture-link")
    fem = get_next_match_date(FEM_URL, "li", "fixture-result-list__fixture")

    if not var and not fem:
        return {"error": "No se encontraron partidos"}
    
    if not var:
        category, date = "fem", fem
    
    elif not fem:
        category, date = "var", var

    else: 
        category, date = ("fem", fem) if fem < var else ("var", var)
    
    return {"category": category, "datetime": date.isoformat()}





    