import os
import smtplib
import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

# --- Email Configuration ---
# It's highly recommended to use environment variables for sensitive data.
# This script loads them from a file named '.env' in the same directory.
load_dotenv()

SMTP_SERVER = "smtp.office365.com"  # SMTP server for Outlook/Office 365
SMTP_PORT = 587                 # Use 587 for TLS or 465 for SSL
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

# --- Recipient Configuration ---
# List of recipient email addresses
RECIPIENT_EMAILS = ["harshith@acutant.com"] # TODO: Change this


def send_email(html_content, subject):
    """
    Sends an email with the given HTML content to the configured recipients.
    """
    if not all([EMAIL_USER, EMAIL_PASSWORD]):
        print("Error: Email user or password not configured. Please check your .env file.")
        return

    msg = MIMEMultipart()
    msg['From'] = EMAIL_USER
    msg['To'] = ", ".join(RECIPIENT_EMAILS)
    msg['Subject'] = subject

    # Attach the HTML content
    msg.attach(MIMEText(html_content, 'html'))

    try:
        print(f"Connecting to SMTP server at {SMTP_SERVER}:{SMTP_PORT}...")
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()  # Secure the connection
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.send_message(msg)
            print("Email sent successfully!")
    except smtplib.SMTPAuthenticationError:
        print("Error: SMTP authentication failed. Check your username/password and app-specific password settings.")
    except Exception as e:
        print(f"An error occurred while sending the email: {e}")


if __name__ == "__main__":
    # This is a test to demonstrate how the function works.
    # In the next step, we will replace this with the actual HTML report.
    print("Running email test...")

    today_str = datetime.date.today().strftime("%d-%b-%Y")
    test_subject = f"Daily Verification Report - {today_str}"
    test_html_body = "<h1>Test Report</h1><p>This is a test email from the automation script.</p>"

    send_email(test_html_body, test_subject)