from app import db, User, Order
from sqlalchemy import text
import os

def migrate():
    # Add site column to User table if it doesn't exist
    with db.engine.connect() as conn:
        # Check if we're using PostgreSQL
        is_postgres = 'postgresql' in str(db.engine.url)
        
        if is_postgres:
            # PostgreSQL syntax
            # First check if the user table exists
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'user'
                )
            """))
            if not result.scalar():
                print("User table does not exist yet, skipping migration")
                return
                
            # Check if site column exists in User table
            result = conn.execute(text("""
                SELECT COUNT(*) 
                FROM information_schema.columns 
                WHERE table_name = 'user' 
                AND column_name = 'site'
            """))
            if result.scalar() == 0:
                conn.execute(text('ALTER TABLE "user" ADD COLUMN site VARCHAR(100)'))
                print("Added site column to User table")
                conn.commit()
            
            # Check if order table exists
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'order'
                )
            """))
            if not result.scalar():
                print("Order table does not exist yet, skipping migration")
                return
                
            # Check if site column exists in Order table
            result = conn.execute(text("""
                SELECT COUNT(*) 
                FROM information_schema.columns 
                WHERE table_name = 'order' 
                AND column_name = 'site'
            """))
            if result.scalar() == 0:
                conn.execute(text('ALTER TABLE "order" ADD COLUMN site VARCHAR(100)'))
                print("Added site column to Order table")
                conn.commit()
            
            # Update existing records
            conn.execute(text("""
                UPDATE "user" 
                SET site = 'TWT Alberton' 
                WHERE site IS NULL
            """))
            print("Updated existing User records with default site")
            conn.commit()
            
            conn.execute(text("""
                UPDATE "order" o
                SET site = (
                    SELECT u.site 
                    FROM "user" u 
                    WHERE u.username = o.submitter
                )
                WHERE o.site IS NULL
            """))
            conn.commit()
        else:
            # SQLite syntax
            # First check if the user table exists
            result = conn.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='user'
            """))
            if not result.scalar():
                print("User table does not exist yet, skipping migration")
                return
                
            # Check if site column exists in User table
            result = conn.execute(text("""
                SELECT COUNT(*) 
                FROM pragma_table_info('user') 
                WHERE name='site'
            """))
            if result.scalar() == 0:
                conn.execute(text("ALTER TABLE user ADD COLUMN site VARCHAR(100)"))
                print("Added site column to User table")
                conn.commit()
            
            # Check if order table exists
            result = conn.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='order'
            """))
            if not result.scalar():
                print("Order table does not exist yet, skipping migration")
                return
                
            # Check if site column exists in Order table
            result = conn.execute(text("""
                SELECT COUNT(*) 
                FROM pragma_table_info('order') 
                WHERE name='site'
            """))
            if result.scalar() == 0:
                conn.execute(text("ALTER TABLE order ADD COLUMN site VARCHAR(100)"))
                print("Added site column to Order table")
                conn.commit()
            
            # Update existing records
            conn.execute(text("""
                UPDATE user 
                SET site = 'TWT Alberton' 
                WHERE site IS NULL
            """))
            print("Updated existing User records with default site")
            conn.commit()
            
            conn.execute(text("""
                UPDATE "order" o
                SET site = (
                    SELECT u.site 
                    FROM user u 
                    WHERE u.username = o.submitter
                )
                WHERE o.site IS NULL
            """))
            conn.commit()
        
        print("Updated existing Order records with site from submitter")
        print("Migration completed successfully")

if __name__ == "__main__":
    migrate() 