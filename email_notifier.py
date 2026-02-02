#!/usr/bin/env python3
# MoSMART Monitor
# Copyright (C) 2026 Magnus S. Modig
# Licensed under GPLv3. See LICENSE for details.

import smtplib
import json
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from datetime import datetime
from cryptography.fernet import Fernet

# Import config manager for centralized settings
try:
    from config_manager import get_section, update_section
except ImportError:
    # Fallback if config_manager not available
    def get_section(section):
        return {}
    def update_section(section, data):
        return False

# Encryption key file for password encryption
KEY_FILE = Path.home() / '.mosmart' / '.email_key'

def _get_encryption_key():
    """Get or create encryption key for password storage"""
    if KEY_FILE.exists():
        with open(KEY_FILE, 'rb') as f:
            return f.read()
    else:
        # Generate new key
        key = Fernet.generate_key()
        KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(KEY_FILE, 'wb') as f:
            f.write(key)
        # Make key file readable only by user
        KEY_FILE.chmod(0o600)
        return key

def _encrypt_password(password):
    """Encrypt password using Fernet"""
    if not password:
        return ''
    key = _get_encryption_key()
    f = Fernet(key)
    encrypted = f.encrypt(password.encode('utf-8'))
    return base64.b64encode(encrypted).decode('utf-8')

def _decrypt_password(encrypted_password):
    """Decrypt password using Fernet"""
    if not encrypted_password:
        return ''
    try:
        key = _get_encryption_key()
        f = Fernet(key)
        encrypted_bytes = base64.b64decode(encrypted_password.encode('utf-8'))
        decrypted = f.decrypt(encrypted_bytes)
        return decrypted.decode('utf-8')
    except Exception as e:
        print(f"⚠️ Password decryption failed: {e}")
        return ''


def load_email_config():
    """
    Load email configuration from config_manager
    Returns email config dict from alert_channels.email section
    Password is automatically decrypted
    """
    try:
        alert_channels = get_section('alert_channels')
        email_config = alert_channels.get('email', {})
        
        # Ensure all required fields exist with defaults
        defaults = {
            'enabled': False,
            'smtp_server': 'smtp.gmail.com',
            'smtp_port': 587,
            'smtp_username': '',
            'smtp_password': '',
            'from_email': '',
            'to_emails': [],
            'use_tls': True,
            'use_starttls': True,
            'alert_on_severity': ['critical', 'high']
        }
        
        # Merge defaults with actual config
        for key, default_value in defaults.items():
            if key not in email_config:
                email_config[key] = default_value
        
        # Decrypt password if it exists
        if email_config.get('smtp_password'):
            email_config['smtp_password'] = _decrypt_password(email_config['smtp_password'])
        
        return email_config
    except Exception as e:
        print(f"Error loading email config: {e}")
        return {
            'enabled': False,
            'smtp_server': 'smtp.gmail.com',
            'smtp_port': 587,
            'smtp_username': '',
            'smtp_password': '',
            'from_email': '',
            'to_emails': [],
            'use_tls': True,
            'use_starttls': True,
            'alert_on_severity': ['critical', 'high']
        }


def save_email_config(email_config):
    """
    Save email configuration via config_manager
    Updates the alert_channels.email section
    Password is automatically encrypted before saving
    """
    try:
        # Make a copy to avoid modifying the original
        config_to_save = email_config.copy()
        
        # Encrypt password if it exists and is not already encrypted
        if config_to_save.get('smtp_password'):
            # Only encrypt if it's not already encrypted (simple check: not base64 with ==)
            password = config_to_save['smtp_password']
            if password and not (len(password) > 20 and password.endswith('==')):
                config_to_save['smtp_password'] = _encrypt_password(password)
        
        alert_channels = get_section('alert_channels')
        alert_channels['email'] = config_to_save
        return update_section('alert_channels', alert_channels)
    except Exception as e:
        print(f"Error saving email config: {e}")
        return False


def test_email_config(config):
    """Test email configuration by sending a test email"""
    if not config.get('enabled'):
        return {'success': False, 'error': '❌ E-postvarslinger er deaktivert i innstillinger'}
    
    if not config.get('smtp_username') or not config.get('smtp_password'):
        return {'success': False, 'error': '❌ SMTP-brukernavn og passord er påkrevd'}
    
    if not config.get('to_emails'):
        return {'success': False, 'error': '❌ Ingen mottaker-epostadresser konfigurert'}
    
    try:
        # Create test message
        subject = "🔧 MoSMART - Test Email"
        body = f"""This is a test email from MoSMART disk monitoring system.

If you received this, email notifications are configured correctly!

Configuration:
- SMTP Server: {config['smtp_server']}:{config['smtp_port']}
- From: {config.get('from_email', config['smtp_username'])}
- To: {', '.join(config['to_emails'])}
- TLS: {config.get('use_tls', True)}
- STARTTLS: {config.get('use_starttls', True)}

Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---
MoSMART Disk Monitor
        """
        
        result = send_email(
            subject=subject,
            body=body,
            to_emails=config['to_emails'],
            config=config
        )
        
        if result.get('success'):
            return {'success': True, 'message': f"✉️ Test-epost sendt til {', '.join(config['to_emails'])}"}
        else:
            return {'success': False, 'error': result.get('error', 'Ukjent feil ved sending')}
    
    except Exception as e:
        return {'success': False, 'error': f'❌ Feil ved sending av test-epost: {str(e)}'}


def send_email(subject, body, to_emails=None, config=None):
    """
    Send email notification
    
    Args:
        subject: Email subject
        body: Email body (plain text)
        to_emails: List of recipient emails (optional, uses config if not provided)
        config: Email config dict (optional, loads from file if not provided)
        
    Returns:
        dict with 'success' and 'error' keys
    """
    if config is None:
        config = load_email_config()
    
    if not config.get('enabled'):
        print("Email notifications disabled - skipping email")
        return {'success': False, 'error': 'E-postvarslinger er deaktivert'}
    
    if to_emails is None:
        to_emails = config.get('to_emails', [])
    
    if not to_emails:
        print("No recipient emails configured")
        return {'success': False, 'error': 'Ingen mottaker-epostadresser konfigurert'}
    
    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = config.get('from_email', config.get('smtp_username'))
        msg['To'] = ', '.join(to_emails)
        
        # Add plain text body
        text_part = MIMEText(body, 'plain', 'utf-8')
        msg.attach(text_part)
        
        # Connect to SMTP server
        print(f"📡 Kobler til SMTP-server {config['smtp_server']}:{config['smtp_port']}...")
        
        # Handle encryption
        use_tls = config.get('use_tls', True)
        use_starttls = config.get('use_starttls', True)
        
        if use_starttls:
            # STARTTLS - start with plain connection then upgrade
            print("🔒 Bruker STARTTLS kryptering")
            server = smtplib.SMTP(config['smtp_server'], config['smtp_port'], timeout=30)
            server.set_debuglevel(1)  # Enable debug output
            server.starttls()
        elif use_tls:
            # Direct TLS/SSL connection (use SMTP_SSL instead)
            print("🔒 Bruker direkte TLS/SSL kryptering")
            server = smtplib.SMTP_SSL(config['smtp_server'], config['smtp_port'], timeout=30)
            server.set_debuglevel(1)  # Enable debug output
        else:
            # No encryption (not recommended)
            print("⚠️ Ingen kryptering (ikke anbefalt)")
            server = smtplib.SMTP(config['smtp_server'], config['smtp_port'], timeout=30)
            server.set_debuglevel(1)  # Enable debug output
        
        # Login
        print(f"🔑 Logger inn som {config['smtp_username']}...")
        server.login(config['smtp_username'], config['smtp_password'])
        
        # Send email
        print(f"📤 Sender e-post til {', '.join(to_emails)}...")
        server.send_message(msg)
        server.quit()
        
        print(f"✅ E-post sendt til {', '.join(to_emails)}: {subject}")
        return {'success': True}
    
    except smtplib.SMTPAuthenticationError as e:
        error_msg = f"Autentisering feilet - sjekk brukernavn/passord. Detaljer: {str(e)}"
        print(f"❌ {error_msg}")
        return {'success': False, 'error': error_msg}
    except smtplib.SMTPConnectError as e:
        error_msg = f"Kan ikke koble til SMTP-server {config['smtp_server']}:{config['smtp_port']}. Sjekk server og port. Detaljer: {str(e)}"
        print(f"❌ {error_msg}")
        return {'success': False, 'error': error_msg}
    except smtplib.SMTPException as e:
        error_msg = f"SMTP-feil: {str(e)}"
        print(f"❌ {error_msg}")
        return {'success': False, 'error': error_msg}
    except TimeoutError as e:
        error_msg = f"Tidsavbrudd ved tilkobling til {config['smtp_server']}:{config['smtp_port']}. Sjekk nettverkstilkobling og brannmur."
        print(f"❌ {error_msg}")
        return {'success': False, 'error': error_msg}
    except Exception as e:
        error_msg = f"Uventet feil: {str(e)}"
        print(f"❌ {error_msg}")
        return {'success': False, 'error': error_msg}


def send_alert_email(alert_data):
    """
    Send email for a disk alert
    
    Args:
        alert_data: Alert dict from alert_engine
    """
    config = load_email_config()
    
    if not config.get('enabled'):
        return False
    
    # Check if this severity should trigger email
    alert_severity = alert_data.get('severity', 'info')
    if alert_severity not in config.get('alert_on_severity', ['critical']):
        return False
    
    # Format email
    severity_icons = {
        'info': 'ℹ️',
        'warning': '⚠️',
        'high': '🟠',
        'critical': '🔴'
    }
    
    icon = severity_icons.get(alert_severity, '•')
    disk_id = alert_data.get('disk_id', 'Unknown')
    message = alert_data.get('message', '')
    alert_type = alert_data.get('alert_type', '')
    timestamp = alert_data.get('timestamp', datetime.now().isoformat())
    
    subject = f"{icon} MoSMART Alert: {alert_severity.upper()} - {disk_id}"
    
    body = f"""
MoSMART Disk Monitoring Alert
{'=' * 50}

Severity: {alert_severity.upper()} {icon}
Disk: {disk_id}
Alert Type: {alert_type}
Time: {timestamp}

Message:
{message}

Details:
- Metric: {alert_data.get('metric', 'N/A')}
- Old Value: {alert_data.get('old_value', 'N/A')}
- New Value: {alert_data.get('new_value', 'N/A')}

{'=' * 50}
This is an automated alert from MoSMART.
Check your dashboard for more details: http://127.0.0.1:5000

---
MoSMART Disk Monitor
    """
    
    result = send_email(subject=subject, body=body, config=config)
    return result.get('success', False)
