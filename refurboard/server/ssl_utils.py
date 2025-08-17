"""
SSL certificate generation utilities
"""

import os
import random
from OpenSSL import crypto


def get_cert_hostname(cert_file):
    """Get the hostname from an existing certificate"""
    try:
        with open(cert_file, "rb") as f:
            cert_data = f.read()
        cert = crypto.load_certificate(crypto.FILETYPE_PEM, cert_data)
        return cert.get_subject().CN
    except Exception:
        return None


def cert_exists_and_valid(cert_file, key_file, hostname):
    """Check if certificate files exist and are valid for the given hostname"""
    try:
        # Check if files exist
        if not (os.path.exists(cert_file) and os.path.exists(key_file)):
            return False
        
        # Check if certificate is for the correct hostname
        existing_hostname = get_cert_hostname(cert_file)
        if existing_hostname != hostname:
            return False
            
        # Check if certificate and key are valid together
        with open(cert_file, "rb") as f:
            cert_data = f.read()
        with open(key_file, "rb") as f:
            key_data = f.read()
            
        cert = crypto.load_certificate(crypto.FILETYPE_PEM, cert_data)
        key = crypto.load_privatekey(crypto.FILETYPE_PEM, key_data)
        
        # Try to verify the key matches the certificate
        context = crypto.X509StoreContext(crypto.X509Store(), cert)
        
        return True
    except Exception:
        return False


def generate_self_signed_cert(hostname, cert_file, key_file, force_regenerate=False):
    """Generate a self-signed SSL certificate, reusing existing one if valid"""
    
    # Check if we can reuse existing certificate
    if not force_regenerate and cert_exists_and_valid(cert_file, key_file, hostname):
        print(f"Reusing existing SSL certificate for {hostname}")
        return
    
    print(f"Generating new SSL certificate for {hostname}")
    
    k = crypto.PKey()
    k.generate_key(crypto.TYPE_RSA, 2048)

    cert = crypto.X509()
    cert.get_subject().C = "US"
    cert.get_subject().ST = "California"
    cert.get_subject().L = "San Francisco"
    cert.get_subject().O = "Refurboard"
    cert.get_subject().OU = "Refurboard"
    cert.get_subject().CN = hostname
    cert.set_serial_number(random.randint(0, 1000000000))
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(10*365*24*60*60)
    cert.set_issuer(cert.get_subject())
    cert.set_pubkey(k)
    cert.sign(k, 'sha256')

    with open(cert_file, "wt") as f:
        f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert).decode("utf-8"))
    with open(key_file, "wt") as f:
        f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, k).decode("utf-8"))
