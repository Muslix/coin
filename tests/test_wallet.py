import sys
import os
import pytest
import json
import tempfile
from typing import Dict, Any
import time
import secrets
# Pfad-Setup für den Import der Module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from wallet import Wallet


@pytest.fixture
def wallet():
    """Eine frische Wallet-Instanz für jeden Test"""
    return Wallet()


def test_key_generation(wallet):
    """Test, ob Schlüssel korrekt generiert werden"""
    keys = wallet.generate_keys()
    
    # Überprüfe, ob alle erwarteten Schlüssel generiert wurden
    assert "private_key" in keys
    assert "public_key" in keys
    assert "address" in keys
    
    # Überprüfe, ob die Schlüssel nicht leer sind
    assert keys["private_key"] is not None
    assert keys["public_key"] is not None
    assert keys["address"] is not None
    
    # Überprüfe, ob die Schlüssel der erwarteten Länge entsprechen
    assert len(keys["private_key"]) > 0
    assert len(keys["public_key"]) > 0
    assert len(keys["address"]) > 0


def test_address_generation(wallet):
    """Test, ob die Adressgenerierung korrekt funktioniert"""
    wallet.generate_keys()
    
    # Die Adresse sollte ein Base64-String sein
    address = wallet.address
    try:
        # Versuche die Adresse zu decodieren
        import base64
        decoded = base64.b64decode(address.encode('utf-8'))
        assert len(decoded) > 0
    except Exception:
        pytest.fail("Die Adresse ist kein gültiger Base64-String")


def test_load_keys(wallet):
    """Test, ob Schlüssel korrekt geladen werden können"""
    # Generiere zuerst Schlüssel
    original_keys = wallet.generate_keys()
    
    # Erstelle eine neue Wallet
    new_wallet = Wallet()
    
    # Lade den privaten Schlüssel in die neue Wallet
    loaded_keys = new_wallet.load_keys(original_keys["private_key"])
    
    # Die generierten öffentlichen Schlüssel und Adressen sollten übereinstimmen
    assert loaded_keys["public_key"] == original_keys["public_key"]
    assert loaded_keys["address"] == original_keys["address"]


def test_sign_transaction(wallet):
    """Test der Transaktionssignierung"""
    # Generiere Schlüssel
    wallet.generate_keys()
    
    # Erstelle eine Testtransaktion
    transaction = {
        "from": wallet.address,
        "to": "recipient_address",
        "amount": 100,
        # Add these fields explicitly for the test
        "timestamp": time.time(),
        "nonce": secrets.token_hex(8)
    }
    
    # Create a copy of the transaction before signing
    transaction_copy = transaction.copy()
    
    # Signiere die Transaktion
    signature = wallet.sign_transaction(transaction_copy)
    
    # Die Signatur sollte ein nicht-leerer String sein
    assert isinstance(signature, str)
    assert len(signature) > 0
    
    # Verifiziere die Signatur mit der Original-Transaktion
    assert wallet.verify_signature(transaction, signature, wallet.public_key)


def test_verify_address(wallet):
    """Test der Adressvalidierung"""
    wallet.generate_keys()
    
    # Die eigene Adresse sollte gültig sein
    assert wallet.verify_address(wallet.address)
    
    # Ein ungültiger String sollte als ungültig erkannt werden
    assert wallet.verify_address("invalid_address") == False
    assert wallet.verify_address("12345") == False
    assert wallet.verify_address("") == False


def test_wallet_save_load_file(wallet):
    """Test, ob die Wallet korrekt in eine Datei gespeichert und geladen werden kann"""
    # Generiere Schlüssel
    wallet.generate_keys()
    
    # Speichere sie in eine temporäre Datei
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_filename = temp_file.name
    
    try:
        # Speichere ohne Passwort
        wallet.save_to_file(temp_filename)
        
        # Lade mit einer neuen Wallet
        new_wallet = Wallet()
        loaded_keys = new_wallet.load_from_file(temp_filename)
        
        # Überprüfe, ob die geladenen Schlüssel mit den ursprünglichen übereinstimmen
        assert loaded_keys["private_key"] == wallet.private_key
        assert loaded_keys["public_key"] == wallet.public_key
        assert loaded_keys["address"] == wallet.address
    finally:
        # Bereinige die temporäre Datei
        if os.path.exists(temp_filename):
            os.unlink(temp_filename)


def test_wallet_encryption(wallet):
    """Test der Wallet-Verschlüsselung mit Passwort"""
    # Generiere Schlüssel
    wallet.generate_keys()
    
    # Verschlüssele mit Passwort
    passphrase = "secure_password"
    encrypted_data = wallet.encrypt_private_key(wallet.private_key, passphrase)
    
    # Überprüfe, ob die Verschlüsselung erfolgt ist
    assert "encrypted_private_key" in encrypted_data
    assert encrypted_data["encrypted_private_key"] != wallet.private_key
    
    # Entschlüssele und überprüfe
    decrypted_key = wallet.decrypt_private_key(encrypted_data, passphrase)
    assert decrypted_key == wallet.private_key
    
    # Test mit falschem Passwort sollte fehlschlagen
    with pytest.raises(Exception):
        wallet.decrypt_private_key(encrypted_data, "wrong_password")


def test_wallet_save_load_encrypted(wallet):
    """Test, ob die Wallet verschlüsselt gespeichert und geladen werden kann"""
    # Generiere Schlüssel
    wallet.generate_keys()
    passphrase = "test_passphrase"
    
    # Speichere verschlüsselt in eine temporäre Datei
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_filename = temp_file.name
    
    try:
        # Speichere mit Passwort
        wallet.save_to_file(temp_filename, passphrase)
        
        # Überprüfe, ob die Datei verschlüsselte Daten enthält
        with open(temp_filename, 'r') as f:
            saved_data = json.load(f)
        assert "encrypted_private_key" in saved_data
        
        # Lade mit einer neuen Wallet
        new_wallet = Wallet()
        loaded_keys = new_wallet.load_from_file(temp_filename, passphrase)
        
        # Überprüfe, ob die geladenen Schlüssel mit den ursprünglichen übereinstimmen
        assert loaded_keys["private_key"] == wallet.private_key
        assert loaded_keys["public_key"] == wallet.public_key
        assert loaded_keys["address"] == wallet.address
        
        # Versuche ohne Passwort zu laden sollte fehlschlagen
        with pytest.raises(ValueError):
            new_wallet.load_from_file(temp_filename)
            
    finally:
        # Bereinige die temporäre Datei
        if os.path.exists(temp_filename):
            os.unlink(temp_filename)