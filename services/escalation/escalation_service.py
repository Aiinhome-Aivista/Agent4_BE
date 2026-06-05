from datetime import datetime

from database.db_connection import get_db_connection

from services.notifications.email_service import EmailService


class EscalationService:

    @staticmethod
    def run_escalation_process():

        connection = None
        cursor = None

        try:

            # =====================================
            # DATABASE CONNECTION
            # =====================================

            connection = get_db_connection()

            cursor = connection.cursor(
                dictionary=True
            )

            # =====================================
            # FETCH CONFIGURATION
            # =====================================

            cursor.execute(
                """
                SELECT *
                FROM escalation_configs
                WHERE is_active = TRUE
                LIMIT 1
                """
            )

            config = cursor.fetchone()

            if not config:
                print("No escalation config found")
                return

            risk_threshold = config["risk_threshold"]

            escalation_interval = config[
                "escalation_interval_minutes"
            ]

            # =====================================
            # FETCH HIGH RISK INCIDENTS
            # =====================================

            from datetime import timedelta

            current_time = datetime.now()
            threshold_time = current_time + timedelta(minutes=60)

            cursor.execute(
                """
                SELECT
                    incidents.*,
                    incident_ai_analysis.risk_score

                FROM incidents

                INNER JOIN incident_ai_analysis
                    ON incidents.id =
                       incident_ai_analysis.incident_id

                WHERE incident_ai_analysis.risk_score >= %s
                AND incidents.status != 'Done'
                AND (
                    incidents.sla_due_at IS NULL
                    OR incidents.sla_due_at <= %s
                )
                """,
                (risk_threshold, threshold_time)
            )

            incidents = cursor.fetchall()

            if not incidents:
                print("No high risk incidents found")
                return

            # =====================================
            # FETCH ENGINEERS
            # =====================================

            cursor.execute(
                """
                SELECT *
                FROM users
                WHERE role = 'engineer'
                ORDER BY id ASC
                """
            )

            engineers = cursor.fetchall()

            if not engineers:
                print("No engineers found")
                return

            # =====================================
            # PROCESS INCIDENTS
            # =====================================

            for incident in incidents:

                incident_id = incident["id"]

                incident_status = incident["status"]

                risk_score = incident["risk_score"]

                # =====================================
                # SKIP IF DONE
                # =====================================

                if incident_status == "Done":
                    continue

                # =====================================
                # FETCH LAST ESCALATION
                # =====================================

                cursor.execute(
                    """
                    SELECT *
                    FROM incident_escalations
                    WHERE incident_id = %s
                    ORDER BY escalation_level DESC
                    LIMIT 1
                    """,
                    (incident_id,)
                )

                last_escalation = cursor.fetchone()

                # =====================================
                # DETERMINE NEXT LEVEL
                # =====================================

                if not last_escalation:

                    next_level = 0

                else:

                    sent_time = last_escalation["sent_at"]

                    current_time = datetime.now()

                    difference_minutes = (
                        current_time - sent_time
                    ).total_seconds() / 60

                    # =====================================
                    # WAIT FOR INTERVAL
                    # =====================================

                    if (
                        difference_minutes
                        < escalation_interval
                    ):
                        continue

                    next_level = (
                        last_escalation[
                            "escalation_level"
                        ] + 1
                    )

                # =====================================
                # ALL ENGINEERS ALREADY NOTIFIED
                # =====================================

                if next_level >= len(engineers):

                    print(
                        f"All engineers already notified "
                        f"for {incident_id}"
                    )

                    continue

                # =====================================
                # CURRENT ENGINEER
                # =====================================

                engineer = engineers[next_level]

                engineer_id = engineer["id"]

                engineer_name = engineer["name"]

                engineer_email = engineer["email"]

                # =====================================
                # PREVIOUS ENGINEER MESSAGE
                # =====================================

                previous_engineer_message = ""

                if next_level > 0:

                    previous_names = []

                    for i in range(next_level):

                        previous_names.append(
                            engineers[i]["name"]
                        )

                    joined_names = ", ".join(
                        previous_names
                    )

                    previous_engineer_message = (
                        f"Email has already been sent "
                        f"to {joined_names} but the "
                        f"issue is still not resolved.\n\n"
                    )

                # =====================================
                # EMAIL SUBJECT
                # =====================================

                subject = (
                    f"High Risk Incident Alert "
                    f"- {incident_id}"
                )

                # =====================================
                # EMAIL BODY
                # =====================================

                body = f"""
{previous_engineer_message}

Incident ID: {incident_id}

Current Risk Score: {risk_score}%

Incident Status: {incident_status}

This incident has crossed the SLA risk threshold.

Please resolve the issue immediately.
                """

                # =====================================
                # SEND EMAIL
                # =====================================

                try:

                    EmailService.send_email(
                        engineer_email,
                        subject,
                        body
                    )

                    print(
                        f"Escalation email sent "
                        f"to {engineer_name}"
                    )

                except Exception as email_error:

                    print(
                        "EMAIL SEND ERROR:",
                        str(email_error)
                    )

                    continue

                # =====================================
                # STORE ESCALATION HISTORY
                # =====================================

                cursor.execute(
                    """
                    INSERT INTO incident_escalations
                    (
                        incident_id,
                        engineer_id,
                        escalation_level,
                        email_sent,
                        resolved
                    )
                    VALUES
                    (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s
                    )
                    """,
                    (
                        incident_id,
                        engineer_id,
                        next_level,
                        True,
                        False
                    )
                )

                connection.commit()

        except Exception as e:

            print(
                "ESCALATION ERROR:",
                str(e)
            )

        finally:

            # =====================================
            # SAFE CURSOR CLOSE
            # =====================================

            try:

                if cursor:
                    cursor.close()

            except Exception as e:

                print(
                    "Cursor close error:",
                    str(e)
                )

            # =====================================
            # SAFE CONNECTION CLOSE
            # =====================================

            try:

                if (
                    connection
                    and connection.is_connected()
                ):
                    connection.close()

            except Exception as e:

                print(
                    "Connection close error:",
                    str(e)
                )