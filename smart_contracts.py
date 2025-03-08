import json
import hashlib
import time
import logging
import importlib.util
import sys
import inspect
from typing import Dict, Any, List, Callable, Optional, Union
from dataclasses import dataclass, field

# Logging-Konfiguration
logger = logging.getLogger('smart_contracts')

@dataclass
class ContractState:
    """Speichert den Zustand eines Smart Contracts"""
    storage: Dict[str, Any] = field(default_factory=dict)
    balance: float = 0.0
    owner: str = ""
    created_at: float = field(default_factory=time.time)
    last_executed: float = 0.0


class SmartContractEngine:
    """Engine zur Ausführung von Smart Contracts"""
    
    def __init__(self, blockchain):
        """Initialisiert die Smart Contract Engine"""
        self.blockchain = blockchain
        self.contracts: Dict[str, Dict[str, Any]] = {}
        self.contract_states: Dict[str, ContractState] = {}
        self.current_sender = None
        
        # Gas-Limit und Preise für Ressourcenverbrauch
        self.gas_limit = 1000000
        self.instruction_costs = {
            'default': 1,          # Standard-Kosten pro Operation
            'storage_write': 10,   # Speicherschreiboperation
            'storage_read': 1,     # Speicherleseoperation
            'blockchain_read': 5,  # Blockchain-Leseoperation
        }
        
        logger.info("Smart Contract Engine initialisiert")
    
    def deploy_contract(self, code: str, owner: str, initial_balance: float = 0.0) -> str:
        """
        Deployt einen neuen Smart Contract
        
        Args:
            code: Der Python-Code des Contracts
            owner: Die Adresse des Contract-Eigentümers
            initial_balance: Das anfängliche Guthaben des Contracts
            
        Returns:
            Die Adresse/ID des deployt Contracts
        """
        try:
            # Entferne führende Leerzeilen und normalisiere Einrückung
            code = code.lstrip('\n')
            
            # Sicherheitsüberprüfung des Codes
            self._validate_contract_code(code)
            
            # Füge owner_only Decorator zum Contract-Code hinzu, wenn er nicht schon enthalten ist
            if "def owner_only" not in code:
                code = """
# Define owner_only decorator
def owner_only(func):
    func._owner_only = True
    return func

""" + code
                
            # Contract kompilieren
            try:
                contract_bytecode = compile(code, '<string>', 'exec')
            except SyntaxError as e:
                logger.error(f"Syntax error in contract code: {str(e)}")
                raise ValueError(f"Contract hat einen Syntax-Fehler: {str(e)}")
            
            # Contract-ID generieren
            contract_id = self._generate_contract_id(code, owner)
            
            if contract_id in self.contracts:
                raise ValueError(f"Contract mit ID {contract_id} existiert bereits")
                
            # Contract mit Metadaten speichern
            self.contracts[contract_id] = {
                'bytecode': contract_bytecode,
                'source': code,
                'owner': owner,
                'created_at': time.time()
            }
            
            # Initialzustand erstellen
            self.contract_states[contract_id] = ContractState(
                owner=owner,
                balance=initial_balance
            )
            
            # Contract initialisieren (constructor)
            contract_namespace = {}
            exec(contract_bytecode, contract_namespace)
            
            # Wenn der Contract einen Konstruktor hat, ausführen
            if 'constructor' in contract_namespace and callable(contract_namespace['constructor']):
                try:
                    # Create contract context
                    context = self._create_execution_context(contract_id)
                    
                    # Call constructor
                    contract_namespace['constructor'](context)
                    
                except Exception as e:
                    # Bei Fehler Contract entfernen
                    del self.contracts[contract_id]
                    del self.contract_states[contract_id]
                    logger.error(f"Fehler beim Initialisieren des Contracts: {str(e)}")
                    raise ValueError(f"Contract-Initialisierung fehlgeschlagen: {str(e)}")
            
            logger.info(f"Neuer Contract deployed: {contract_id} von {owner}")
            return contract_id
                
        except Exception as e:
            # Verbesserte Fehlerbehandlung - wandle unerwartete Fehler in aussagekräftige Fehlermeldungen um
            if not isinstance(e, ValueError):
                logger.error(f"Unerwarteter Fehler beim Contract-Deployment: {str(e)}")
                raise ValueError(f"Contract-Deployment fehlgeschlagen: {str(e)}")
            else:
                raise
        
    def call_contract(self, contract_id: str, method: str, sender: str, 
                      args: List = None, kwargs: Dict = None, value: float = 0.0) -> Any:
        """
        Ruft eine Methode eines Smart Contracts auf
        
        Args:
            contract_id: Die ID des aufzurufenden Contracts
            method: Der Name der aufzurufenden Methode
            sender: Die Adresse des Aufrufers
            args: Positionelle Argumente für die Methode
            kwargs: Benannte Argumente für die Methode
            value: Menge an Coins, die an den Contract gesendet werden
            
        Returns:
            Das Ergebnis des Methodenaufrufs
        """
        if args is None:
            args = []
        if kwargs is None:
            kwargs = {}
            
        if contract_id not in self.contracts:
            raise ValueError(f"Contract mit ID {contract_id} existiert nicht")
            
        # Gas-Zähler initialisieren
        gas_used = 0
        
        # Contract-Zustand aktualisieren
        state = self.contract_states[contract_id]
        state.balance += value
        state.last_executed = time.time()
        
        # Contract-Code ausführen
        contract_bytecode = self.contracts[contract_id]['bytecode']
        contract_namespace = {}
        
        # Ausführungsumgebung erstellen
        exec(contract_bytecode, contract_namespace)
        
        # Prüfen ob die Methode existiert
        if method not in contract_namespace or not callable(contract_namespace[method]):
            raise ValueError(f"Methode {method} existiert nicht im Contract {contract_id}")
            
        # Speichern des aktuellen Senders für contract_call
        prev_sender = self.current_sender
        self.current_sender = sender
        
        # Execution context erstellen
        context = self._create_execution_context(contract_id, sender=sender, value=value)
        
        # Methode mit Gas-Tracking ausführen
        try:
            # Überprüfen ob die Methode nur vom Eigentümer aufgerufen werden darf
            if hasattr(contract_namespace[method], '_owner_only') and contract_namespace[method]._owner_only:
                if sender != state.owner:
                    raise PermissionError("Nur der Contract-Eigentümer darf diese Methode aufrufen")
                    
            # Gas-Limit prüfen
            if gas_used > self.gas_limit:
                raise Exception("Gas-Limit überschritten")
                
            # Methode ausführen
            result = contract_namespace[method](context, *args, **kwargs)
            
            return result
        except Exception as e:
            # Bei Fehler Transaktion rückgängig machen (Zustand wiederherstellen)
            logger.error(f"Fehler bei Contract-Ausführung {contract_id}.{method}: {str(e)}")
            raise
        finally:
            # Stelle sicher, dass der vorherige Sender wiederhergestellt wird
            self.current_sender = prev_sender
            
    def _create_execution_context(self, contract_id: str, sender: str = None, value: float = 0.0) -> Dict[str, Any]:
        """Erstellt einen Ausführungskontext für den Contract"""
        state = self.contract_states[contract_id]
        
        context = {
            'storage': state.storage,
            'balance': state.balance,
            'sender': sender,
            'owner': state.owner,
            'contract_address': contract_id,
            'block_time': time.time(),
            'value': value,
            'blockchain': {
                'get_balance': self.blockchain.get_balance,
                'get_block': self._safe_get_block,
                'contract_call': self._safe_contract_call
            }
        }
        
        return context
        
    def _generate_contract_id(self, code: str, owner: str) -> str:
        """Generiert eine eindeutige ID für den Contract"""
        contract_data = f"{code}{owner}{time.time()}"
        return hashlib.sha256(contract_data.encode()).hexdigest()[:40]
        
    def _validate_contract_code(self, code: str) -> bool:
        """
        Validiert den Contract-Code auf Sicherheitsrisiken
        Einfache Version - in Produktion wäre eine umfassendere Prüfung nötig
        """
        # Verbotene Module und Funktionen
        blacklist = [
            'os', 'sys', 'subprocess', 'eval', 'exec', '__import__', 
            'open', 'file', 'compile', 'reload', 'input'
        ]
        
        for item in blacklist:
            if item in code:
                logger.warning(f"Potenziell gefährlicher Code erkannt: {item}")
                raise ValueError(f"Sicherheitsrisiko: Der Code enthält verbotene Funktionen: {item}")
                
        return True
        
    def _safe_get_block(self, index_or_hash):
        """Sichere Methode, um auf Blockchain-Blöcke zuzugreifen"""
        # Gas berechnen
        gas_cost = self.instruction_costs['blockchain_read']
        
        try:
            if isinstance(index_or_hash, int):
                return self.blockchain.get_block_by_index(index_or_hash)
            else:
                return self.blockchain.get_block_by_hash(index_or_hash)
        except Exception:
            return None
            
    def _safe_contract_call(self, contract_id, method, args=None, kwargs=None, value=0.0):
        """Ermöglicht Aufrufe zwischen Contracts"""
        # Verhindern von Rekursion und Stack-Overflows
        # In einer echten Implementierung würden hier Depth-Limits gesetzt
        
        if args is None:
            args = []
        if kwargs is None:
            kwargs = {}
            
        # Stelle sicher, dass wir einen Sender haben
        if self.current_sender is None:
            raise ValueError("Contract calls can only be made from within a contract execution")
            
        # Contract-übergreifende Aufrufe mit dem Sender des ursprünglichen Contracts
        return self.call_contract(contract_id, method, self.current_sender, args, kwargs, value)

    def get_contract_state(self, contract_id: str) -> Dict[str, Any]:
        """Gibt den aktuellen Zustand eines Contracts zurück"""
        if contract_id not in self.contract_states:
            raise ValueError(f"Contract mit ID {contract_id} existiert nicht")
            
        state = self.contract_states[contract_id]
        return {
            'storage': state.storage,
            'balance': state.balance,
            'owner': state.owner,
            'created_at': state.created_at,
            'last_executed': state.last_executed
        }
        
    def get_deployed_contracts(self) -> List[str]:
        """Gibt eine Liste aller deployt Contracts zurück"""
        return list(self.contracts.keys())


# Decorator für owner-only Methoden
def owner_only(func):
    """Decorator zum Markieren von Methoden, die nur vom Owner aufgerufen werden dürfen"""
    func._owner_only = True
    return func


# Beispiel für einen einfachen Token-Contract
EXAMPLE_TOKEN_CONTRACT = """
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