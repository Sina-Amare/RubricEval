#!/usr/bin/env python3
"""Check database status and contents."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from database import Session, Submission, Report

def check_database():
    """Check database status."""
    session = Session()
    try:
        # Count submissions by status
        print("=== SUBMISSIONS BY STATUS ===")
        from sqlalchemy import func
        status_counts = session.query(
            Submission.status, 
            func.count(Submission.id)
        ).group_by(Submission.status).all()
        
        for status, count in status_counts:
            print(f"{status}: {count}")
        
        # Total submissions
        total = session.query(Submission).count()
        print(f"\nTotal submissions: {total}")
        
        # Count reports
        report_count = session.query(Report).count()
        print(f"Total reports: {report_count}")
        
        # Recent submissions
        print("\n=== RECENT SUBMISSIONS (last 5) ===")
        recent = session.query(Submission).order_by(
            Submission.created_at.desc()
        ).limit(5).all()
        
        for sub in recent:
            print(f"ID: {sub.id}, URL: {sub.github_url}, Status: {sub.status}, Created: {sub.created_at}")
            
    finally:
        session.close()

if __name__ == "__main__":
    check_database()