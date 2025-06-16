import os
import random
import aiohttp
import asyncio
from models import Film
from database import SessionLocal
from sqlalchemy import select

KINOPOISK_API_TOKEN = os.getenv("KINOPOISK_API_TOKEN") or "ACTXDM9-R3M4XBF-NDSC4BB-BPMF9BN"
KINOPOISK_API_URL = "https://api.kinopoisk.dev/v1.4/movie/search"
KINOPOISK_API_MOVIE = "https://api.kinopoisk.dev/v1.4/movie/"

async def search_films_kinopoisk(title: str, limit: int = 5):
    headers = {"X-API-KEY": KINOPOISK_API_TOKEN}
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

async def get_film_details_kinopoisk(film_id: str):
    headers = {"X-API-KEY": KINOPOISK_API_TOKEN}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{KINOPOISK_API_MOVIE}{film_id}", headers=headers, timeout=10) as resp:
                if resp.status != 200:
                    print(f"Kinopoisk API error: status {resp.status}")
                    return None
                film = await resp.json()
                return {
                    "kinopoiskId": film.get("id"),
                    "title": film.get("name"),
                    "year": film.get("year"),
                    "genre": ", ".join([g.get("name") for g in film.get("genres", [])]),
                    "description": film.get("description"),
                    "trailer_url": film.get("videos", {}).get("trailers", [{}])[0].get("url"),
                    "poster_url": film.get("poster", {}).get("url"),
                    "watch_url": film.get("watchability", {}).get("items", [{}])[0].get("url"),
                    "director": ", ".join([p.get("name") for p in film.get("persons", []) if p.get("profession") == "режиссеры"]),
                    "actors": ", ".join([p.get("name") for p in film.get("persons", []) if p.get("profession") == "актеры"][:5]),
                    "country": ", ".join([c.get("name") for c in film.get("countries", [])]),
                    "rating": film.get("rating", {}).get("kp"),
                    "watched": False
                }
    except asyncio.TimeoutError:
        print("Timeout while fetching film details")
        return None
    except Exception as e:
        print(f"Error fetching film details: {e}")
        return None

async def add_film_from_kinopoisk(film_data: dict):
    async with SessionLocal() as session:
        session.add(Film(
            title=film_data["title"],
            year=film_data.get("year"),
            genre=film_data.get("genre"),
            description=film_data.get("description"),
            trailer_url=film_data.get("trailer_url"),
            poster_url=film_data.get("poster_url"),
            watch_url=film_data.get("watch_url"),
            director=film_data.get("director"),
            actors=film_data.get("actors"),
            country=film_data.get("country"),
            rating=film_data.get("rating"),
            watched=film_data.get("watched", False)
        ))
        await session.commit()

async def mark_film_watched(film_id: int):
    async with SessionLocal() as session:
        film = await session.get(Film, film_id)
        if film:
            film.watched = True
            await session.commit()

async def delete_film(film_id: int):
    async with SessionLocal() as session:
        film = await session.get(Film, film_id)
        if film:
            await session.delete(film)
            await session.commit()

async def get_watched_films():
    async with SessionLocal() as session:
        result = await session.execute(select(Film).where(Film.watched == True))
        return result.scalars().all()

async def get_random_film():
    async with SessionLocal() as session:
        result = await session.execute(select(Film))
        films = result.scalars().all()
        return random.choice(films) if films else None

async def get_all_films():
    async with SessionLocal() as session:
        result = await session.execute(select(Film))
        return result.scalars().all() 