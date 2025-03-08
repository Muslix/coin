import sys
import os
import pytest
import time
from typing import Dict, Any

# Pfad-Setup für den Import der Module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from blockchain import Blockchain, Block, MerkleTree


@pytest.fixture
def fresh_blockchain():
    """Eine komplett frische Blockchain-Instanz ohne zusätzliche Blöcke"""
    return Blockchain(difficulty=2)  # Niedrige Schwierigkeit für schnellere Tests

@pytest.fixture
def blockchain_with_balance():
    """Eine Blockchain-Instanz mit Guthaben für Test-Adressen"""
    bc = Blockchain(difficulty=2)  # Niedrige Schwierigkeit für schnellere Tests
    
    # Initial-Balance für Test-Sender bereitstellen
    test_addresses = ["sender1", "sender2", "test_sender"]
    
    # Erstelle Initial-Guthaben für Test-Adressen
    for address in test_addresses:
        bc.add_transaction("genesis", address, 1000)
    
    # Mine einen Block, um die Initial-Transaktionen zu bestätigen
    bc.mine_pending_transactions("setup_miner")
    
    return bc

# Alias für Abwärtskompatibilität - bestehende Tests verwenden dieses Fixture
@pytest.fixture
def blockchain(request):
    """
    Wählt die passende Blockchain-Instanz basierend auf dem Test
    """
    # Liste von Tests, die eine frische Blockchain benötigen
    fresh_blockchain_tests = [
        "test_genesis_block_creation",
    ]
    
    # Prüfen, ob der aktuelle Test eine frische Blockchain benötigt
    test_name = request.function.__name__
    if test_name in fresh_blockchain_tests:
        return request.getfixturevalue("fresh_blockchain")
    else:
        return request.getfixturevalue("blockchain_with_balance")


def test_genesis_block_creation(blockchain):
    """Test, ob der Genesis-Block korrekt erstellt wird"""
    assert len(blockchain.chain) == 1
    assert blockchain.chain[0].index == 0
    assert blockchain.chain[0].previous_hash == "0"
    

def test_add_transaction(blockchain):
    """Test, ob Transaktionen korrekt hinzugefügt werden"""
    # Zuerst Guthaben für den Sender bereitstellen
    blockchain.add_transaction("genesis", "sender1", 1000)
    blockchain.mine_pending_transactions("miner1")
    
    # Füge eine Transaktion hinzu
    tx_id = blockchain.add_transaction("sender1", "recipient1", 100)
    
    # Überprüfe, ob die Transaktion in den pending_transactions ist
    assert len(blockchain.pending_transactions) == 1
    assert blockchain.pending_transactions[0]["from"] == "sender1"
    assert blockchain.pending_transactions[0]["to"] == "recipient1"
    assert blockchain.pending_transactions[0]["amount"] == 100
    assert "id" in blockchain.pending_transactions[0]
    assert blockchain.pending_transactions[0]["id"] == tx_id
    
def test_mine_pending_transactions(blockchain):
    """Test, ob das Mining von Transaktionen funktioniert"""
    # Speichere die initiale Anzahl von Blöcken
    initial_blocks = len(blockchain.chain)
    
    # Füge eine Transaktion hinzu
    blockchain.add_transaction("sender1", "recipient1", 50)
    
    # Mine einen Block
    miner_address = "miner1"
    block = blockchain.mine_pending_transactions(miner_address)
    
    # Überprüfe, ob ein neuer Block erstellt wurde
    assert len(blockchain.chain) == initial_blocks + 1
    assert blockchain.chain[-1].index == initial_blocks
    
    # Überprüfe, ob die Transaktion im Block ist
    assert any(tx["from"] == "sender1" and tx["to"] == "recipient1" and tx["amount"] == 50 
               for tx in blockchain.chain[-1].transactions)
    
    # Überprüfe, ob die Mining-Belohnung hinzugefügt wurde
    assert any(tx["from"] == "network" and tx["to"] == miner_address and tx["amount"] == blockchain.mining_reward 
               for tx in blockchain.chain[-1].transactions)
    
    # Überprüfe, ob die pending_transactions zurückgesetzt wurden
    assert len(blockchain.pending_transactions) == 0
    

def test_get_balance(blockchain):
    """Test, ob der Kontostand korrekt berechnet wird"""
    # Speichere den anfänglichen Kontostand von sender1
    initial_balance = blockchain.get_balance("sender1")
    
    # Neuen Test-Empfänger verwenden, der noch kein Guthaben hat
    recipient = "new_recipient1"
    
    # Füge eine Transaktion hinzu und mine einen Block
    blockchain.add_transaction("sender1", recipient, 50)
    blockchain.mine_pending_transactions("miner2")
    
    # Überprüfe den Kontostand der Beteiligten
    assert blockchain.get_balance("sender1") == initial_balance - 50  # Sent 50
    assert blockchain.get_balance(recipient) == 50  # Received 50
    assert blockchain.get_balance("miner2") == blockchain.mining_reward  # Mining reward

def test_is_chain_valid(blockchain):
    """Test, ob die Kette korrekt validiert wird"""
    # Füge zwei Blöcke hinzu mit gültigen Transaktionen
    blockchain.add_transaction("genesis", "sender1", 100)
    blockchain.mine_pending_transactions("miner1")
    
    blockchain.add_transaction("sender1", "recipient1", 50)
    blockchain.mine_pending_transactions("miner2")
    
    # Die Kette sollte gültig sein
    assert blockchain.is_chain_valid() == True
    
    # Manipuliere die Kette - ändere die Transaktion UND aktualisiere den merkle_root
    blockchain.chain[1].transactions[0]["amount"] = 200
    
    # Die Kette sollte jetzt ungültig sein, weil der merkle_root nicht mehr stimmt
    assert blockchain.is_chain_valid() == False
    

def test_merkle_tree():
    """Test der Merkle-Tree-Implementierung"""
    # Erstelle Transaktionen für den Merkle-Tree
    transactions = [
        {"from": "A", "to": "B", "amount": 10},
        {"from": "C", "to": "D", "amount": 20},
        {"from": "E", "to": "F", "amount": 30},
        {"from": "G", "to": "H", "amount": 40}
    ]
    
    # Berechne den Merkle Root
    root = MerkleTree.create_merkle_root(transactions)
    
    # Stelle sicher, dass der Root ein String und nicht leer ist
    assert isinstance(root, str)
    assert len(root) > 0
    
    # Verifiziere, dass die Transaktionen im Tree sind
    assert MerkleTree.verify_transaction(transactions[0], root, transactions) == True
    
    # Ändere eine Transaktion
    altered_transactions = transactions.copy()
    altered_transactions[0]["amount"] = 999
    
    # Der Root sollte sich ändern
    altered_root = MerkleTree.create_merkle_root(altered_transactions)
    assert root != altered_root


def test_continuous_mining(blockchain, monkeypatch):
    """Test des kontinuierlichen Mining-Prozesses"""
    # Mock time.sleep, um den Test zu beschleunigen
    monkeypatch.setattr(time, 'sleep', lambda x: None)
    
    # Wir wollen den aktuellen Block-Count speichern, um später zu vergleichen
    initial_block_count = len(blockchain.chain)
    
    # Starte kontinuierliches Mining
    miner_address = "miner1"
    blocks_mined = []  # List to track mined blocks
    
    # Erstelle einen Callback, der den Test fortsetzt, nachdem ein Block gemined wurde
    def mining_callback(block):
        blocks_mined.append(block)
        # Stop mining after the first block is mined
        if len(blocks_mined) >= 1:
            blockchain.stop_continuous_mining()
    
    # Starte Mining in einem separaten Thread
    blockchain.start_continuous_mining(miner_address, mining_callback)
    
    # Warte auf das Mining von mindestens einem Block oder timeout
    timeout = 5  # seconds
    start_time = time.time()
    while len(blocks_mined) < 1 and time.time() - start_time < timeout:
        time.sleep(0.1)  # Dies wird durch den Mock ersetzt
    
    # Falls die Mining-Funktion den Callback nicht aufruft, manuell stoppen
    if blockchain._mining_thread and blockchain._mining_thread.is_alive():
        blockchain.stop_continuous_mining()
    
    # Überprüfe, ob mindestens ein Block gemined wurde
    assert len(blockchain.chain) > initial_block_count
    
    # Überprüfe, ob der Callback aufgerufen wurde
    assert len(blocks_mined) > 0
    

def test_difficulty_adjustment(blockchain, monkeypatch):
    """Test der automatischen Schwierigkeitsanpassung"""
    # Setze Parameter für den Test
    blockchain.difficulty = 1
    blockchain.difficulty_adjustment_interval = 3
    blockchain.target_block_time = 10
    
    # Mock time.time, um die Blockzeiten zu kontrollieren
    current_time = 1000.0
    
    def mock_time():
        nonlocal current_time
        current_time += 1.0  # Sehr schnelles Mining, sollte die Schwierigkeit erhöhen
        return current_time
    
    monkeypatch.setattr(time, 'time', mock_time)
    
    # Speichere die ursprüngliche Schwierigkeit
    original_difficulty = blockchain.difficulty
    
    # Mine mehrere Blöcke bis zur Anpassung
    for _ in range(blockchain.difficulty_adjustment_interval):
        blockchain.mine_pending_transactions("miner1")
    
    # Die Schwierigkeit sollte erhöht werden, da das Mining zu schnell ist
    assert blockchain.difficulty > original_difficulty