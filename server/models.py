from sqlalchemy import Column, Integer, String, JSON, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)
    username = Column(String, unique=True)
    password_hash = Column(String) # Store bcrypt hash here

class Match(Base):
    __tablename__ = "matches"
    id = Column(String, primary_key=True)
    status = Column(String) # ACTIVE, FINISHED
    current_tick = Column(Integer, default=0)
    state_snapshot = Column(JSON) # Full serialize of current board

    # Store orders for the *current* ticking phase
    pending_orders = Column(JSON)
