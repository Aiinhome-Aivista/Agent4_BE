import sys
from database.db_connection import get_db_connection

conn = get_db_connection()
cursor = conn.cursor(dictionary=True)

try:
    cursor.execute("DESCRIBE incidents")
    print("INCIDENTS:")
    for row in cursor.fetchall():
        print(row)

    cursor.execute("DESCRIBE uploaded_documents")
    print("UPLOADED_DOCUMENTS:")
    for row in cursor.fetchall():
        print(row)
finally:
    conn.close()
