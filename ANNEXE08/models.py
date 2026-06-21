from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime

Base = declarative_base()

class UploadedFile(Base):
    __tablename__ = 'uploaded_files'
    id = Column(Integer, primary_key=True)
    original_name = Column(String)
    stored_path = Column(String)
    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow)

class ExtractedRecord(Base):
    __tablename__ = 'extracted_records'
    id = Column(Integer, primary_key=True)
    file_id = Column(Integer)
    # Candidate fields
    nom = Column(String)
    prenom = Column(String)
    date_naissance = Column(String)
    nature_date = Column(String)
    nature = Column(String)
    lieu_naissance = Column(String)
    nom_pere = Column(String)
    prenom_pere = Column(String)
    nom_mere = Column(String)
    prenom_mere = Column(String)
    sexe = Column(String)
    situation_familiale = Column(String)
    # Spouse
    spouse_nom = Column(String)
    spouse_prenom = Column(String)
    spouse_date_naissance = Column(String)
    spouse_lieu_naissance = Column(String)
    spouse_nom_pere = Column(String)
    spouse_prenom_mere = Column(String)

    raw_text = Column(Text)
    processed_at = Column(DateTime, default=datetime.datetime.utcnow)

class ExportedFile(Base):
    __tablename__ = 'exported_files'
    id = Column(Integer, primary_key=True)
    path = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


def get_engine(db_path='sqlite:///annexe08.db'):
    return create_engine(db_path, connect_args={"check_same_thread": False})

engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

if __name__ == '__main__':
    init_db()
