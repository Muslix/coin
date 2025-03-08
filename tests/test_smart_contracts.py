import sys
import os
import pytest
from unittest.mock import MagicMock

# Pfad-Setup für den Import der Module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from blockchain import Blockchain
from smart_contracts import SmartContractEngine, owner_only, EXAMPLE_TOKEN_CONTRACT


@pytest.fixture
def blockchain():
    """Eine Mock-Blockchain für die Tests"""
    blockchain = Blockchain(difficulty=1)
    return blockchain


@pytest.fixture
def contract_engine(blockchain):
    """Eine Smart Contract Engine für die Tests"""
    engine = SmartContractEngine(blockchain)
    return engine


def test_contract_deployment(contract_engine):
    """Test, ob ein Contract korrekt deployed werden kann"""
    owner = "test_owner_address"
    
    # Deploy einen einfachen Testcontract
    simple_contract = """
def constructor(context):
    context['storage']['value'] = 42
    
def get_value(context):
    return context['storage']['value']
    
def set_value(context, new_value):
    context['storage']['value'] = new_value
    return True
"""
    
    # Deploy Contract
    contract_id = contract_engine.deploy_contract(simple_contract, owner)
    
    # Überprüfe, ob der Contract korrekt gespeichert wurde
    assert contract_id in contract_engine.contracts
    assert contract_engine.contracts[contract_id]['owner'] == owner
    assert 'bytecode' in contract_engine.contracts[contract_id]
    
    # Überprüfe, ob der Initialzustand korrekt gesetzt wurde
    assert contract_id in contract_engine.contract_states
    assert contract_engine.contract_states[contract_id].owner == owner
    assert contract_engine.contract_states[contract_id].storage['value'] == 42


def test_contract_method_call(contract_engine):
    """Test, ob eine Contract-Methode korrekt aufgerufen werden kann"""
    owner = "test_owner_address"
    
    # Deploy einen einfachen Testcontract
    simple_contract = """
def constructor(context):
    context['storage']['value'] = 42
    
def get_value(context):
    return context['storage']['value']
    
def set_value(context, new_value):
    context['storage']['value'] = new_value
    return True
"""
    
    # Deploy Contract
    contract_id = contract_engine.deploy_contract(simple_contract, owner)
    
    # Rufe get_value auf
    result = contract_engine.call_contract(contract_id, "get_value", owner)
    assert result == 42
    
    # Rufe set_value auf
    set_result = contract_engine.call_contract(contract_id, "set_value", owner, [100])
    assert set_result == True
    
    # Überprüfe, ob der Wert geändert wurde
    new_result = contract_engine.call_contract(contract_id, "get_value", owner)
    assert new_result == 100


def test_owner_only_decorator(contract_engine):
    """Test des owner_only Decorators"""
    owner = "test_owner_address"
    non_owner = "another_address"
    
    # Contract mit owner_only Methode - include the decorator definition in the contract code
    contract_code = """
# Define the owner_only decorator inside the contract code
def owner_only(func):
    func._owner_only = True
    return func

def constructor(context):
    context['storage']['value'] = 42

def get_value(context):
    return context['storage']['value']

@owner_only
def admin_set_value(context, new_value):
    context['storage']['value'] = new_value
    return True
"""
    
    # Deploy Contract
    contract_id = contract_engine.deploy_contract(contract_code, owner)
    
    # Test normale Methode (kann von jedem aufgerufen werden)
    value = contract_engine.call_contract(contract_id, "get_value", non_owner)
    assert value == 42
    
    # Test owner_only Methode mit Owner
    result = contract_engine.call_contract(contract_id, "admin_set_value", owner, [100])
    assert result == True
    
    # Überprüfe, ob der Wert aktualisiert wurde
    value = contract_engine.call_contract(contract_id, "get_value", non_owner)
    assert value == 100
    
    # Test owner_only Methode mit Nicht-Owner (sollte fehlschlagen)
    try:
        contract_engine.call_contract(contract_id, "admin_set_value", non_owner, [200])
        assert False, "Non-owner should not be allowed to call owner_only method"
    except PermissionError:
        # Erwarteter Fehler
        pass
    
    # Überprüfe, dass der Wert nicht geändert wurde
    value = contract_engine.call_contract(contract_id, "get_value", non_owner)
    assert value == 100


def test_contract_state_persistence(contract_engine):
    """Test, ob der Contract-Zustand persistent ist"""
    owner = "test_owner_address"
    
    # Modified token contract with included owner_only decorator
    TOKEN_CONTRACT = """
# Define the owner_only decorator inside the contract code
def owner_only(func):
    func._owner_only = True
    return func

# Einfacher Token-Contract
def constructor(context):
    # Initialisiert den Token-Contract mit dem Namen, Symbol und Gesamtvorrat
    context['storage']['name'] = 'MyCoin Token'
    context['storage']['symbol'] = 'MCT'
    context['storage']['total_supply'] = 1000000
    context['storage']['balances'] = {context['owner']: context['storage']['total_supply']}

def name(context):
    # Gibt den Namen des Tokens zurück
    return context['storage']['name']

def symbol(context):
    # Gibt das Symbol des Tokens zurück
    return context['storage']['symbol']

def total_supply(context):
    # Gibt den Gesamtvorrat zurück
    return context['storage']['total_supply']

def balance_of(context, address):
    # Gibt das Guthaben einer Adresse zurück
    balances = context['storage']['balances']
    return balances.get(address, 0)

def transfer(context, to, amount):
    # Überträgt Tokens von der Senderadresse zur Zieladresse
    sender = context['sender']
    balances = context['storage']['balances']
    
    # Prüfen, ob der Sender genügend Balance hat
    if sender not in balances or balances[sender] < amount:
        return False
    
    # Überweisung durchführen
    if to not in balances:
        balances[to] = 0
    
    balances[sender] -= amount
    balances[to] += amount
    
    return True

@owner_only
def mint(context, address, amount):
    # Erstellt neue Tokens und weist sie einer Adresse zu (nur Owner)
    balances = context['storage']['balances']
    
    if address not in balances:
        balances[address] = 0
        
    balances[address] += amount
    context['storage']['total_supply'] += amount
    
    return True

@owner_only
def burn(context, address, amount):
    # Verbrennt Tokens einer Adresse (nur Owner)
    balances = context['storage']['balances']
    
    if address not in balances or balances[address] < amount:
        return False
        
    balances[address] -= amount
    context['storage']['total_supply'] -= amount
    
    return True
"""
    
    # Deploy Contract
    contract_id = contract_engine.deploy_contract(TOKEN_CONTRACT, owner)
    
    # Überprüfe initial state
    state = contract_engine.get_contract_state(contract_id)
    assert 'storage' in state
    assert 'name' in state['storage']
    assert state['storage']['name'] == 'MyCoin Token'
    assert state['storage']['total_supply'] == 1000000
    
    # Rufe contract.mint auf, um zusätzliche Tokens zu erstellen
    recipient = "test_recipient"
    contract_engine.call_contract(contract_id, "mint", owner, [recipient, 5000])
    
    # Überprüfe, ob der Zustand korrekt aktualisiert wurde
    state = contract_engine.get_contract_state(contract_id)
    assert state['storage']['total_supply'] == 1005000
    assert state['storage']['balances'][recipient] == 5000
    
    # Überprüfe, ob balanceof den korrekten Wert zurückgibt
    balance = contract_engine.call_contract(contract_id, "balance_of", recipient, [recipient])
    assert balance == 5000


def test_token_transfer(contract_engine):
    """Test einer Token-Übertragung im Beispiel-Contract"""
    owner = "test_owner_address"
    recipient = "recipient_address"
    
    # Deploy Contract
    contract_id = contract_engine.deploy_contract(EXAMPLE_TOKEN_CONTRACT, owner)
    
    # Überprüfe initial Guthaben
    initial_balance = contract_engine.call_contract(contract_id, "balance_of", owner, [owner])
    assert initial_balance == 1000000
    
    # Führe Transfer durch
    transfer_amount = 50000
    transfer_result = contract_engine.call_contract(
        contract_id, "transfer", owner, [recipient, transfer_amount]
    )
    assert transfer_result == True
    
    # Überprüfe Guthaben nach Transfer
    owner_balance = contract_engine.call_contract(contract_id, "balance_of", owner, [owner])
    recipient_balance = contract_engine.call_contract(contract_id, "balance_of", owner, [recipient])
    
    assert owner_balance == 1000000 - transfer_amount
    assert recipient_balance == transfer_amount


def test_contract_validation(contract_engine):
    """Test der Sicherheitsvalidierung von Contracts"""
    owner = "test_owner_address"
    
    # Contract mit potenziell gefährlichem Code
    malicious_contract = """
import os
def constructor(context):
    os.system('echo "This should not be executed"')
"""
    
    # Der Deploy sollte fehlschlagen
    with pytest.raises(ValueError):
        contract_engine.deploy_contract(malicious_contract, owner)


def test_blockchain_integration(blockchain, contract_engine):
    """Test der Integration zwischen Blockchain und Smart Contract Engine"""
    # Mock die blockchain.deploy_contract Methode, um unsere Engine zu verwenden
    blockchain.contract_engine = contract_engine
    
    owner = "test_owner_address"
    initial_balance = 10.0
    
    # Füge Guthaben zum Owner hinzu, damit er den Contract initialisieren kann
    blockchain.add_transaction("genesis", owner, 100.0)
    blockchain.mine_pending_transactions(owner)
    
    # Deploy Contract über die Blockchain
    contract_id = blockchain.deploy_contract(EXAMPLE_TOKEN_CONTRACT, owner, initial_balance)
    
    # Mine die Transaktion
    blockchain.mine_pending_transactions(owner)
    
    # Überprüfe, ob der Contract existiert
    assert contract_id in contract_engine.contracts
    
    # Rufe den Contract über die Blockchain auf
    name = blockchain.call_contract(contract_id, "name", owner)
    assert name == "MyCoin Token"
    
    # Überprüfe das Guthaben
    owner_tokens = blockchain.call_contract(contract_id, "balance_of", owner, [owner])
    assert owner_tokens == 1000000


def test_contract_state_retrieval(contract_engine):
    """Test, ob der Contract-Zustand korrekt abgerufen werden kann"""
    owner = "test_owner_address"
    
    # Deploy Contract
    contract_id = contract_engine.deploy_contract(EXAMPLE_TOKEN_CONTRACT, owner)
    
    # Hole den Zustand
    state = contract_engine.get_contract_state(contract_id)
    
    # Überprüfe die Struktur des Zustands
    assert 'storage' in state
    assert 'balance' in state
    assert 'owner' in state
    assert 'created_at' in state
    assert 'last_executed' in state
    
    # Überprüfe die Werte im Zustand
    assert state['owner'] == owner
    assert state['storage']['name'] == 'MyCoin Token'
    assert state['storage']['symbol'] == 'MCT'
    assert state['storage']['total_supply'] == 1000000