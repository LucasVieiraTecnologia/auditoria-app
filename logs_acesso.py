import json
import os
from datetime import datetime
from pathlib import Path

# Define the log file path
LOG_FILE = Path('logs_acesso.json')

def init_logs():
    """Initialize the log file if it doesn't exist"""
    if not LOG_FILE.exists():
        # Create an empty list as initial content
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f, ensure_ascii=False, indent=2)

def log_acesso(username: str, acao: str, detalhes: str = ''):
    """
    Log an access event
    
    Args:
        username: The username performing the action
        acao: The action being performed (e.g., 'LOGIN', 'LOGOUT')
        detalhes: Additional details about the action
    """
    # Ensure log file exists
    init_logs()
    
    # Create log entry
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'username': username,
        'acao': acao,
        'detalhes': detalhes
    }
    
    # Read existing logs
    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        logs = json.load(f)
    
    # Append new log entry
    logs.append(log_entry)
    
    # Write back to file
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)

def ler_logs():
    """
    Read all log entries
    
    Returns:
        List of log entries (each entry is a dict)
    """
    # Ensure log file exists
    init_logs()
    
    # Read and return logs
    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)