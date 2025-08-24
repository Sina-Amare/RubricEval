"""Database models and operations for CV Review Bot."""

import os
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime, timezone
import json
from config import DATABASE_PATH

# Ensure database directory exists
os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)

# Create database engine
Base = declarative_base()
engine = create_engine(f'sqlite:///{DATABASE_PATH}', echo=False)
Session = sessionmaker(bind=engine)

class Submission(Base):
    """Model for candidate submissions."""
    __tablename__ = 'submissions'
    
    id = Column(Integer, primary_key=True)
    telegram_user_id = Column(String, nullable=False, index=True)
    telegram_username = Column(String)
    github_url = Column(String, nullable=False)
    role = Column(String, nullable=False)  # 'backend' or 'frontend'
    status = Column(String, default='pending', index=True)  # pending, analyzing, completed, failed
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    completed_at = Column(DateTime)
    error_message = Column(Text)  # Store error if analysis fails
    
    # Relationship with reports
    report = relationship("Report", back_populates="submission", uselist=False)
    
    def to_dict(self):
        """Convert submission to dictionary."""
        return {
            'id': self.id,
            'telegram_user_id': self.telegram_user_id,
            'telegram_username': self.telegram_username,
            'github_url': self.github_url,
            'role': self.role,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'error_message': self.error_message
        }

class Report(Base):
    """Model for analysis reports."""
    __tablename__ = 'reports'
    
    id = Column(Integer, primary_key=True)
    submission_id = Column(Integer, ForeignKey('submissions.id'), nullable=False, unique=True)
    analysis_result = Column(Text)  # JSON string with full analysis
    recommendation = Column(String, index=True)  # ACCEPT or REJECT
    confidence = Column(Float)
    completeness_score = Column(Float)
    quality_score = Column(Float)
    architecture_score = Column(Float)
    testing_score = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship with submission
    submission = relationship("Submission", back_populates="report")
    
    def get_analysis(self):
        """Parse and return analysis result as dictionary."""
        if self.analysis_result:
            try:
                return json.loads(self.analysis_result)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_analysis(self, analysis_dict):
        """Set analysis result from dictionary."""
        self.analysis_result = json.dumps(analysis_dict)
    
    def to_dict(self):
        """Convert report to dictionary."""
        return {
            'id': self.id,
            'submission_id': self.submission_id,
            'recommendation': self.recommendation,
            'confidence': self.confidence,
            'completeness_score': self.completeness_score,
            'quality_score': self.quality_score,
            'architecture_score': self.architecture_score,
            'testing_score': self.testing_score,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'analysis': self.get_analysis()
        }

# Database helper functions
def init_database():
    """Initialize database tables."""
    Base.metadata.create_all(engine)

def get_session():
    """Get a new database session."""
    return Session()

def create_submission(telegram_user_id: str, telegram_username: str, 
                     github_url: str, role: str) -> Submission:
    """Create a new submission."""
    session = get_session()
    try:
        submission = Submission(
            telegram_user_id=telegram_user_id,
            telegram_username=telegram_username,
            github_url=github_url,
            role=role,
            status='pending'
        )
        session.add(submission)
        session.commit()
        session.refresh(submission)
        return submission
    finally:
        session.close()

def update_submission_status(submission_id: int, status: str, 
                            error_message: str = None) -> bool:
    """Update submission status."""
    session = get_session()
    try:
        submission = session.query(Submission).get(submission_id)
        if submission:
            submission.status = status
            if status == 'completed':
                submission.completed_at = datetime.now(timezone.utc)
            if error_message:
                submission.error_message = error_message
            session.commit()
            return True
        return False
    finally:
        session.close()

def create_report(submission_id: int, analysis_result: dict, 
                 recommendation: str, confidence: float,
                 scores: dict) -> Report:
    """Create an analysis report."""
    session = get_session()
    try:
        report = Report(
            submission_id=submission_id,
            recommendation=recommendation,
            confidence=confidence,
            completeness_score=scores.get('completeness', 0),
            quality_score=scores.get('quality', 0),
            architecture_score=scores.get('architecture', 0),
            testing_score=scores.get('testing', 0)
        )
        report.set_analysis(analysis_result)
        session.add(report)
        session.commit()
        session.refresh(report)
        return report
    finally:
        session.close()

def get_submission(submission_id: int) -> Submission:
    """Get submission by ID."""
    session = get_session()
    try:
        return session.query(Submission).get(submission_id)
    finally:
        session.close()

def get_recent_reports(limit: int = 10) -> list:
    """Get recent reports with submissions."""
    session = get_session()
    try:
        reports = session.query(Report).join(Submission).order_by(
            Report.created_at.desc()
        ).limit(limit).all()
        return [(report, report.submission) for report in reports]
    finally:
        session.close()

def get_pending_submissions() -> list:
    """Get all pending or analyzing submissions."""
    session = get_session()
    try:
        return session.query(Submission).filter(
            Submission.status.in_(['pending', 'analyzing'])
        ).all()
    finally:
        session.close()

def get_user_submissions(telegram_user_id: str) -> list:
    """Get all submissions by a user."""
    session = get_session()
    try:
        return session.query(Submission).filter(
            Submission.telegram_user_id == telegram_user_id
        ).order_by(Submission.created_at.desc()).all()
    finally:
        session.close()

# Initialize database on module import
init_database()