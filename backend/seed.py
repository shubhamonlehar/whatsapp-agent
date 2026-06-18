from app.db import Base, SessionLocal, engine
from app.seed_data import seed_if_empty


def main() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_if_empty(db)
    print("Seed data is ready.")


if __name__ == "__main__":
    main()
