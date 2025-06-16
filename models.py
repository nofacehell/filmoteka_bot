from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from database import Base

class Film(Base):
    __tablename__ = "films"
    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    year = Column(Integer)
    genre = Column(String)
    description = Column(String)
    trailer_url = Column(String)
    watched = Column(Boolean, default=False)

class UserFilm(Base):
    __tablename__ = "user_films"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    film_id = Column(Integer, ForeignKey("films.id")) 