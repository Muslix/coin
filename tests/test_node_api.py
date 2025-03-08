import sys
import os
import pytest
import json
from unittest.mock import patch, MagicMock

# Pfad-Setup für den Import der Module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from node import Node
from blockchain import Blockchain


@pytest.fixture
def test_client():
    """Erstellt einen Flask-Test-Client für die API-Tests"""
    # Mock Blockchain erstellen
    blockchain = Blockchain(difficulty=1)
    
    # Node mit Mock-Blockchain instanziieren
    node = Node(host='127.0.0.1', port=5000, blockchain=blockchain)
    
    # Flask-Test-Client zurückgeben
    test_client = node.app.test_client()
    
    return test_client, node, blockchain


def test_node_info(test_client):
    """Test des Node-Info-Endpunkts"""
    client, node, _ = test_client
    
    # GET-Request an den /node/info Endpunkt senden
    response = client.get('/node/info')
    
    # Überprüfe Statuscode
    assert response.status_code == 200
    
    # Parse JSON-Antwort
    data = json.loads(response.data)
    
    # Überprüfe notwendige Felder
    assert 'node_id' in data
    assert 'host' in data
    assert 'port' in data
    assert 'peers' in data
    assert 'blockchain_length' in data
    assert 'difficulty' in data
    assert 'pending_transactions' in data


def test_get_blockchain(test_client):
    """Test des Blockchain-Abrufs"""
    client, _, blockchain = test_client
    
    # GET-Request an den /blockchain Endpunkt senden
    response = client.get('/blockchain')
    
    # Überprüfe Statuscode
    assert response.status_code == 200
    
    # Parse JSON-Antwort
    data = json.loads(response.data)
    
    # Überprüfe Struktur der Antwort
    assert 'chain' in data
    assert 'length' in data
    assert data['length'] == len(blockchain.chain)
    assert len(data['chain']) == len(blockchain.chain)


def test_get_block_by_index(test_client):
    """Test des Block-Abrufs nach Index"""
    client, _, blockchain = test_client
    
    # Zuerst Guthaben für den Sender bereitstellen
    blockchain.add_transaction("genesis", "sender1", 100)
    blockchain.mine_pending_transactions("miner1")
    
    # Füge eine Transaktion hinzu
    blockchain.add_transaction("sender1", "recipient1", 50)
    blockchain.mine_pending_transactions("miner2")
    
    # GET-Request für den Block mit Index 2 (da wir jetzt 2 Blöcke haben + Genesis)
    response = client.get('/block/index/2')
    
    # Überprüfe Statuscode
    assert response.status_code == 200
    
    # Parse JSON-Antwort
    data = json.loads(response.data)
    
    # Überprüfe grundlegende Struktur
    assert 'index' in data
    assert 'transactions' in data
    assert data['index'] == 2
    
    # Überprüfe Inhalt des Blocks
    assert any(tx['from'] == "sender1" and tx['to'] == "recipient1" and tx['amount'] == 50
               for tx in data['transactions'])


def test_new_transaction(test_client):
    """Test des Transaktions-Erstellungs-Endpunkts"""
    client, node, blockchain = test_client
    
    # Mock für broadcast_transaction, um Netzwerkanfragen zu vermeiden
    node.broadcast_transaction = MagicMock()
    
    # Zuerst Guthaben für den Sender bereitstellen
    sender_address = 'test_sender'
    blockchain.add_transaction("genesis", sender_address, 1000)
    blockchain.mine_pending_transactions("miner1")
    
    # Transaktion erstellen
    transaction = {
        'sender': sender_address,
        'recipient': 'test_recipient',
        'amount': 100,
        'signature': 'test_signature'  # In a real test, we would generate a valid signature
    }
    
    # POST-Request senden
    response = client.post('/transaction/new',
                          data=json.dumps(transaction),
                          content_type='application/json')
    
    # Überprüfe Statuscode
    assert response.status_code == 200
    
    # Überprüfe, ob die Transaktion in den pending_transactions hinzugefügt wurde
    assert len(blockchain.pending_transactions) >= 1
    
    # Find our transaction in pending_transactions (might not be the only one)
    matching_tx = [tx for tx in blockchain.pending_transactions 
                  if tx['from'] == sender_address and 
                     tx['to'] == 'test_recipient' and 
                     tx['amount'] == 100]
    
    assert len(matching_tx) > 0
    
    # Überprüfe, ob broadcast_transaction aufgerufen wurde
    node.broadcast_transaction.assert_called_once()


def test_pending_transactions(test_client):
    """Test des Endpunkts für ausstehende Transaktionen"""
    client, _, blockchain = test_client
    
    # Zuerst Guthaben für den Sender bereitstellen
    blockchain.add_transaction("genesis", "sender1", 100)
    blockchain.mine_pending_transactions("miner1")
    
    # Füge eine Transaktion hinzu
    blockchain.add_transaction("sender1", "recipient1", 50)
    
    # GET-Request senden
    response = client.get('/transactions/pending')
    
    # Überprüfe Statuscode
    assert response.status_code == 200
    
    # Parse JSON-Antwort
    data = json.loads(response.data)
    
    # Überprüfe, ob die Transaktion in der Liste ist
    assert 'transactions' in data
    assert 'count' in data
    assert data['count'] == 1
    
    # Überprüfe den Inhalt der Transaktion
    assert len(data['transactions']) == 1
    assert data['transactions'][0]['from'] == "sender1"
    assert data['transactions'][0]['to'] == "recipient1"
    assert data['transactions'][0]['amount'] == 50


def test_mine_endpoint(test_client):
    """Test des Mining-Endpunkts"""
    client, node, blockchain = test_client
    
    # Mock für broadcast_new_block, um Netzwerkanfragen zu vermeiden
    node.broadcast_new_block = MagicMock()
    
    # Füge eine Transaktion hinzu
    blockchain.add_transaction("sender1", "recipient1", 50)
    
    # GET-Request zum Minen eines Blocks senden
    response = client.get('/mine?address=test_miner')
    
    # Überprüfe Statuscode
    assert response.status_code == 200
    
    # Parse JSON-Antwort
    data = json.loads(response.data)
    
    # Überprüfe, ob der Block erfolgreich gemined wurde
    assert 'message' in data
    assert 'block_index' in data
    assert 'block_hash' in data
    assert 'transactions' in data
    
    # Überprüfe, ob der Block zur Chain hinzugefügt wurde
    assert len(blockchain.chain) == 2
    
    # Überprüfe, ob broadcast_new_block aufgerufen wurde
    node.broadcast_new_block.assert_called_once()


def test_get_balance(test_client):
    """Test des Balance-Endpunkts"""
    client, _, blockchain = test_client
    
    # Zuerst Guthaben für den Sender bereitstellen
    blockchain.add_transaction("genesis", "sender1", 100)
    blockchain.mine_pending_transactions("miner1")
    
    # Füge eine Transaktion hinzu und mine einen Block
    blockchain.add_transaction("sender1", "recipient1", 50)
    blockchain.mine_pending_transactions("miner2")
    
    # GET-Request für Balance des Empfängers senden
    response = client.get('/balance?address=recipient1')
    
    # Überprüfe Statuscode
    assert response.status_code == 200
    
    # Parse JSON-Antwort
    data = json.loads(response.data)
    
    # Überprüfe, ob der Kontostand korrekt ist
    assert 'address' in data
    assert 'balance' in data
    assert data['address'] == 'recipient1'
    assert data['balance'] == 50
    
    # Optional: Überprüfe auch den Kontostand des Senders
    response_sender = client.get('/balance?address=sender1')
    data_sender = json.loads(response_sender.data)
    assert data_sender['balance'] == 50  # Started with 100, sent 50


def test_node_registration(test_client):
    """Test der Node-Registrierung"""
    client, node, _ = test_client
    
    # Mock für requets.post, um HTTP-Requests zu vermeiden
    with patch('requests.post') as mock_post:
        # POST-Request zur Node-Registrierung senden
        response = client.post('/nodes/register',
                             data=json.dumps({'nodes': ['http://testnode:5000']}),
                             content_type='application/json')
        
        # Überprüfe Statuscode
        assert response.status_code == 200
        
        # Parse JSON-Antwort
        data = json.loads(response.data)
        
        # Überprüfe, ob der Node registriert wurde
        assert 'message' in data
        assert 'total_nodes' in data
        assert 'http://testnode:5000' in data['total_nodes']
        assert 'http://testnode:5000' in node.peers


@pytest.mark.skipif(True, reason="Erfordert aktive HTTP-Verbindungen zu Peers")
def test_resolve_conflicts(test_client):
    """
    Test des Konsens-Algorithmus
    
    Hinweis: Dieser Test ist standardmäßig deaktiviert, da er echte HTTP-Verbindungen erfordert.
    In einer echten Testumgebung würden alle HTTP-Anfragen gemockt.
    """
    client, node, blockchain = test_client
    
    # Mock-Peer mit längerer Chain
    peer_url = 'http://mockpeer:5000'
    node.register_node(peer_url)
    
    # Mock für requests.get
    with patch('requests.get') as mock_get:
        # Mock-Antwort erstellen
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        # Erstelle längere Chain
        longer_chain = []
        for i in range(3):  # 3 Blöcke (länger als unsere 1 Block-Chain)
            block_data = {
                'index': i,
                'timestamp': 1000000 + i * 60,
                'transactions': [],
                'previous_hash': f"hash{i-1}" if i > 0 else "0",
                'hash': f"hash{i}",
                'merkle_root': '',
                'nonce': 0,
                'difficulty': 1
            }
            longer_chain.append(block_data)
        
        mock_response.json.return_value = {
            'chain': longer_chain,
            'length': len(longer_chain)
        }
        mock_get.return_value = mock_response
        
        # GET-Request zum Auflösen von Konflikten senden
        response = client.get('/nodes/resolve')
        
        # Überprüfe Statuscode
        assert response.status_code == 200
        
        # Parse JSON-Antwort
        data = json.loads(response.data)
        
        # Da die gemockte Chain länger ist, sollte unsere ersetzt worden sein
        assert 'message' in data
        assert data['message'] == 'Our chain was replaced'
        assert mock_get.called


def test_smart_contract_deployment(test_client):
    """Test der Smart Contract Deployment API"""
    client, _, blockchain = test_client  # Fixed unpacking syntax
    
    # Stelle sicher, dass die Smart Contract Engine initialisiert ist
    blockchain.initialize_contract_engine()
    
    # Completely remove indentation from contract code
    contract_data = {
        'code': '''
def constructor(context):
    context['storage']['value'] = 42

def get_value(context):
    return context['storage']['value']
''',
        'owner': 'test_owner',
        'initial_balance': 0.0
    }
    
    # POST-Request zum Contract-Deployment senden
    response = client.post('/contracts/deploy',
                         data=json.dumps(contract_data),
                         content_type='application/json')
    
    # Überprüfe Statuscode
    assert response.status_code == 200