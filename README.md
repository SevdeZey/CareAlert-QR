QR-Based Feedback System

This project provides a lightweight, QR-driven platform for collecting rapid, location-based user feedback. Users scan a QR code placed at service points and instantly access a simple web form where they can submit feedback. The system is modular, easy to deploy, and designed to work in internal networks or limited-access environments.

Overview

When a user scans a QR code, the system opens a URL tied to a specific location. The backend displays a survey page, receives the submitted data, and stores it in a SQLite database. Staff members can then review and export the collected feedback.

Key Features

QR code generation for each location

Clean and minimal survey interface

Location-based feedback tracking

SQLite storage for quick setup

Simple backend built with Flask

Easy to deploy on internal servers or private networks

Feedback export and review capabilities

Project Structure

Backend

app.py — main application

db_init.py — initial database setup

create_sample_data.py — sample dataset generator

generate_qr.py — QR code generator

Frontend

templates/ — HTML templates (Jinja2)

static/ — CSS, JS, and assets

Database

data.db (SQLite)

Migration scripts

Environment

.env for configuration

venv/ for dependencies

Technologies Used

Python + Flask for server-side logic

SQLite for lightweight, file-based storage

Jinja2 templates for rendering pages

HTML / CSS / JavaScript for UI

qrcode Python library for QR generation

How It Works (Flow)

QR code is generated for a specific location.

User scans the QR code using any mobile device.

Browser opens the location-specific survey page.

User fills out and submits the feedback form.

Flask backend processes the data and stores it in SQLite.

A confirmation/thank-you page is shown.

Staff can later review, filter, or export feedback.

Roadmap

Planned improvements include:

SMS or email notifications

Full admin dashboard with charts and filters

API endpoints for mobile app integration

Custom QR print templates

Multi-location analytics and heatmaps

Role-based access control

On-premise and cloud deployment options
