import os
import smtplib

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))

SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")


class EmailService:

    @staticmethod
    def send_email(to_email, subject, body):

        try:

            # =====================================
            # VALIDATION
            # =====================================

            if not SMTP_SERVER:
                raise Exception(
                    "SMTP_SERVER missing in .env"
                )

            if not SMTP_EMAIL:
                raise Exception(
                    "SMTP_EMAIL missing in .env"
                )

            if not SMTP_PASSWORD:
                raise Exception(
                    "SMTP_PASSWORD missing in .env"
                )

            # =====================================
            # CREATE EMAIL
            # =====================================

            msg = MIMEMultipart()

            msg["From"] = SMTP_EMAIL
            msg["To"] = to_email
            msg["Subject"] = subject

            msg.attach(
                MIMEText(body, "plain")
            )

            # =====================================
            # SMTP CONNECTION
            # =====================================

            server = smtplib.SMTP(
                SMTP_SERVER,
                SMTP_PORT
            )

            server.ehlo()

            # =====================================
            # ENABLE TLS
            # =====================================

            server.starttls()

            server.ehlo()

            # =====================================
            # LOGIN
            # =====================================

            server.login(
                SMTP_EMAIL,
                SMTP_PASSWORD
            )

            # =====================================
            # SEND EMAIL
            # =====================================

            server.sendmail(
                SMTP_EMAIL,
                to_email,
                msg.as_string()
            )

            # =====================================
            # CLOSE CONNECTION
            # =====================================

            server.quit()

            print(
                f"Email successfully sent to {to_email}"
            )

        except Exception as e:

            print(
                "EMAIL ERROR:",
                str(e)
            )

            raise Exception(str(e))