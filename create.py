from connections import Base, engine, db_session
from models import User

# ==========================================
# CREATE DATABASE TABLES
# ==========================================

Base.metadata.create_all(engine)

# ==========================================
# CREATE DEFAULT ADMIN
# ==========================================

admin = db_session.query(User).filter_by(
    email="admin@gmail.com"
).first()

if admin is None:

    admin = User(
        fullname="System Administrator",
        phone="0700000000",
        email="admin@gmail.com",
        password="admin",
        role="admin",
        status="Active"
    )

    db_session.add(admin)
    db_session.commit()

    print("✓ Default administrator created.")

else:

    print("✓ Default administrator already exists.")

print("✓ Database tables created successfully.")