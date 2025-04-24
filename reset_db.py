from app import app, db
import os
import sys

def reset_database():
    with app.app_context():
        try:
            # Get the database URL to determine which database we're using
            db_url = app.config["SQLALCHEMY_DATABASE_URI"]
            print(f"Resetting database: {db_url}")
            
            # Close any existing connections
            db.session.close()
            db.engine.dispose()
            
            # Drop all tables
            print("Dropping all tables...")
            db.drop_all()
            
            # Create all tables
            print("Creating all tables...")
            db.create_all()
            
            # Commit the changes
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
                    # Drop tables with CASCADE to handle dependencies
                    conn.execute(db.text("DROP TABLE IF EXISTS \"user\" CASCADE"))
                    conn.execute(db.text("DROP TABLE IF EXISTS \"order\" CASCADE"))
                    conn.commit()
                    
                    # Recreate tables
                    db.create_all()
                    conn.commit()
                    
                print("Database reset complete using alternative method!")
            except Exception as e2:
                print(f"Error with alternative method: {str(e2)}")
                print("\nPlease ensure you have the correct database permissions and try again.")

if __name__ == "__main__":
    # Check if we're running in production
    is_production = os.getenv("RENDER") is not None
    
    if is_production:
        print("WARNING: You are about to reset the PRODUCTION database!")
        print("This will DELETE ALL DATA including users and orders.")
        print("This action cannot be undone.")
        print("Proceeding with reset in production environment...")
    else:
        confirm = input("This will DELETE ALL DATA in the database. Are you sure? (yes/no): ")
        if confirm.lower() != "yes":
            print("Operation cancelled.")
            sys.exit(0)
    
    reset_database() 