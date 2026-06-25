"""SQLAlchemy database models for ScopePilot."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    users = relationship("User", back_populates="workspace")
    projects = relationship("Project", back_populates="workspace")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), default="member")  # admin, member
    created_at = Column(DateTime, default=datetime.utcnow)

    workspace = relationship("Workspace", back_populates="users")


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    name = Column(String(255), nullable=False)
    jira_url = Column(String(500), nullable=False)
    jira_email = Column(String(255), nullable=False)
    jira_api_token = Column(String(500), nullable=False)
    jira_project_key = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    workspace = relationship("Workspace", back_populates="projects")
    sprints = relationship("Sprint", back_populates="project")


class Sprint(Base):
    __tablename__ = "sprints"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    jira_sprint_id = Column(Integer, nullable=False)
    name = Column(String(255), nullable=False)
    state = Column(String(50), default="active")  # active, closed, future
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    imported_at = Column(DateTime, default=datetime.utcnow)
    total_tickets = Column(Integer, default=0)
    analysis_status = Column(String(50), default="pending")  # pending, running, done, failed
    analysis_data = Column(JSON, nullable=True)  # SprintAnalysis.to_dict()

    project = relationship("Project", back_populates="sprints")
    tickets = relationship("Ticket", back_populates="sprint")


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True)
    sprint_id = Column(Integer, ForeignKey("sprints.id"), nullable=False)
    key = Column(String(50), nullable=False)  # e.g. LP-2139
    summary = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    issue_type = Column(String(50), nullable=True)
    status = Column(String(50), nullable=True)
    priority = Column(String(50), nullable=True)
    assignee = Column(String(255), nullable=True)
    labels = Column(JSON, nullable=True)
    story_points = Column(Integer, nullable=True)
    acceptance_criteria = Column(JSON, nullable=True)
    comments = Column(JSON, nullable=True)
    analysis_data = Column(JSON, nullable=True)  # TicketAnalysis.to_dict()
    created_at = Column(DateTime, default=datetime.utcnow)

    sprint = relationship("Sprint", back_populates="tickets")
