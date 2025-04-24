from app import app, db
import os

def reset_database():
    with app.app_context():
        try:
            print("Dropping all tables...")
            db.drop_all()
            print("Creating all tables...")
            db.create_all()
            db.session.commit()
            print("Database reset complete!")
            print("All tables have been dropped and recreated.")
            print("You can now start with a fresh database.")
        except Exception as e:
            print(f"Error resetting database: {str(e)}")
            print("\nTrying alternative method...")
            try:
                # For PostgreSQL, we need to close all connections first
                db.session.close()
                db.engine.dispose()
                
                # Drop and recreate all tables using raw SQL
                with db.engine.connect() as conn:
                    conn.execute(db.text("DROP TABLE IF EXISTS user CASCADE"))
                    conn.execute(db.text("DROP TABLE IF EXISTS order CASCADE"))
                    db.create_all()
                    conn.commit()
                print("Database reset complete using alternative method!")
            except Exception as e2:
                print(f"Error with alternative method: {str(e2)}")
                print("\nPlease ensure you have the correct database permissions and try again.")

if __name__ == "__main__":
    confirm = input("This will DELETE ALL DATA in the database. Are you sure? (yes/no): ")
    if confirm.lower() == "yes":
        reset_database()
    else:
        print("Operation cancelled.") 