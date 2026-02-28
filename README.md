# Teammate Matcher (Flask + SQLite)

A small demo web app for matching first-year students to data-driven campus project ideas.

Built with **Flask**, **SQLite**, and **Tailwind CSS (CDN)**.

## Setup

1. **Create and activate a virtual environment (optional but recommended)**

   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```

2. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Run the app**

   ```bash
   python app.py
   ```

   The app will start on **http://127.0.0.1:5000**.

4. **First run**

   On the first request, the app will:

   - Create a local `teammate_matcher.db` SQLite database.
   - Create `students` and `projects` tables (if they do not exist).
   - Insert realistic demo data for first-year students and project ideas.

## Pages

- `/` – Home page listing demo project ideas and a sidebar with sample first-year profiles.
- `/profiles` – Full list of student profiles (skills like **Python**, **pandas**, **Molecular Biology**, etc.).

