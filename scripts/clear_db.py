#!/usr/bin/env python3
"""Clear database - remove all data or failed submissions."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from database import Session, Submission, Report, Base, engine

def clear_failed_submissions():
    """Clear only failed/analyzing submissions."""
    session = Session()
    try:
        # Delete failed and stuck analyzing submissions
        failed = session.query(Submission).filter(
            Submission.status.in_(['failed', 'analyzing', 'pending'])
        ).all()
        
        count = len(failed)
        
        for sub in failed:
            # Delete related reports first
            session.query(Report).filter_by(submission_id=sub.id).delete()
            # Delete submission
            session.delete(sub)
        
        session.commit()
        print(f"Deleted {count} failed/stuck submissions")
        
        # Show remaining
        remaining = session.query(Submission).count()
        print(f"Remaining submissions: {remaining}")
        
    finally:
        session.close()

def clear_all_data():
    """Clear ALL data from database."""
    response = input("WARNING: This will delete ALL data. Are you sure? (yes/no): ")
    if response.lower() != 'yes':
        print("Cancelled")
        return
        
    session = Session()
    try:
        # Delete all reports
        report_count = session.query(Report).delete()
        # Delete all submissions
        submission_count = session.query(Submission).delete()
        
        session.commit()
        print(f"Deleted {submission_count} submissions and {report_count} reports")
        
    finally:
        session.close()

def reset_database():
    """Drop and recreate all tables."""
    response = input("WARNING: This will DELETE EVERYTHING and recreate tables. Are you sure? (yes/no): ")
    if response.lower() != 'yes':
        print("Cancelled")
        return
        
    # Drop all tables
    Base.metadata.drop_all(bind=engine)
    print("All tables dropped")
    
    # Recreate tables
    Base.metadata.create_all(bind=engine)
    print("Tables recreated")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Database cleanup utility')
    parser.add_argument('--failed', action='store_true', help='Clear only failed/stuck submissions')
    parser.add_argument('--all', action='store_true', help='Clear all data')
    parser.add_argument('--reset', action='store_true', help='Drop and recreate tables')
    
    args = parser.parse_args()
    
    if args.failed:
        clear_failed_submissions()
    elif args.all:
        clear_all_data()
    elif args.reset:
        reset_database()
    else:
        print("Usage:")
        print("  python clear_db.py --failed  # Clear failed/stuck submissions")
        print("  python clear_db.py --all     # Clear all data")
        print("  python clear_db.py --reset   # Drop and recreate tables")