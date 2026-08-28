import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from sqlalchemy.orm import Session
from database.models import Prefecture
from database.engine import SessionLocal

def seed():
    session = SessionLocal()
    try:
        prefectures = session.query(Prefecture).all()
        print(f"Done. Total: {len(prefectures)}")
        for p in prefectures:
            print(f"  {p.code}: {p.name}")
    finally:
        session.close()

if __name__ == "__main__":
    seed()