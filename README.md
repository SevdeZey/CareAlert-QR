# QR-Based Hospital Feedback System

A lightweight, QR-driven feedback collection system for hospitals.  
Patients scan a QR code placed on doors or service points and instantly submit feedback through a simple web form.  
This repository contains a modular and scalable implementation showcasing the core workflow from QR scan → survey → submission.

---

## 📌 System Overview

```mermaid
flowchart TD
    A[QR Code on Door] --> B[Patient Scans QR]
    B --> C[Survey Page Opens]
    C --> D[User Submits Feedback]
    D --> E[Flask Backend Receives Data]
    E --> F[(SQLite Database)]
    F --> G[Admin / Staff Views Feedback]

# Project Structure
mindmap
  root((Project Structure))
    App
      app.py
      db_init.py
      create_sample_data.py
      generate_qr.py
    Frontend
      templates/
      static/
    Database
      SQLite data.db
      Migration Scripts
    Environment
      .env
      venv/

# Features
graph LR
    A[QR Generation] --> B[Simplified Survey UI]
    B --> C[Location-Based Tracking]
    C --> D[SQLite Storage]
    D --> E[Admin/Staff Resolve Actions]

# Technologies Used
graph TD
    A[Python] --> B[Flask]
    A --> C[SQLite]
    A --> D[qrcode Py Library]
    B --> E[Jinja2 Templates]
    E --> F[HTML/CSS/JS]

# How It Works
sequenceDiagram
    participant User
    participant QR as QR Code
    participant Browser
    participant Server as Flask Server
    participant DB as SQLite DB

    User->>QR: Scan QR Code
    QR-->>Browser: Open location-specific URL
    Browser->>Server: GET survey page
    Server-->>Browser: Render HTML form
    User->>Browser: Submits feedback
    Browser->>Server: POST feedback data
    Server->>DB: Insert record
    DB-->>Server: OK
    Server-->>Browser: Thank you page

# Road Map
timeline
    title Production Roadmap
    Q1 : SMS Integration : Admin Login : Role Management
    Q2 : 2000+ Location Setup : QR Design Templates : Mass QR Export
    Q3 : Advanced Reporting Dashboard : Cloud / On-Prem Deployment
    Q4 : Internal Network Optimization : Security Hardening : Backup Strategy

# Future Enhancements

SMS notifications

Full admin dashboard

Secure API for mobile app integration

Custom QR print designs

Hospital network deployment

Multi-location analytics

Role-based user system

