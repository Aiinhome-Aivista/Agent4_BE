import os
from database.db_connection import get_db_connection

def main():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Let's fetch the most recent incidents and join with scores and AI analysis
    cursor.execute("""
        SELECT 
            i.id, i.ticket_id, i.title, i.status, i.source, i.created_at,
            s.risk_score, s.risk_level,
            ai.summary, ai.solution, ai.risk_score AS ai_risk_score
        FROM incidents i
        LEFT JOIN sla_risk_scores s ON s.incident_id = i.id
        LEFT JOIN incident_ai_analysis ai ON ai.incident_id = i.id
        ORDER BY i.created_at DESC
        LIMIT 10
    """)
    rows = cursor.fetchall()
    print("--- INCIDENTS IN DB ---")
    for r in rows:
        print(f"ID: {r['id']}, Key: {r['ticket_id']}, Title: {r['title']}")
        print(f"  Status: {r['status']}, Source: {r['source']}, Created: {r['created_at']}")
        print(f"  Risk Level (s.risk_level): {r['risk_level']}, Risk Score (s.risk_score): {r['risk_score']}")
        print(f"  AI Summary: {r['summary']}, AI Risk Score (ai.risk_score): {r['ai_risk_score']}")
        print("-" * 50)
        
    cursor.close()
    conn.close()

if __name__ == "__main__":
    main()
