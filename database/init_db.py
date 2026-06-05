"""
Run this once to initialize the database schema.
Usage: python database/init_db.py
"""
import os
import bcrypt
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

def init_db():
    conn = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST"),
        port=int(os.getenv("MYSQL_PORT", 3306)),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
    )
    cursor = conn.cursor()

    db_name = os.getenv("MYSQL_NAME", "sla_db")
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
    cursor.execute(f"USE {db_name}")

    # ── Users ────────────────────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            name        VARCHAR(100) NOT NULL,
            email       VARCHAR(150) UNIQUE NOT NULL,
            password    VARCHAR(255) NOT NULL,
            role        ENUM('admin','engineer') NOT NULL DEFAULT 'engineer',
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── Connector configurations ──────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS connector_configs (
            id              INT AUTO_INCREMENT PRIMARY KEY,
            connector_type  ENUM('jira','servicenow') NOT NULL,
            base_url        VARCHAR(500) NOT NULL,
            username        VARCHAR(200) NOT NULL,
            api_token       TEXT NOT NULL,
            app_id          VARCHAR(100) NULL,
            is_active       TINYINT(1) DEFAULT 0,
            last_synced_at  DATETIME NULL,
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uq_connector_type (connector_type)
        )
    """)

    # ── Incidents ─────────────────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS incidents (
            id                  INT AUTO_INCREMENT PRIMARY KEY,
            source              ENUM('jira','servicenow') NOT NULL,
            ticket_id           VARCHAR(100) NOT NULL,
            title               VARCHAR(500),
            description         TEXT,
            priority            ENUM('critical','high','medium','low') DEFAULT 'medium',
            status              VARCHAR(100),
            assignee            VARCHAR(200),
            reporter            VARCHAR(200),
            created_at          DATETIME,
            updated_at          DATETIME,
            resolved_at         DATETIME NULL,
            sla_due_at          DATETIME NULL,
            reassignment_count  INT DEFAULT 0,
            raw_data            JSON,
            ingested_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uq_source_ticket (source, ticket_id)
        )
    """)

    # ── SLA Risk scores ───────────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sla_risk_scores (
            id                  INT AUTO_INCREMENT PRIMARY KEY,
            incident_id         INT NOT NULL,
            risk_score          FLOAT NOT NULL DEFAULT 0,
            risk_level          ENUM('LOW','MEDIUM','HIGH') DEFAULT 'LOW',
            breach_probability  FLOAT DEFAULT 0,
            reasons             JSON,
            recommended_actions JSON,
            calculated_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (incident_id) REFERENCES incidents(id) ON DELETE CASCADE
        )
    """)

    # ── Alert log ─────────────────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alert_log (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            incident_id INT NOT NULL,
            alert_type  VARCHAR(100),
            message     TEXT,
            sent_to     JSON,
            sent_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (incident_id) REFERENCES incidents(id) ON DELETE CASCADE
        )
    """)

    # ── Seed users ────────────────────────────────────────────────────────────
    def hash_pw(plain: str) -> str:
        return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()

    seed_users = [
        ("Alice Admin",    "alice@company.com",   hash_pw("Admin@123"),    "admin"),
        ("Bob Engineer",   "bob@company.com",     hash_pw("Engineer@123"), "engineer"),
        ("Carol Engineer", "carol@company.com",   hash_pw("Engineer@123"), "engineer"),
        ("Dave Engineer",  "dave@company.com",    hash_pw("Engineer@123"), "engineer"),
    ]

    for name, email, pw, role in seed_users:
        cursor.execute("""
            INSERT IGNORE INTO users (name, email, password, role)
            VALUES (%s, %s, %s, %s)
        """, (name, email, pw, role))

    conn.commit()
    cursor.close()
    conn.close()
    print("✅  Database initialized successfully.")
    print("   Admin  → alice@company.com  / Admin@123")
    print("   Engineers → bob/carol/dave@company.com / Engineer@123")

if __name__ == "__main__":
    init_db()
