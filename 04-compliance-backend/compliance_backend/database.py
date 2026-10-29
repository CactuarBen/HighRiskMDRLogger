from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# sqlite:///audit.db creates a file audit.db
# check_same_thread=False is required for SQLite with FastAPI
engine = create_engine(
    "sqlite:///audit.db",
    connect_args={"check_same_thread": False},
)

# a session is one conversation with the database
SessionLocal = sessionmaker(bind=engine)

# Base is the parent class the table classes inherit from
Base = declarative_base()

# get_db() hands each API request its own session and closes it afterwards
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()