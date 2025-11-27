from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.orm import declarative_base

Base = declarative_base()

# Local mirror of the game state
class LocalUnit(Base):
    __tablename__ = "units"
    id = Column(String, primary_key=True)
    type = Column(String)
    q = Column(Integer)
    r = Column(Integer)
    hp = Column(Float)

# Initialize SQLite in memory or file
engine = create_engine('sqlite:///game_cache.db')
