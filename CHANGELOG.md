# Changelog

All notable changes to the TalentFlow ATS project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-01-15

### Added

#### Authentication & Session Management
- User authentication with secure session cookies
- Login and logout functionality with session persistence
- Password hashing using bcrypt for secure credential storage
- Session expiration and automatic cleanup

#### Role-Based Access Control (RBAC)
- Four distinct user roles with granular permissions:
  - **Admin** — Full system access including user management, configuration, and audit log review
  - **Hiring Manager** — Job requisition creation and management, candidate evaluation, and hiring decisions
  - **Recruiter** — Candidate sourcing, application processing, interview coordination, and pipeline management
  - **Interviewer** — Interview participation, feedback submission, and candidate scoring

#### Job Requisition Management
- Create, edit, and close job requisitions with detailed descriptions
- Track requisition status through lifecycle stages (Draft, Open, On Hold, Closed, Cancelled)
- Assign hiring managers and recruiters to requisitions
- Department and location categorization for job postings

#### Candidate Database with Skill Tags
- Centralized candidate profiles with contact information and resume tracking
- Skill tagging system for candidate categorization and searchability
- Many-to-many relationship between candidates and skills for flexible tagging
- Candidate search and filtering by skills, experience, and status

#### Application Pipeline with Kanban View
- Visual kanban board for tracking applications across pipeline stages
- Configurable pipeline stages (Applied, Screening, Interview, Offer, Hired, Rejected)
- Drag-and-drop style stage transitions with status tracking
- Application history and stage progression timeline

#### Interview Scheduling and Feedback
- Schedule interviews with date, time, and location details
- Assign interviewers to interview sessions
- Structured feedback submission with rating scores
- Interview status tracking (Scheduled, Completed, Cancelled, No Show)
- Consolidated feedback view for hiring decision support

#### Role-Specific Dashboards
- **Admin Dashboard** — System overview with user statistics, recent activity, and audit log summary
- **Hiring Manager Dashboard** — Open requisitions, pending decisions, and candidate pipeline overview
- **Recruiter Dashboard** — Active applications, upcoming interviews, and sourcing metrics
- **Interviewer Dashboard** — Assigned interviews, pending feedback submissions, and schedule view

#### Audit Trail
- Comprehensive audit logging for all system actions
- Tracks user identity, action type, target entity, and timestamp
- Filterable audit log view for compliance and accountability
- Immutable log entries for data integrity