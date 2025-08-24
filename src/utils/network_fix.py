"""
Network fix for Telegram API connectivity issues.

This module provides permanent fixes for DNS and connectivity issues,
particularly in WSL and restricted network environments.
"""

import socket
import ssl
import logging
from typing import Tuple, Optional

# Known Telegram API IPs (official)
TELEGRAM_API_IPS = [
    '149.154.167.220',
    '149.154.167.40',
    '149.154.167.50',
    '149.154.167.51',
    '149.154.167.90',
    '149.154.167.91'
]

logger = logging.getLogger(__name__)


def install_network_fixes():
    """
    Install network fixes for Telegram API connectivity.
    This patches socket.getaddrinfo to handle DNS issues.
    """
    original_getaddrinfo = socket.getaddrinfo
    
    def patched_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        """
        Patched getaddrinfo that fixes Telegram API resolution.
        
        If api.telegram.org resolves to a private IP (10.x.x.x or 192.168.x.x),
        use known Telegram IPs instead.
        """
        # First try normal resolution
        try:
            results = original_getaddrinfo(host, port, family, type, proto, flags)
            
            # Check if this is Telegram API
            if host in ['api.telegram.org', 'api.telegram.org.']:
                # Check if resolved to private IP
                for result in results:
                    ip = result[4][0]
                    if ip.startswith('10.') or ip.startswith('192.168.') or ip.startswith('172.'):
                        logger.warning(f"Telegram API resolved to private IP {ip}, using fallback")
                        # Use fallback
                        return [
                            (socket.AF_INET, socket.SOCK_STREAM, 6, '', (TELEGRAM_API_IPS[0], port)),
                            (socket.AF_INET, socket.SOCK_STREAM, 6, '', (TELEGRAM_API_IPS[1], port))
                        ]
            
            return results
            
        except socket.gaierror:
            # If DNS fails completely for Telegram, use fallback
            if host in ['api.telegram.org', 'api.telegram.org.']:
                logger.warning(f"DNS resolution failed for {host}, using fallback IPs")
                return [
                    (socket.AF_INET, socket.SOCK_STREAM, 6, '', (TELEGRAM_API_IPS[0], port)),
                    (socket.AF_INET, socket.SOCK_STREAM, 6, '', (TELEGRAM_API_IPS[1], port))
                ]
            raise
    
    # Apply the patch
    socket.getaddrinfo = patched_getaddrinfo
    logger.info("Network fixes installed for Telegram API")


def test_telegram_connectivity() -> Tuple[bool, str]:
    """
    Test if we can connect to Telegram API.
    
    Returns:
        Tuple of (success, message)
    """
    import urllib.request
    import json
    
    test_urls = [
        f"https://{ip}/bot123:ABC/getMe" for ip in TELEGRAM_API_IPS[:2]
    ]
    
    for url in test_urls:
        try:
            # Create request with proper headers
            req = urllib.request.Request(
                url,
                headers={'Host': 'api.telegram.org'}
            )
            
            # Try to connect (will fail with 401 but that's ok)
            try:
                response = urllib.request.urlopen(req, timeout=5)
            except urllib.error.HTTPError as e:
                if e.code == 401:  # Unauthorized is expected with fake token
                    return True, f"Successfully connected to Telegram API at {url.split('/')[2]}"
                elif e.code == 404:
                    return True, f"Connected to Telegram API (404 means server is reachable)"
            except Exception:
                continue
                
        except Exception as e:
            continue
    
    return False, "Could not connect to any Telegram API server"


def diagnose_network_issue() -> str:
    """
    Diagnose the network issue and return a report.
    
    Returns:
        Diagnostic message
    """
    import subprocess
    
    diagnosis = []
    
    # Check DNS resolution
    try:
        ips = socket.gethostbyname_ex('api.telegram.org')[2]
        diagnosis.append(f"DNS Resolution: api.telegram.org -> {', '.join(ips)}")
        
        # Check if resolved to private IP
        for ip in ips:
            if ip.startswith('10.') or ip.startswith('192.168.') or ip.startswith('172.'):
                diagnosis.append("⚠️ WARNING: Telegram API resolving to private IP!")
                diagnosis.append("This indicates: Firewall, VPN, or ISP blocking")
                
    except Exception as e:
        diagnosis.append(f"DNS Resolution Failed: {e}")
    
    # Check if we can reach Telegram
    can_connect, message = test_telegram_connectivity()
    diagnosis.append(f"Telegram Connectivity: {message}")
    
    # Check internet connectivity
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        diagnosis.append("Internet Connectivity: OK")
    except:
        diagnosis.append("Internet Connectivity: FAILED")
    
    return "\n".join(diagnosis)


# Auto-install fixes when module is imported
install_network_fixes()