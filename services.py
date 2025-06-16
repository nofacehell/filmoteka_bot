import os
import random
import aiohttp
from models import Film
from database import SessionLocal
from sqlalchemy import select

KINOPOISK_API_TOKEN = os.getenv("KINOPOISK_API_TOKEN") or "ACTXDM9-R3M4XBF-NDSC4BB-BPMF9BN"
KINOPOISK_API_URL = "https://api.kinopoisk.dev/v1.4/movie/search"

async def search_films_kinopoisk(title: str, limit: int = 5):
    headers = {
        "X-API-KEY": KINOPOISK_API_TOKEN
    }
    params = {"query": title, "limit": limit}
    async with aiohttp.ClientSession() as session:
        async with session.get(KINOPOISK_API_URL, headers=headers, params=params) as resp:
            data = await resp.json()
            films = data.get("docs", [])
            result = []
            for film in films:
                result.append({
                    "kinopoiskId": film.get("id"),
                    "title": film.get("name"),
                    "year": film.get("year"),
                    "genre": film.get("genres", [{}])[0].get("name"),
                    "description": film.get("description"),
                    "trailer_url": film.get("videos", {}).get("trailers", [{}])[0].get("url"),
                    "poster_url": film.get("poster", {}).get("url"),
                    "watch_url": film.get("watchability", {}).get("items", [{}])[0].get("url")
                })
            return result

async def add_film_from_kinopoisk(film_data: dict):
    async with SessionLocal() as session:
        session.add(Film(
            title=film_data["title"],
            year=film_data.get("year"),
            genre=film_data.get("genre"),
            description=film_data.get("description"),
            trailer_url=film_data.get("trailer_url")
        ))
        await session.commit()

async def get_random_film():
    async with SessionLocal() as session:
        result = await session.execute(select(Film))
        films = result.scalars().all()
        return random.choice(films) if films else None

async def get_all_films():
    async with SessionLocal() as session:
        result = await session.execute(select(Film))
        return result.scalars().all() 