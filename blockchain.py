import hashlib
import json
import time
import threading
import logging
import pickle
import os
import requests
from typing import List, Dict, Any, Callable, Optional, Set, Union, Tuple

# Konfiguration des Loggings
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='blockchain.log',
    filemode='a'
)
logger = logging.getLogger('blockchain')


class MerkleTree:
    """
    Implementierung eines Merkle Trees für effiziente und sichere Verifikation von Transaktionen
    """
    @staticmethod
    def create_merkle_root(transactions: List[Dict[str, Any]]) -> str:
        """
        Erstellt einen Merkle Root Hash aus einer Liste von Transaktionen
        """
        if not transactions:
            return hashlib.sha256(b"").hexdigest()
            
        # Konvertiere Transaktionen in Hashes
        tx_hashes = [hashlib.sha256(json.dumps(tx, sort_keys=True).encode()).hexdigest() for tx in transactions]
        
        # Baue den Merkle Tree auf
        while len(tx_hashes) > 1:
            # Stelle sicher, dass die Anzahl der Hashes gerade ist
            if len(tx_hashes) % 2 != 0:
                tx_hashes.append(tx_hashes[-1])
                
            # Kombiniere je zwei benachbarte Hashes
            next_level = []
            for i in range(0, len(tx_hashes), 2):
                combined = tx_hashes[i] + tx_hashes[i+1]
                next_level.append(hashlib.sha256(combined.encode()).hexdigest())
                
            tx_hashes = next_level
            
        # Der letzte übrige Hash ist der Merkle Root
        return tx_hashes[0]
    
    @staticmethod
    def verify_transaction(tx: Dict[str, Any], merkle_root: str, transactions: List[Dict[str, Any]]) -> bool:
        """
        Verifiziert, ob eine Transaktion im Merkle Tree enthalten ist
        """
        # In einer vollständigen Implementierung würde hier ein Merkle Proof erstellt und validiert
        # Für diese Demo vereinfacht:
        return merkle_root == MerkleTree.create_merkle_root(transactions)


class Block:
    def __init__(self, index: int, timestamp: float, transactions: List[Dict[str, Any]], 
                 previous_hash: str, nonce: int = 0):
        self.index = index
        self.timestamp = timestamp
        self.transactions = transactions
        self.previous_hash = previous_hash
        self.nonce = nonce
        self.merkle_root = MerkleTree.create_merkle_root(transactions)
        self.hash = self.calculate_hash()
        self.difficulty = 0  # Wird vom Blockchain-Objekt gesetzt

    def calculate_hash(self) -> str:
        """
        Calculate SHA-256 hash of the block
        """
        block_string = json.dumps({
            "index": self.index,
            "timestamp": self.timestamp,
            "merkle_root": self.merkle_root,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce
        }, sort_keys=True).encode()
        
        return hashlib.sha256(block_string).hexdigest()
    
    def mine_block(self, difficulty: int) -> None:
        """
        Mine a new block (Proof of Work)
        """
        self.difficulty = difficulty
        target = '0' * difficulty
        
        # Performance-Optimierung durch effizienteres Hashing
        while self.hash[:difficulty] != target:
            self.nonce += 1
            if self.nonce % 100000 == 0:
                # Periodisches Logging für längere Mining-Prozesse
                logger.info(f"Mining Block #{self.index}: Nonce at {self.nonce}, target difficulty {difficulty}")
            self.hash = self.calculate_hash()
            
        logger.info(f"Block #{self.index} mined with nonce {self.nonce}: {self.hash}")
        print(f"Block #{self.index} mined: {self.hash}")


class Blockchain:
    # Fest definierter Genesis-Block für Konsistenz zwischen Nodes
    GENESIS_TIMESTAMP = 1684792800.0  # Ein fester Zeitpunkt (z.B. 23. Mai 2023 00:00:00 UTC)
    GENESIS_MESSAGE = "Genesis Block - First block in the chain"
    GENESIS_PREV_HASH = "0"
    GENESIS_NONCE = 0
    
    # Erhöhe die Standardschwierigkeit auf 6, damit Blöcke nicht so schnell gefunden werden
    DEFAULT_DIFFICULTY = 6

    def __init__(self, difficulty: int = DEFAULT_DIFFICULTY):
        self.chain: List[Block] = []
        self.difficulty = difficulty
        self.pending_transactions: List[Dict[str, Any]] = []
        self.mining_reward = 100
        self._mining_thread: Optional[threading.Thread] = None
        self._stop_mining = threading.Event()
        self.mining_callback: Optional[Callable] = None
        self._sync_callback: Optional[Callable] = None
        
        # Double-Spend-Prävention
        self._processed_tx_ids: Set[str] = set()
        
        # Auto-adjust difficulty parameters
        self.target_block_time = 60  # Target time in seconds between blocks
        self.difficulty_adjustment_interval = 10  # Adjust difficulty every 10 blocks
        self.last_difficulty_adjustment_time = time.time()
        
        # Smart Contract Engine hinzufügen (wird später initialisiert)
        self.contract_engine = None
        
        # Checkpoint-bezogene Attribute
        self.checkpoint_file = "blockchain_checkpoint.pkl"
        self.checkpoint_metadata_file = "blockchain_checkpoint_meta.json"
        self.is_paused = False
        self.pause_timestamp = None
        self.checkpoint_logger = logging.getLogger('blockchain.checkpoint')
        
        # Create the genesis block
        self.create_genesis_block()
        
        logger.info(f"Blockchain initialized with difficulty {difficulty}")

    def create_checkpoint(self, reason: str = "Manual checkpoint") -> bool:
        """
        Erstellt einen Checkpoint des aktuellen Blockchain-Zustands
        
        Args:
            reason: Grund für den Checkpoint (z.B. "Update", "Backup")
            
        Returns:
            True bei Erfolg, False bei Fehler
        """
        try:
            self.checkpoint_logger.info(f"Erstelle Checkpoint: {reason}")
            
            # Metadaten zum Checkpoint
            metadata = {
                "timestamp": time.time(),
                "reason": reason,
                "chain_length": len(self.chain),
                "difficulty": self.difficulty,
                "pending_transactions": len(self.pending_transactions),
                "blockchain_hash": self._calculate_blockchain_hash(),
                "version": "1.0"  # Versionsinfo für zukünftige Kompatibilität
            }
            
            # Speichern der Metadaten
            with open(self.checkpoint_metadata_file, 'w') as meta_file:
                json.dump(metadata, meta_file, indent=2)
            
            # Blockchain-Zustand speichern mit pickle
            # Das enthält: chain, pending_transactions, _processed_tx_ids, etc.
            with open(self.checkpoint_file, 'wb') as checkpoint_file:
                pickle.dump({
                    'chain': self.chain,
                    'pending_transactions': self.pending_transactions,
                    'processed_tx_ids': self._processed_tx_ids,
                    'difficulty': self.difficulty,
                    'mining_reward': self.mining_reward,
                    'target_block_time': self.target_block_time,
                    'last_difficulty_adjustment_time': self.last_difficulty_adjustment_time
                }, checkpoint_file)
                
            self.checkpoint_logger.info(f"Checkpoint erfolgreich erstellt: {len(self.chain)} Blöcke")
            print(f"Checkpoint erfolgreich erstellt: {len(self.chain)} Blöcke")
            return True
            
        except Exception as e:
            self.checkpoint_logger.error(f"Fehler beim Erstellen des Checkpoints: {str(e)}")
            print(f"Fehler beim Erstellen des Checkpoints: {str(e)}")
            return False

    def _calculate_blockchain_hash(self) -> str:
        """
        Berechnet einen Hash über die gesamte Blockchain für Integritätsprüfungen
        """
        combined_hashes = "".join([block.hash for block in self.chain])
        return hashlib.sha256(combined_hashes.encode()).hexdigest()
    
    def load_checkpoint(self, validate: bool = True) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Lädt einen gespeicherten Checkpoint und stellt die Blockchain wieder her
        
        Args:
            validate: Bei True wird nach dem Laden eine vollständige Validierung durchgeführt
            
        Returns:
            (Erfolg, Metadaten) - Tupel mit bool und Checkpoint-Metadaten oder None bei Fehler
        """
        if not os.path.exists(self.checkpoint_file) or not os.path.exists(self.checkpoint_metadata_file):
            self.checkpoint_logger.warning("Keine Checkpoint-Dateien gefunden")
            return False, None
            
        try:
            # Metadaten laden
            with open(self.checkpoint_metadata_file, 'r') as meta_file:
                metadata = json.load(meta_file)
                
            # Blockchain-Zustand laden
            with open(self.checkpoint_file, 'rb') as checkpoint_file:
                state = pickle.load(checkpoint_file)
                
            # Blockchain-Zustand wiederherstellen
            self.chain = state['chain']
            self.pending_transactions = state['pending_transactions']
            self._processed_tx_ids = state['processed_tx_ids']
            self.difficulty = state['difficulty']
            self.mining_reward = state['mining_reward']
            self.target_block_time = state['target_block_time']
            self.last_difficulty_adjustment_time = state['last_difficulty_adjustment_time']
            
            self.checkpoint_logger.info(f"Checkpoint geladen: {len(self.chain)} Blöcke, " 
                                        f"erstellt am {time.ctime(metadata['timestamp'])}")
            print(f"Checkpoint geladen: {len(self.chain)} Blöcke")
            
            # Optional: Validierung durchführen
            if validate:
                is_valid, issues = self.comprehensive_validation()
                if not is_valid:
                    self.checkpoint_logger.error(f"Validierungsfehler nach Checkpoint-Wiederherstellung: {issues}")
                    print(f"WARNUNG: Validierungsfehler nach Wiederherstellung: {issues}")
                else:
                    self.checkpoint_logger.info("Checkpoint-Validierung erfolgreich")
                    print("Checkpoint-Validierung erfolgreich")
            
            return True, metadata
            
        except Exception as e:
            self.checkpoint_logger.error(f"Fehler beim Laden des Checkpoints: {str(e)}")
            print(f"Fehler beim Laden des Checkpoints: {str(e)}")
            return False, None
    
    def pause_blockchain(self, reason: str = "Pausiert für Wartung") -> bool:
        """
        Pausiert die Blockchain sicher für Updates oder Wartung
        
        Args:
            reason: Grund für die Pause
            
        Returns:
            True bei Erfolg, False bei Fehler
        """
        if self.is_paused:
            print("Blockchain ist bereits pausiert")
            return False
            
        try:
            # Mining stoppen
            if self._mining_thread and self._mining_thread.is_alive():
                self.stop_continuous_mining()
                
            # Checkpoint erstellen
            checkpoint_success = self.create_checkpoint(reason)
            if not checkpoint_success:
                return False
                
            self.is_paused = True
            self.pause_timestamp = time.time()
            
            self.checkpoint_logger.info(f"Blockchain pausiert: {reason}")
            print(f"Blockchain erfolgreich pausiert: {reason}")
            return True
            
        except Exception as e:
            self.checkpoint_logger.error(f"Fehler beim Pausieren der Blockchain: {str(e)}")
            print(f"Fehler beim Pausieren der Blockchain: {str(e)}")
            return False
    
    def resume_blockchain(self, validate: bool = True) -> bool:
        """
        Setzt eine pausierte Blockchain fort
        
        Args:
            validate: Bei True wird eine Validierung durchgeführt
            
        Returns:
            True bei Erfolg, False bei Fehler
        """
        if not self.is_paused and self.pause_timestamp is None:
            # Wenn keine explizite Pause vorliegt, versuchen wir trotzdem den Checkpoint zu laden
            success, metadata = self.load_checkpoint(validate)
            if success:
                print("Blockchain aus Checkpoint wiederhergestellt")
                return True
            else:
                print("Kein Checkpoint gefunden und Blockchain war nicht pausiert")
                return False
                
        try:
            # Checkpoint laden
            success, metadata = self.load_checkpoint(validate)
            if not success:
                print("Fehler beim Laden des Checkpoints")
                return False
                
            self.is_paused = False
            self.pause_timestamp = None
            
            pause_duration = time.time() - metadata['timestamp']
            self.checkpoint_logger.info(f"Blockchain fortgesetzt nach {pause_duration:.1f} Sekunden")
            print(f"Blockchain erfolgreich fortgesetzt (Pausiert für {pause_duration:.1f} Sekunden)")
            return True
            
        except Exception as e:
            self.checkpoint_logger.error(f"Fehler beim Fortsetzen der Blockchain: {str(e)}")
            print(f"Fehler beim Fortsetzen der Blockchain: {str(e)}")
            return False

    def comprehensive_validation(self) -> Tuple[bool, List[str]]:
        """
        Führt eine umfassende Validierung der Blockchain durch
        
        Returns:
            (Gültig, Probleme) - Tupel mit Validitätsstatus und Liste von gefundenen Problemen
        """
        issues = []
        
        # 1. Ketten-Integrität (bereits implementierte Methode nutzen)
        if not self.is_chain_valid():
            issues.append("Blockchain-Integritätsprüfung fehlgeschlagen")
            return False, issues
            
        # 2. Zusätzliche Prüfungen für jeden Block
        for i, block in enumerate(self.chain):
            # 2.1 Block-Index-Kontinuität prüfen
            if block.index != i:
                issues.append(f"Block {i} hat falschen Index: {block.index}")
                
            # 2.2 Block-Zeitstempel plausibel?
            if i > 0:
                prev_block = self.chain[i-1]
                if block.timestamp < prev_block.timestamp:
                    issues.append(f"Block {i} hat Zeitstempel vor vorherigem Block")
                    
            # 2.3 Merkle-Root-Konsistenz mit Transaktionen
            expected_merkle_root = MerkleTree.create_merkle_root(block.transactions)
            if block.merkle_root != expected_merkle_root:
                issues.append(f"Block {i} hat inkonsistenten Merkle-Root")
                
            # 2.4 Hash entspricht dem Block-Inhalt
            expected_hash = block.calculate_hash()
            if block.hash != expected_hash:
                issues.append(f"Block {i} hat inkonsistenten Hash")
                
        # 3. Guthaben-Konsistenz prüfen
        balance_map = {}
        for block in self.chain:
            for tx in block.transactions:
                sender = tx["from"]
                recipient = tx["to"]
                amount = tx["amount"]
                
                # Initialisiere Konten falls nicht vorhanden
                if sender not in balance_map:
                    balance_map[sender] = 0
                if recipient not in balance_map:
                    balance_map[recipient] = 0
                    
                # Transaktion anwenden
                if sender != "network" and sender != "genesis":  # Diese dürfen ins Negative gehen
                    balance_map[sender] -= amount
                balance_map[recipient] += amount
                
                # Prüfen auf negative Bilanzen (außer bei Systemadressen)
                if sender != "network" and sender != "genesis" and balance_map[sender] < 0:
                    issues.append(f"Negativer Kontostand für {sender} nach Transaktion in Block {block.index}")
        
        # Wenn Probleme gefunden wurden, ist die Validierung fehlgeschlagen
        if issues:
            return False, issues
            
        return True, []
     
    def create_genesis_block(self) -> None:
        """
        Create the first block in the chain with deterministic values
        """
        # Prüfe, ob bereits ein Chain-Checkpoint existiert
        if os.path.exists(self.checkpoint_file) and os.path.exists(self.checkpoint_metadata_file):
            success, _ = self.load_checkpoint(validate=False)
            if success:
                logger.info("Genesis block loaded from checkpoint")
                return
                
        # Erstelle einen deterministischen Genesis-Block (immer gleicher Inhalt)
        genesis_transactions = [{
            "from": "genesis",
            "to": "network",
            "amount": 0,
            "timestamp": self.GENESIS_TIMESTAMP,
            "message": self.GENESIS_MESSAGE
        }]
        
        # Verwende feste Parameter für den Genesis-Block
        genesis_block = Block(0, self.GENESIS_TIMESTAMP, genesis_transactions, self.GENESIS_PREV_HASH, self.GENESIS_NONCE)
        
        # Berechne den Hash manuell (ohne Mining)
        genesis_block.hash = genesis_block.calculate_hash()
        genesis_block.difficulty = self.difficulty
        
        # In die Kette einfügen
        self.chain.append(genesis_block)
        logger.info(f"Genesis block created: {genesis_block.hash}")
        
        # Optional: Checkpoint erstellen, damit neue Nodes dieselbe Chain haben
        self.create_checkpoint("Initial genesis block")
        
    def get_latest_block(self) -> Block:
        """
        Return the most recent block in the chain
        """
        return self.chain[-1]
    
    def generate_transaction_id(self, transaction: Dict[str, Any]) -> str:
        """
        Generate a unique ID for a transaction to prevent double-spending
        """
        tx_data = json.dumps(transaction, sort_keys=True).encode()
        return hashlib.sha256(tx_data).hexdigest()
    
    def mine_pending_transactions(self, miner_address: str) -> Block:
        """
        Create a new block with all pending transactions and mine it
        """
        if not self.pending_transactions:
            logger.debug("No transactions to mine")
            # In continuous mining, create at least the reward transaction
            self.pending_transactions.append({
                "from": "network",
                "to": miner_address,
                "amount": self.mining_reward,
                "timestamp": time.time(),
                "type": "reward"
            })
        else:
            # Create reward transaction for the miner
            self.pending_transactions.append({
                "from": "network",
                "to": miner_address,
                "amount": self.mining_reward,
                "timestamp": time.time(),
                "type": "reward"
            })
        
        # Create new block and mine it
        block = Block(
            index=len(self.chain),
            timestamp=time.time(),
            transactions=self.pending_transactions.copy(),  # Make a copy to avoid race conditions
            previous_hash=self.get_latest_block().hash
        )
        
        # Add transaction IDs to processed set to prevent double-spending
        for tx in self.pending_transactions:
            tx_id = self.generate_transaction_id(tx)
            self._processed_tx_ids.add(tx_id)
        
        # Begrenzen der Größe von _processed_tx_ids, um Speicherverbrauch zu kontrollieren
        if len(self._processed_tx_ids) > 10000:
            # Behalte nur die letzten 5000 Transaktionen
            self._processed_tx_ids = set(list(self._processed_tx_ids)[-5000:])
            
        block.mine_block(self.difficulty)
        
        # Add the newly mined block to the chain
        self.chain.append(block)
        
        # Reset the pending transactions
        self.pending_transactions = []
        
        # Check if we need to adjust difficulty
        self._adjust_difficulty()
        
        return block
    
    def _adjust_difficulty(self) -> None:
        """Adjust mining difficulty based on block time"""
        if len(self.chain) % self.difficulty_adjustment_interval != 0:
            return
            
        current_time = time.time()
        expected_time = self.target_block_time * self.difficulty_adjustment_interval
        actual_time = current_time - self.last_difficulty_adjustment_time
        
        # Adjust difficulty based on difference between expected and actual mining time
        if actual_time < expected_time / 2:
            self.difficulty += 1
            logger.info(f"Mining too fast. Increased difficulty to {self.difficulty}")
            print(f"Mining too fast. Increased difficulty to {self.difficulty}")
        elif actual_time > expected_time * 2:
            if self.difficulty > 1:
                self.difficulty -= 1
                logger.info(f"Mining too slow. Decreased difficulty to {self.difficulty}")
                print(f"Mining too slow. Decreased difficulty to {self.difficulty}")
        
        self.last_difficulty_adjustment_time = current_time
        
    def start_continuous_mining(self, miner_address: str, callback: Optional[Callable] = None, sync_callback: Optional[Callable] = None) -> None:
        """
        Start continuous mining in a background thread
        
        Args:
            miner_address: Address to receive mining rewards
            callback: Optional callback function called when a new block is mined
            sync_callback: Optional callback to synchronize with network before mining
        """
        if self._mining_thread and self._mining_thread.is_alive():
            logger.warning("Mining already in progress")
            print("Mining already in progress")
            return
            
        self._stop_mining.clear()
        self.mining_callback = callback
        self._sync_callback = sync_callback
        
        def mining_thread():
            logger.info(f"Starting continuous mining with difficulty {self.difficulty}")
            print(f"Starting continuous mining with difficulty {self.difficulty}")
            print(f"Mining rewards will be sent to {miner_address}")
            
            while not self._stop_mining.is_set():
                try:
                    # WICHTIG: Vor jedem Mining-Versuch mit dem Netzwerk synchronisieren
                    if self._sync_callback:
                        # Wenn eine Sync-Funktion übergeben wurde, rufe sie auf
                        # Dies ermöglicht dem Node die Synchronisierung mit dem Netzwerk
                        logger.debug("Syncing with network before mining...")
                        synced = self._sync_callback()
                        if synced:
                            logger.debug("Blockchain synced with network")
                            # Nach einer Synchronisierung kurz warten, um Race Conditions zu vermeiden
                            time.sleep(0.5)
                    
                    # If no pending transactions, create a dummy one to keep mining
                    if not self.pending_transactions:
                        self.add_transaction("network", miner_address, 0, {"type": "empty"})
                        
                    # Mine a block
                    block = self.mine_pending_transactions(miner_address)
                    
                    # Call the callback if provided
                    if self.mining_callback:
                        self.mining_callback(block)
                        
                    # Small delay to prevent CPU overuse and give chance for blockchain sync
                    # This delay also helps with reducing race conditions between nodes
                    time.sleep(0.5)
                except Exception as e:
                    logger.error(f"Error in mining thread: {str(e)}")
                    print(f"Mining error: {str(e)}")
                    time.sleep(5)  # Pause bei Fehler
                
        self._mining_thread = threading.Thread(target=mining_thread)
        self._mining_thread.daemon = True
        self._mining_thread.start()
        
    def stop_continuous_mining(self) -> None:
        """Stop the continuous mining thread"""
        if not self._mining_thread or not self._mining_thread.is_alive():
            logger.warning("No mining in progress")
            print("No mining in progress")
            return
            
        logger.info("Stopping mining...")
        print("Stopping mining...")
        self._stop_mining.set()
        self._mining_thread.join(timeout=2.0)
        logger.info("Mining stopped")
        print("Mining stopped")
        
    def add_transaction(self, sender: str, recipient: str, amount: float, metadata: Optional[Dict[str, Any]] = None) -> Union[str, bool]:
        """
        Add a new transaction to the list of pending transactions
        Returns transaction ID on success, False on failure
        """
        if amount < 0:
            logger.warning(f"Rejected negative amount transaction: {amount}")
            return False
            
        if sender != "network" and sender != "genesis":  # Network and genesis can create coins
            # Check if sender has enough balance
            balance = self.get_balance(sender)
            if balance < amount:
                logger.warning(f"Rejected transaction from {sender}: insufficient funds")
                return False
        
        transaction = {
            "from": sender,
            "to": recipient,
            "amount": amount,
            "timestamp": time.time()
        }
        
        # Add additional metadata if provided
        if metadata:
            for key, value in metadata.items():
                transaction[key] = value
                
        # Generate transaction ID
        tx_id = self.generate_transaction_id(transaction)
        
        # Check for double spending
        if tx_id in self._processed_tx_ids:
            logger.warning(f"Rejected duplicate transaction: {tx_id}")
            return False
            
        # Add transaction ID to the transaction
        transaction["id"] = tx_id
        
        self.pending_transactions.append(transaction)
        logger.info(f"Added transaction: {tx_id} - {sender} -> {recipient}: {amount}")
        
        return tx_id
    
    def get_balance(self, address: str) -> float:
        """
        Calculate the balance of a given address
        """
        balance = 0
        
        # Check all blocks in the blockchain
        for block in self.chain:
            for transaction in block.transactions:
                if transaction["from"] == address:
                    balance -= transaction["amount"]
                if transaction["to"] == address:
                    balance += transaction["amount"]
                    
        return balance
    
    def is_chain_valid(self) -> bool:
        """
        Check if the blockchain is valid
        """
        for i in range(1, len(self.chain)):
            current_block = self.chain[i]
            previous_block = self.chain[i - 1]
            
            # Check if the current block's hash is correct
            if current_block.hash != current_block.calculate_hash():
                logger.error(f"Invalid hash in block {i}")
                return False
            
            # Check if the current block points to the correct previous hash
            if current_block.previous_hash != previous_block.hash:
                logger.error(f"Invalid previous hash in block {i}")
                return False
                
            # Verify the merkle root
            if current_block.merkle_root != MerkleTree.create_merkle_root(current_block.transactions):
                logger.error(f"Invalid merkle root in block {i}")
                return False
            
            # Verify the proof of work
            if current_block.hash[:current_block.difficulty] != '0' * current_block.difficulty:
                logger.error(f"Invalid proof of work in block {i}")
                return False
        
        logger.info("Blockchain validation complete: valid")
        return True
        
    def set_difficulty(self, difficulty: int) -> None:
        """Set the mining difficulty manually"""
        if difficulty < 1:
            difficulty = 1
        self.difficulty = difficulty
        logger.info(f"Mining difficulty set to {self.difficulty}")
        print(f"Mining difficulty set to {self.difficulty}")
        
    def get_mining_stats(self) -> Dict[str, Any]:
        """Get current mining statistics"""
        stats = {
            "difficulty": self.difficulty,
            "chain_length": len(self.chain),
            "pending_transactions": len(self.pending_transactions),
            "mining_active": self._mining_thread is not None and self._mining_thread.is_alive(),
            "target_block_time": self.target_block_time,
            "last_block_time": time.time() - self.chain[-1].timestamp if len(self.chain) > 0 else 0
        }
        logger.debug(f"Mining stats: {stats}")
        return stats
        
    def get_block_by_hash(self, block_hash: str) -> Optional[Block]:
        """Get a block by its hash"""
        for block in self.chain:
            if block.hash == block_hash:
                return block
        return None
        
    def get_block_by_index(self, index: int) -> Optional[Block]:
        """Get a block by its index"""
        if 0 <= index < len(self.chain):
            return self.chain[index]
        return None
        
    def get_transaction_history(self, address: str) -> List[Dict[str, Any]]:
        """Get all transactions involving the given address"""
        transactions = []
        for block in self.chain:
            for tx in block.transactions:
                if tx["from"] == address or tx["to"] == address:
                    tx_copy = tx.copy()
                    tx_copy["block"] = block.index
                    tx_copy["confirmed_time"] = block.timestamp
                    transactions.append(tx_copy)
        return transactions
        
    def initialize_contract_engine(self):
        """Initialisiert die Smart Contract Engine"""
        # Import here to avoid circular imports
        from smart_contracts import SmartContractEngine
        
        if self.contract_engine is None:
            self.contract_engine = SmartContractEngine(self)
            logger.info("Smart Contract Engine initialisiert")
            
        return self.contract_engine
    
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
        # Stelle sicher, dass die Contract Engine initialisiert ist
        if self.contract_engine is None:
            self.initialize_contract_engine()
            
        # Prüfe, ob der Owner genug Guthaben hat (falls initial_balance > 0)
        if initial_balance > 0:
            owner_balance = self.get_balance(owner)
            if owner_balance < initial_balance:
                raise ValueError(f"Unzureichendes Guthaben: {owner} hat nur {owner_balance}, benötigt {initial_balance}")
                
            # Füge eine Transaktion hinzu, um das Guthaben zum Contract zu übertragen
            contract_id = self.contract_engine._generate_contract_id(code, owner)
            self.add_transaction(
                sender=owner,
                recipient=contract_id,
                amount=initial_balance,
                metadata={"type": "contract_creation"}
            )
            
        # Deploye den Contract
        contract_id = self.contract_engine.deploy_contract(code, owner, initial_balance)
        logger.info(f"Smart Contract deployed: {contract_id}")
        
        return contract_id
        
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
        # Stelle sicher, dass die Contract Engine initialisiert ist
        if self.contract_engine is None:
            self.initialize_contract_engine()
            
        # Prüfe, ob der Sender genug Guthaben hat (falls value > 0)
        if value > 0:
            sender_balance = self.get_balance(sender)
            if sender_balance < value:
                raise ValueError(f"Unzureichendes Guthaben: {sender} hat nur {sender_balance}, benötigt {value}")
                
            # Füge eine Transaktion hinzu, um das Guthaben zum Contract zu übertragen
            self.add_transaction(
                sender=sender,
                recipient=contract_id,
                amount=value,
                metadata={"type": "contract_call", "method": method}
            )
            
        # Rufe den Contract auf
        result = self.contract_engine.call_contract(contract_id, method, sender, args, kwargs, value)
        logger.info(f"Smart Contract aufgerufen: {contract_id}.{method} von {sender}")
        
        return result
        
    def get_contract_state(self, contract_id: str) -> Dict[str, Any]:
        """
        Gibt den aktuellen Zustand eines Contracts zurück
        
        Args:
            contract_id: Die ID des Contracts
            
        Returns:
            Der Zustand des Contracts
        """
        # Stelle sicher, dass die Contract Engine initialisiert ist
        if self.contract_engine is None:
            self.initialize_contract_engine()
            
        return self.contract_engine.get_contract_state(contract_id)
        
    def get_deployed_contracts(self) -> List[str]:
        """
        Gibt eine Liste aller deployt Contracts zurück
        
        Returns:
            Liste von Contract-IDs
        """
        # Stelle sicher, dass die Contract Engine initialisiert ist
        if self.contract_engine is None:
            self.initialize_contract_engine()
            
        return list(self.contract_engine.contracts.keys())