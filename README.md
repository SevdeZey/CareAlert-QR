# QR-Based Feedback System

A lightweight, QR-driven feedback collection platform designed for rapid, location-based user feedback. Users scan a QR code placed on service points and instantly submit feedback through a simple web form. This repository contains a modular and scalable implementation showcasing the core workflow from QR scan → survey → submission.

## System Overview
\```mermaid
flowchart TD
    A[QR Code at Location] --> B[User Scans QR]
    B --> C[Survey Page Opens]
    C --> D[User Submits Feedback]
    D --> E[Flask Backend Receives Data]
    E --> F[(SQLite Database)]
    F --> G[Admin / Staff Views Feedback]
\```

## Project Structure
\```mermaid
mindmap
  root((Project Structure))
    Backend
      app.py
      db_init.py
      create_sample_data.py
      generate_qr.py
    Frontend
      templates/
      static/
    Database
      SQLite (data.db)
      Migration Scripts
    Environment
      .env
      venv/
\```

## Features
\```mermaid
graph LR
    A[QR Generation] --> B[Simplified Survey UI]
    B --> C[Location-Based Tracking]
    C --> D[SQLite Storage]
    D --> E[Admin/Staff View & Export Feedback]
\```

## Technologies
\```mermaid
graph TD
    A[Python] --> B[Flask]
    A --> C[SQLite]
    A --> D[qrcode Library]
    B --> E[Jinja2 Templates]
    E --> F[HTML/CSS/JS]
\```

## How It Works
\```mermaid
sequenceDiagram
    participant User
    participant QR as QR Code
    participant Browser
    participant Server as Flask Server
    participant DB as SQLite DB

    User->>QR: Scan QR Code
    QR-->>Browser: Open location-specific URL
    Browser->>Server: GET /survey
    Server-->>Browser: Render survey form
    User->>Browser: Submit feedback
    Browser->>Server: POST feedback
    Server->>DB: Insert record
    DB-->>Server: OK
    Server-->>Browser: Display Thank You Page
\```

## Roadmap
\```mermaid
timeline
    title Production Roadmap
    Q1 : SMS Integration : Admin Login : Role Management
    Q2 : Multi-Location Setup : QR Design Templates : Mass QR Export
    Q3 : Reporting Dashboard : Cloud Deployment
    Q4 : Security Hardening : Backup Strategy : Internal Optimization
\```

## Future Enhancements
- SMS notifications  
- Full admin dashboard with charts  
- Secure API for mobile app integration  
- Custom QR design generator  
- Multi-location analytics  
- Role-based access control  
- On-premise or cloud deployment options  
