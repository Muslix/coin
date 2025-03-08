import json
import threading
import time
import logging
import uuid
import socket
import requests
from typing import List, Dict, Any, Optional, Set
from urllib.parse import urlparse
from flask import Flask, jsonify, request, abort
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash

from blockchain import Blockchain, Block

# Konfiguration des Loggings
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='node.log',
    filemode='a'
)

# Reduziere Werkzeug (Flask) Logs auf WARNING-Level
werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.setLevel(logging.WARNING)

# Node Logger
logger = logging.getLogger('node')

# Reduziere Logging für häufige Operationen wie Node-Registrierung
registration_logger = logger.getChild('registration')
registration_logger.setLevel(logging.WARNING)  # Nur WARNING und höher (ERROR, CRITICAL) loggen

# Bekannte lokale Ports für schnelleren Node-Discovery
LOCAL_NODE_PORTS = [5000, 5001, 5002, 5003, 5004, 5005]

# Erstelle einen speziellen Logger für gefundene Blöcke
blocks_logger = logging.getLogger('node.blocks')

class Node:
    def __init__(self, host: str = '0.0.0.0', port: int = 5000, blockchain: Optional[Blockchain] = None):
        self.host = host
        self.port = port
        self.node_id = str(uuid.uuid4()).replace('-', '')
        self.blockchain = blockchain if blockchain is not None else Blockchain()
        self.peers: Set[str] = set()
        self.app = Flask(__name__)
        self.cors = CORS(self.app, resources={r"/*": {"origins": "*"}})  # CORS für API-Zugriff von Web-Clients
        
        # Einfache API-Authentifizierung
        self.api_keys: Dict[str, str] = {}  # username -> password_hash
        
        # P2P Verbindungsverwaltung
        self.connected_nodes: Dict[str, Dict[str, Any]] = {}  # node_id -> node_info
        
        # Mining-Adresse speichern, um Mining neu starten zu können
        self.current_miner_address = None
        
        # Setup API-Routen
        self.setup_routes()
        
        # Automatische Peer-Discovery aktivieren
        self.discovery_active = True
        
        logger.info(f"Node initialized with ID {self.node_id} at http://{host}:{port}")
        
    def setup_routes(self):
        """Set up Flask routes for the node API"""
        
        @self.app.route('/blockchain/pause', methods=['POST'])
        def pause_blockchain():
            """
            Pausiert die Blockchain für Updates oder Wartung
            """
            values = request.get_json()
            reason = values.get('reason', 'Manual pause')
            
            success = self.blockchain.pause_blockchain(reason)
            
            if success:
                return jsonify({
                    'message': f'Blockchain erfolgreich pausiert: {reason}',
                    'paused_at': time.time()
                })
            else:
                return jsonify({
                    'message': 'Fehler beim Pausieren der Blockchain'
                }), 500
                
        @self.app.route('/blockchain/resume', methods=['POST'])
        def resume_blockchain():
            """
            Setzt eine pausierte Blockchain fort
            """
            values = request.get_json()
            validate = values.get('validate', True)
            
            success = self.blockchain.resume_blockchain(validate)
            
            if success:
                # Bei erfolgreicher Wiederherstellung, falls validiert wurde
                if validate:
                    valid, issues = self.blockchain.comprehensive_validation()
                    
                    return jsonify({
                        'message': 'Blockchain erfolgreich fortgesetzt',
                        'resumed_at': time.time(),
                        'validation_result': {
                            'valid': valid,
                            'issues': issues
                        }
                    })
                else:
                    return jsonify({
                        'message': 'Blockchain erfolgreich fortgesetzt ohne Validierung',
                        'resumed_at': time.time()
                    })
            else:
                return jsonify({
                    'message': 'Fehler beim Fortsetzen der Blockchain'
                }), 500
                
        @self.app.route('/blockchain/checkpoint', methods=['POST'])
        def create_checkpoint():
            """
            Erstellt einen Checkpoint der Blockchain
            """
            values = request.get_json()
            reason = values.get('reason', 'Manual checkpoint')
            
            success = self.blockchain.create_checkpoint(reason)
            
            if success:
                return jsonify({
                    'message': f'Checkpoint erfolgreich erstellt: {reason}',
                    'timestamp': time.time(),
                    'blockchain_length': len(self.blockchain.chain)
                })
            else:
                return jsonify({
                    'message': 'Fehler beim Erstellen des Checkpoints'
                }), 500
                
        @self.app.route('/blockchain/validate', methods=['GET'])
        def validate_blockchain():
            """
            Führt eine vollständige Validierung der Blockchain durch
            """
            valid, issues = self.blockchain.comprehensive_validation()
            
            return jsonify({
                'valid': valid,
                'issues': issues,
                'blockchain_length': len(self.blockchain.chain),
                'timestamp': time.time()
            })
        # Basic node info
        @self.app.route('/node/info', methods=['GET'])
        def node_info():
            """Get basic info about this node"""
            return jsonify({
                'node_id': self.node_id,
                'host': self.host,
                'port': self.port,
                'peers': list(self.peers),
                'blockchain_length': len(self.blockchain.chain),
                'difficulty': self.blockchain.difficulty,
                'pending_transactions': len(self.blockchain.pending_transactions)
            })
        
        # Blockchain endpoints
        @self.app.route('/blockchain', methods=['GET'])
        def get_blockchain():
            """Get the entire blockchain"""
            # Optional Paginierung für große Blockchains
            start = request.args.get('start', 0, type=int)
            limit = request.args.get('limit', len(self.blockchain.chain), type=int)
            
            chain_data = []
            end = min(start + limit, len(self.blockchain.chain))
            
            for block in self.blockchain.chain[start:end]:
                chain_data.append({
                    'index': block.index,
                    'timestamp': block.timestamp,
                    'transactions': block.transactions,
                    'previous_hash': block.previous_hash,
                    'merkle_root': block.merkle_root,
                    'nonce': block.nonce,
                    'hash': block.hash,
                    'difficulty': block.difficulty
                })
                
            return jsonify({
                'chain': chain_data,
                'length': len(self.blockchain.chain),
                'start': start,
                'limit': limit
            })
        
        @self.app.route('/block/<string:block_hash>', methods=['GET'])
        def get_block_by_hash(block_hash):
            """Get a block by its hash"""
            block = self.blockchain.get_block_by_hash(block_hash)
            
            if not block:
                return jsonify({'message': 'Block not found'}), 404
                
            block_data = {
                'index': block.index,
                'timestamp': block.timestamp,
                'transactions': block.transactions,
                'previous_hash': block.previous_hash,
                'merkle_root': block.merkle_root, 
                'nonce': block.nonce,
                'hash': block.hash,
                'difficulty': block.difficulty
            }
            
            return jsonify(block_data)
            
        @self.app.route('/block/index/<int:block_index>', methods=['GET'])
        def get_block_by_index(block_index):
            """Get a block by its index"""
            block = self.blockchain.get_block_by_index(block_index)
            
            if not block:
                return jsonify({'message': 'Block not found'}), 404
                
            block_data = {
                'index': block.index,
                'timestamp': block.timestamp,
                'transactions': block.transactions,
                'previous_hash': block.previous_hash,
                'merkle_root': block.merkle_root,
                'nonce': block.nonce,
                'hash': block.hash,
                'difficulty': block.difficulty
            }
            
            return jsonify(block_data)
        
        # Transaction endpoints
        @self.app.route('/transaction/new', methods=['POST'])
        def new_transaction():
            """Create a new transaction"""
            values = request.get_json()
            
            required = ['sender', 'recipient', 'amount', 'signature']
            if not all(k in values for k in required):
                return jsonify({'message': 'Missing values'}), 400
                
            # Basic validation
            if values['amount'] <= 0:
                return jsonify({'message': 'Amount must be positive'}), 400
                
            # Add transaction to the blockchain
            tx_id = self.blockchain.add_transaction(
                sender=values['sender'],
                recipient=values['recipient'],
                amount=values['amount'],
                metadata={"signature": values['signature']}
            )
            
            if not tx_id:
                return jsonify({'message': 'Transaction rejected'}), 400
                
            # Broadcast transaction to all peers
            self.broadcast_transaction(values)
            
            return jsonify({
                'message': f'Transaction will be added to Block',
                'transaction_id': tx_id
            })
            
        @self.app.route('/transactions/pending', methods=['GET'])
        def get_pending_transactions():
            """Get all pending transactions"""
            return jsonify({
                'transactions': self.blockchain.pending_transactions,
                'count': len(self.blockchain.pending_transactions)
            })
            
        @self.app.route('/transactions/history/<string:address>', methods=['GET'])
        def get_transaction_history(address):
            """Get transaction history for an address"""
            transactions = self.blockchain.get_transaction_history(address)
            return jsonify({
                'address': address,
                'transactions': transactions,
                'count': len(transactions)
            })
        
        # Mining endpoints
        @self.app.route('/mine', methods=['GET'])
        def mine():
            """Mine a single block"""
            if not request.args.get('address'):
                return jsonify({'message': 'Mining address required as query parameter'}), 400
                
            miner_address = request.args.get('address')
            
            # Mine a new block
            block = self.blockchain.mine_pending_transactions(miner_address)
            
            # Announce the new block to the network
            self.broadcast_new_block()
            
            return jsonify({
                'message': 'New block mined',
                'block_index': block.index,
                'block_hash': block.hash,
                'transactions': len(block.transactions)
            })
            
        @self.app.route('/mining/start', methods=['POST'])
        def start_mining():
            """Start continuous mining"""
            values = request.get_json()
            
            if not values or not values.get('address'):
                return jsonify({'message': 'Mining address required'}), 400
                
            miner_address = values.get('address')
            # Speichere die Mining-Adresse für späteren Neustart
            self.current_miner_address = miner_address
            
            # Verbesserte Version: Callback für Block-Mining, der sofort Konsensus auslöst
            def mining_callback(block):
                # Sicherheitscheck für potentielle Race Conditions
                if not block or not hasattr(block, 'hash'):
                    logger.warning("Received invalid block in mining_callback")
                    return
                    
                logger.info(f"Successfully mined block #{block.index}, hash: {block.hash}")
                # Sofort anderen Nodes Bescheid geben, dass wir einen neuen Block haben
                threading.Thread(target=self._immediate_block_broadcast, args=(block,)).start()
            
            # Synchronisierungsfunktion für regelmäßige Konsens-Updates
            def sync_callback():
                # Versuche, die Blockchain vor jedem Mining-Versuch zu synchronisieren
                if self.peers:
                    try:
                        updated = self.resolve_conflicts()
                        if updated:
                            logger.info("Blockchain updated with network consensus before mining")
                        return updated
                    except Exception as e:
                        logger.error(f"Error during pre-mining sync: {str(e)}")
                return False
            
            # Start continuous mining with improved callbacks
            self.blockchain.start_continuous_mining(miner_address, mining_callback, sync_callback)
            
            return jsonify({
                'message': 'Continuous mining started',
                'miner': miner_address,
                'difficulty': self.blockchain.difficulty
            })
            
        @self.app.route('/mining/stop', methods=['POST'])
        def stop_mining():
            """Stop continuous mining"""
            self.blockchain.stop_continuous_mining()
            
            return jsonify({
                'message': 'Mining stopped'
            })
            
        @self.app.route('/mining/stats', methods=['GET'])
        def mining_stats():
            """Get mining statistics"""
            stats = self.blockchain.get_mining_stats()
            
            return jsonify({
                'stats': stats
            })
            
        @self.app.route('/mining/difficulty', methods=['POST'])
        def set_difficulty():
            """Set mining difficulty"""
            values = request.get_json()
            
            if not values or 'difficulty' not in values:
                return jsonify({'message': 'Difficulty value required'}), 400
                
            difficulty = int(values.get('difficulty'))
            self.blockchain.set_difficulty(difficulty)
            
            return jsonify({
                'message': f'Mining difficulty set to {difficulty}',
                'difficulty': difficulty
            })
        
        # Node network management
        @self.app.route('/nodes/register', methods=['POST'])
        def register_nodes():
            """Register new peer nodes"""
            values = request.get_json()
            
            nodes = values.get('nodes')
            if nodes is None or not isinstance(nodes, list):
                return jsonify({'message': 'Error: Please supply a valid list of nodes'}), 400
                
            registered_count = 0
            for node in nodes:
                parsed_url = urlparse(node)
                if parsed_url.netloc:
                    if self.register_node(node):
                        registered_count += 1
                    
            # Attempt to notify registered nodes about this node
            self_url = f"http://{self.host}:{self.port}"
            for node in self.peers:
                try:
                    requests.post(f"{node}/nodes/register", json={'nodes': [self_url]}, timeout=2)
                except requests.RequestException:
                    # Ignorieren wenn der Peer nicht erreichbar ist
                    pass
            
            # Nur loggen, wenn tatsächlich neue Nodes hinzugefügt wurden, und nur einmal für alle
            if registered_count > 0:
                registration_logger.info(f"Added {registered_count} new nodes, total nodes: {len(self.peers)}")
                
            return jsonify({
                'message': f'Added {registered_count} new nodes',
                'total_nodes': list(self.peers)
            })
            
        @self.app.route('/nodes/list', methods=['GET'])
        def list_nodes():
            """List all registered nodes"""
            return jsonify({
                'nodes': list(self.peers),
                'count': len(self.peers)
            })
            
        @self.app.route('/nodes/resolve', methods=['GET'])
        def consensus():
            """Resolve conflicts using consensus algorithm"""
            replaced = self.resolve_conflicts()
            
            if replaced:
                response = {
                    'message': 'Our chain was replaced',
                    'new_chain_length': len(self.blockchain.chain)
                }
            else:
                response = {
                    'message': 'Our chain is authoritative',
                    'chain_length': len(self.blockchain.chain)
                }
                
            return jsonify(response)
        
        # Wallet endpoints
        @self.app.route('/balance', methods=['GET'])
        def get_balance():
            """Get balance of an address"""
            address = request.args.get('address')
            
            if not address:
                return jsonify({'message': 'Address parameter required'}), 400
                
            balance = self.blockchain.get_balance(address)
            
            return jsonify({
                'address': address,
                'balance': balance
            })
            
        # API Management
        @self.app.route('/api/register', methods=['POST'])
        def register_api_key():
            """Register a new API key"""
            values = request.get_json()
            
            if not values or 'username' not in values or 'password' not in values:
                return jsonify({'message': 'Username and password required'}), 400
                
            username = values['username']
            password = values['password']
            
            if username in self.api_keys:
                return jsonify({'message': 'Username already exists'}), 400
                
            # Hash the password
            password_hash = generate_password_hash(password)
            self.api_keys[username] = password_hash
            
            return jsonify({'message': 'API key registered successfully'})
            
        @self.app.route('/api/validate', methods=['POST'])
        def validate_api_key():
            """Validate an API key"""
            values = request.get_json()
            
            if not values or 'username' not in values or 'password' not in values:
                return jsonify({'message': 'Username and password required'}), 400
                
            username = values['username']
            password = values['password']
            
            if username not in self.api_keys:
                return jsonify({'message': 'Invalid credentials'}), 401
                
            if not check_password_hash(self.api_keys[username], password):
                return jsonify({'message': 'Invalid credentials'}), 401
                
            return jsonify({'message': 'Credentials validated'})
            
        # Health check
        @self.app.route('/health', methods=['GET'])
        def health_check():
            """Health check endpoint"""
            return jsonify({
                'status': 'healthy',
                'node_id': self.node_id,
                'blockchain_length': len(self.blockchain.chain),
                'peers': len(self.peers),
            })
        
        # Smart Contract endpoints
        @self.app.route('/contracts/deploy', methods=['POST'])
        def deploy_contract():
            """Deploy a new smart contract"""
            values = request.get_json()
            
            if not values or not all(k in values for k in ['code', 'owner']):
                return jsonify({'message': 'Missing values'}), 400
            
            code = values['code']
            owner = values['owner']
            initial_balance = float(values.get('initial_balance', 0.0))
            
            try:
                # Deployen des Contracts
                contract_id = self.blockchain.deploy_contract(code, owner, initial_balance)
                
                # Mining der Transaktion, falls initial_balance > 0
                if initial_balance > 0:
                    self.blockchain.mine_pending_transactions(owner)
                    
                return jsonify({
                    'message': 'Contract deployed successfully',
                    'contract_id': contract_id
                })
            except ValueError as e:
                return jsonify({'message': str(e)}), 400
            except Exception as e:
                logger.error(f"Error deploying contract: {str(e)}")
                return jsonify({'message': f'Contract deployment failed: {str(e)}'}), 500
                
        @self.app.route('/contracts/call/<string:contract_id>', methods=['POST'])
        def call_contract(contract_id):
            """Call a contract method"""
            values = request.get_json()
            
            if not values or not all(k in values for k in ['method', 'sender']):
                return jsonify({'message': 'Missing values'}), 400
            
            method = values['method']
            sender = values['sender']
            args = values.get('args', [])
            kwargs = values.get('kwargs', {})
            value = float(values.get('value', 0.0))
            
            try:
                # Aufruf der Contract-Methode
                result = self.blockchain.call_contract(contract_id, method, sender, args, kwargs, value)
                
                # Mining der Transaktion, falls value > 0
                if value > 0:
                    self.blockchain.mine_pending_transactions(sender)
                    
                return jsonify({
                    'message': 'Contract method called successfully',
                    'result': result
                })
            except ValueError as e:
                return jsonify({'message': str(e)}), 400
            except PermissionError as e:
                return jsonify({'message': str(e)}), 403
            except Exception as e:
                logger.error(f"Error calling contract: {str(e)}")
                return jsonify({'message': f'Contract call failed: {str(e)}'}), 500
                
        @self.app.route('/contracts/state/<string:contract_id>', methods=['GET'])
        def get_contract_state(contract_id):
            """Get the state of a contract"""
            try:
                state = self.blockchain.get_contract_state(contract_id)
                return jsonify(state)
            except ValueError as e:
                return jsonify({'message': str(e)}), 404
            except Exception as e:
                logger.error(f"Error getting contract state: {str(e)}")
                return jsonify({'message': f'Error getting contract state: {str(e)}'}), 500
                
        @self.app.route('/contracts/list', methods=['GET'])
        def list_contracts():
            """List all deployed contracts"""
            try:
                contracts = self.blockchain.get_deployed_contracts()
                
                # Option: Hole zusätzliche Informationen zu jedem Contract
                detailed = request.args.get('detailed', 'false').lower() == 'true'
                
                if detailed:
                    contract_details = []
                    for contract_id in contracts:
                        try:
                            state = self.blockchain.get_contract_state(contract_id)
                            contract_details.append({
                                'id': contract_id,
                                'owner': state['owner'],
                                'balance': state['balance'],
                                'created_at': state['created_at'],
                                'last_executed': state['last_executed']
                            })
                        except Exception:
                            # Fehler bei einem Contract sollten nicht die ganze Liste blockieren
                            contract_details.append({'id': contract_id, 'error': 'Error getting details'})
                    
                    return jsonify({'contracts': contract_details, 'count': len(contracts)})
                else:
                    return jsonify({'contracts': contracts, 'count': len(contracts)})
            except Exception as e:
                logger.error(f"Error listing contracts: {str(e)}")
                return jsonify({'message': f'Error listing contracts: {str(e)}'}), 500
                
        # Neue Route für automatische Node-Discovery
        @self.app.route('/nodes/discovery', methods=['GET'])
        def node_discovery():
            """Endpoint for automatic node discovery"""
            # Gibt Node-ID und URL zurück, damit andere Nodes diesen Node identifizieren können
            return jsonify({
                'node_id': self.node_id,
                'url': f"http://{self.host}:{self.port}",
                'blockchain_length': len(self.blockchain.chain),
                'peers_count': len(self.peers)
            })
        
        @self.app.route('/block/notify/<int:block_index>', methods=['POST'])
        def notify_new_block(block_index):
            """
            Benachrichtigung über einen neuen Block auf einem anderen Node
            """
            values = request.get_json()
            
            if not values or 'node_url' not in values:
                return jsonify({'message': 'Invalid notification data'}), 400
                
            sender_url = values['node_url']
            
            # Prüfen, ob unser aktueller Block-Index niedriger ist
            current_index = len(self.blockchain.chain) - 1
            
            if block_index > current_index:
                # Wir sind hinter dem anderen Node, also starten wir sofort den Konsens
                threading.Thread(target=self._fetch_from_specific_peer, args=(sender_url,)).start()
                return jsonify({
                    'message': 'Will sync with your chain',
                    'our_index': current_index,
                    'your_index': block_index
                })
            else:
                return jsonify({
                    'message': 'Already up to date',
                    'our_index': current_index
                })
    
    def start(self):
        """Start the node server"""
        threading.Thread(target=self.app.run, 
                         kwargs={'host': self.host, 'port': self.port, 'threaded': True}).start()
        logger.info(f"Node started at http://{self.host}:{self.port}")
        
        # Start periodic peer discovery
        threading.Thread(target=self._periodic_peer_discovery, daemon=True).start()
        
        # Start automatic local network discovery (fast version for localhost)
        threading.Thread(target=self._automatic_local_discovery, daemon=True).start()
        
        # Start regelmäßige Konsensus-Bildung (häufiger als zuvor)
        threading.Thread(target=self._periodic_consensus, daemon=True).start()
        
    def _periodic_peer_discovery(self):
        """Periodically discover and connect to new peers"""
        while True:
            try:
                self._discover_peers()
                time.sleep(300)  # Run every 5 minutes
            except Exception as e:
                logger.error(f"Error in peer discovery: {str(e)}")
                time.sleep(60)  # Wait a minute and try again
                
    def _discover_peers(self):
        """Discover new peers by asking known peers"""
        if not self.peers:
            return
            
        for peer in list(self.peers):
            try:
                response = requests.get(f"{peer}/nodes/list", timeout=2)
                if response.status_code == 200:
                    nodes = response.json().get('nodes', [])
                    for node in nodes:
                        if node != f"http://{self.host}:{self.port}":
                            self.register_node(node)
            except requests.RequestException:
                # Node might be down, consider removing it
                logger.warning(f"Peer {peer} unreachable during discovery")
    
    def _automatic_local_discovery(self):
        """
        Verbesserte Funktion für automatisches Entdecken von Nodes
        Speziell optimiert für lokale Entwicklungsumgebung
        """
        # Warte kurz, damit der Server vollständig starten kann
        time.sleep(2)
        logger.info("Starting local node discovery on standard ports...")
        
        # Versuche sofort alle bekannten lokalen Ports zu erreichen
        self._discover_local_nodes()
        
        # Starte periodische lokale Entdeckung
        while self.discovery_active:
            try:
                # Nur alle 60 Sekunden prüfen
                time.sleep(60)
                self._discover_local_nodes()
            except Exception as e:
                logger.error(f"Error in local node discovery: {str(e)}")
                time.sleep(10)
        
    def _discover_local_nodes(self):
        """
        Scannt nur localhost auf bekannten Ports, um Nodes zu finden
        Optimiert für lokale Entwicklung mit mehreren Nodes auf einem Rechner
        """
        my_url = f"http://{self.host}:{self.port}"
        connected_nodes = 0
        
        # Prüfe alle bekannten Ports auf localhost
        for test_port in LOCAL_NODE_PORTS:
            # Eigenen Port überspringen
            if test_port == self.port:
                continue
                
            target_url = f"http://localhost:{test_port}"
            
            try:
                # Versuche Verbindung zum Node auf diesem Port herzustellen
                response = requests.get(f"{target_url}/nodes/discovery", timeout=1)
                
                if response.status_code == 200:
                    data = response.json()
                    node_url = data.get('url', target_url)
                    
                    # Prüfen, ob es sich um einen gültigen Node handelt
                    if 'node_id' in data and node_url != my_url:
                        # Node gefunden, registrieren
                        was_added = self.register_node(node_url)
                        
                        if was_added:
                            connected_nodes += 1
                            registration_logger.debug(f"Discovered node at {node_url}")  # DEBUG-Level für Discovery
                            
                            # Gegenseitige Registrierung (wichtig für P2P-Netzwerk)
                            try:
                                requests.post(
                                    f"{node_url}/nodes/register", 
                                    json={"nodes": [my_url]},
                                    timeout=1
                                )
                                registration_logger.debug(f"Registered with {node_url}")  # DEBUG-Level für diese Message
                            except requests.RequestException as e:
                                registration_logger.warning(f"Failed to register with {node_url}: {str(e)}")
                            
            except requests.RequestException:
                # Ignorieren wenn Port nicht erreichbar ist
                pass
                
        if connected_nodes > 0:
            registration_logger.info(f"Local discovery found {connected_nodes} nodes")  # Als Information behalten
        return connected_nodes
        
    def register_node(self, address: str) -> bool:
        """Add a new node to the list of peers"""
        parsed_url = urlparse(address)
        if parsed_url.netloc:
            node_url = f"{parsed_url.scheme or 'http'}://{parsed_url.netloc}"
            if node_url not in self.peers and node_url != f"http://{self.host}:{self.port}":
                self.peers.add(node_url)
                registration_logger.debug(f"Registered peer node: {node_url}")  # Nur DEBUG-Level für einzelne Registrierungen
                return True
        return False
            
    def broadcast_transaction(self, transaction: Dict[str, Any]):
        """Broadcast transaction to all peer nodes"""
        for peer in list(self.peers):
            try:
                requests.post(f"{peer}/transaction/new", json=transaction, timeout=2)
                logger.debug(f"Broadcast transaction to {peer}")
            except requests.RequestException as e:
                # If peer is unreachable, consider removing it
                logger.warning(f"Could not broadcast transaction to {peer}: {str(e)}")
                
    def broadcast_new_block(self):
        """Notify all nodes about the new block"""
        # Diese Methode wird durch _immediate_block_broadcast ersetzt,
        # bleibt aber für Rückwärtskompatibilität erhalten
        for peer in list(self.peers):
            try:
                requests.get(f"{peer}/nodes/resolve", timeout=2)
                logger.debug(f"Legacy broadcast new block to {peer}")
            except requests.RequestException as e:
                logger.warning(f"Could not broadcast new block to {peer}: {str(e)}")
                
    def _periodic_consensus(self):
        """
        Führt in regelmäßigen Abständen den Konsensus-Algorithmus aus
        """
        # Warte kurz, um dem Node Zeit zum Starten zu geben
        time.sleep(5)
        logger.info("Starting periodic blockchain consensus...")
        
        while True:
            try:
                # Nur ausführen, wenn Peers vorhanden sind
                if self.peers:
                    success = self.resolve_conflicts()
                    if success:
                        logger.info("Periodic consensus check: Chain was updated")
                    else:
                        logger.debug("Periodic consensus check: No update needed")
                    
                # Alle 10 Sekunden prüfen (statt 30 Sekunden) für schnellere Synchronisation
                time.sleep(10)
                
            except Exception as e:
                logger.error(f"Error in periodic consensus: {str(e)}")
                time.sleep(10)
                
    def resolve_conflicts(self) -> bool:
        """
        Consensus algorithm: resolve conflicts by replacing our chain with the longest valid chain in the network
        """
        new_chain = None
        current_length = len(self.blockchain.chain)
        max_length = current_length
        source_node = None
        
        # Grab and verify the chains from all the nodes in our network
        for peer in list(self.peers):
            try:
                response = requests.get(f"{peer}/blockchain", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    length = data['length']
                    chain = data['chain']
                    
                    # Check if the length is longer and the chain is valid
                    if length > max_length and self._is_chain_valid(chain):
                        max_length = length
                        new_chain = chain
                        source_node = peer
                        logger.info(f"Found longer valid chain from {peer} with length {length}")
            except requests.RequestException as e:
                logger.warning(f"Error getting blockchain from {peer}: {str(e)}")
                continue
                
        # Replace our chain if we discovered a new, valid chain longer than ours
        if new_chain:
            # Logge alle Blöcke, die dem lokalen Node fehlen
            missing_blocks_count = max_length - current_length
            blocks_logger.info(f"Importing {missing_blocks_count} new blocks from node {source_node}")
            
            # Extrahiere neue Block-Informationen für verbesserte Logs
            for i in range(current_length, max_length):
                block = new_chain[i]
                tx_count = len(block['transactions'])
                miner = "unknown"
                
                # Finde den Miner (Empfänger der Mining-Belohnung)
                for tx in block['transactions']:
                    if tx.get('from') == 'network' and tx.get('type') == 'reward':
                        miner = tx.get('to', 'unknown')
                        break
                
                blocks_logger.info(
                    f"Block #{i} from peer {source_node} - "
                    f"Hash: {block['hash'][:10]}... | "
                    f"Mined by: {miner} | "
                    f"Transactions: {tx_count}"
                )
                
                # Zeige auch eine Zusammenfassung im Terminal an
                print(f"Imported Block #{i} from peer node - Mined by: {miner}")
                
            logger.info(f"Replacing local chain (length: {current_length}) with network chain (length: {max_length})")
            self._replace_chain(new_chain)
            return True
            
        logger.debug("Local chain is authoritative, no consensus action needed")
        return False
    
    def _is_chain_valid(self, chain) -> bool:
        """
        Verify if a given blockchain is valid
        """
        # Prüfe jeden Block in der Kette
        for i, block_data in enumerate(chain):
            # Genesis-Block überspringen
            if i == 0:
                continue
                
            # Vorherigen Block erhalten
            prev_block_data = chain[i-1]
            
            # 1. Prüfen, ob der previous_hash korrekt ist
            if block_data['previous_hash'] != prev_block_data['hash']:
                logger.error(f"Invalid previous hash in block {i}")
                return False
                
            # 2. Prüfen, ob der Hash den richtigen Schwierigkeitsgrad hat
            difficulty = block_data.get('difficulty', 4)
            if block_data['hash'][:difficulty] != '0' * difficulty:
                logger.error(f"Invalid proof of work in block {i}")
                return False
                
            # 3. Prüfen, ob der Index korrekt ist
            if block_data['index'] != i:
                logger.error(f"Invalid block index {block_data['index']} at position {i}")
                return False
                
        logger.info(f"External chain with {len(chain)} blocks validated successfully")
        return True
    
    def _replace_chain(self, new_chain):
        """
        Replace the local chain with the given one
        """
        try:
            # Speichere den Mining-Status, bevor wir die Chain ersetzen
            was_mining = False
            mining_address = self.current_miner_address
            
            # Stoppt das Mining, falls aktiv, da sonst Race Conditions entstehen können
            if self.blockchain._mining_thread and self.blockchain._mining_thread.is_alive():
                was_mining = True
                logger.info("Temporarily stopping mining to update blockchain")
                self.blockchain.stop_continuous_mining()
                
            # Sichere ausstehende Transaktionen vor dem Ersetzen der Blockchain
            pending_transactions = self.blockchain.pending_transactions.copy()
            
            # Führe ausstehende Transaktionen zusammen und entferne Duplikate
            existing_tx_ids = set()
            for block in new_chain:
                for tx in block['transactions']:
                    if 'id' in tx:
                        existing_tx_ids.add(tx['id'])
            
            # Setze die Blockchain zurück und füge alle Blöcke hinzu
            self.blockchain.chain = []
            
            for block_data in new_chain:
                # Konvertiere JSON-Daten in Block-Objekt
                block = Block(
                    index=block_data['index'],
                    timestamp=block_data['timestamp'],
                    transactions=block_data['transactions'],
                    previous_hash=block_data['previous_hash'],
                    nonce=block_data['nonce']
                )
                block.hash = block_data['hash']
                block.merkle_root = block_data.get('merkle_root', '')
                block.difficulty = block_data.get('difficulty', 4)
                
                # Füge Block zur Kette hinzu
                self.blockchain.chain.append(block)
                
            # Aktualisiere die Schwierigkeit basierend auf der neuen Kette
            self.blockchain.difficulty = new_chain[-1].get('difficulty', 4)
            
            # Füge die ausstehenden Transaktionen wieder hinzu, die noch nicht in der neuen Kette sind
            for tx in pending_transactions:
                if 'id' in tx and tx['id'] not in existing_tx_ids:
                    self.blockchain.pending_transactions.append(tx)
            
            # Starte das Mining wieder, falls es vorher aktiv war
            if was_mining and mining_address:
                logger.info(f"Restarting mining with address {mining_address}")
                
                # Mining-Callbacks für Block-Notifications und Synchronisierung
                def mining_callback(block):
                    if not block or not hasattr(block, 'hash'):
                        return
                    logger.info(f"Successfully mined block #{block.index}, hash: {block.hash}")
                    threading.Thread(target=self._immediate_block_broadcast, args=(block,)).start()
                
                def sync_callback():
                    if self.peers:
                        try:
                            updated = self.resolve_conflicts()
                            return updated
                        except Exception as e:
                            logger.error(f"Error during pre-mining sync: {str(e)}")
                    return False
                
                # Starte das Mining neu mit denselben Callbacks wie zuvor
                self.blockchain.start_continuous_mining(mining_address, mining_callback, sync_callback)
                print(f"Mining restarted with address: {mining_address}")
            
            logger.info(f"Successfully replaced chain with {len(self.blockchain.chain)} blocks")
            return True
            
        except Exception as e:
            logger.error(f"Error replacing chain: {str(e)}")
            return False

    def _immediate_block_broadcast(self, block):
        """
        Benachrichtigt sofort alle Peers über einen neu geminten Block
        """
        if not self.peers:
            logger.debug("No peers to broadcast new block to")
            return
            
        # Bereite einfache Notification vor (keine volle Blockchain-Übertragung)
        self_url = f"http://{self.host}:{self.port}"
        notification_data = {
            'node_url': self_url,
            'block_index': block.index,
            'block_hash': block.hash
        }
        
        logger.info(f"Broadcasting new block #{block.index} to {len(self.peers)} peers")
        
        # Benachrichtige alle Peers parallel
        for peer in list(self.peers):
            threading.Thread(
                target=self._notify_peer_about_block, 
                args=(peer, block.index, notification_data)
            ).start()
    
    def _notify_peer_about_block(self, peer_url, block_index, notification_data):
        """
        Benachrichtigt einen bestimmten Peer über einen neuen Block
        """
        try:
            requests.post(
                f"{peer_url}/block/notify/{block_index}",
                json=notification_data,
                timeout=2
            )
            logger.debug(f"Notified {peer_url} about new block #{block_index}")
        except requests.RequestException as e:
            logger.warning(f"Failed to notify {peer_url} about new block: {str(e)}")
    
    def _fetch_from_specific_peer(self, peer_url):
        """
        Lädt die Blockchain von einem bestimmten Peer
        Verwendet für gezielte Synchronisierung nach Block-Benachrichtigungen
        """
        try:
            response = requests.get(f"{peer_url}/blockchain", timeout=5)
            if response.status_code == 200:
                data = response.json()
                chain = data['chain']
                
                if self._is_chain_valid(chain) and len(chain) > len(self.blockchain.chain):
                    current_length = len(self.blockchain.chain)
                    new_length = len(chain)
                    
                    blocks_logger.info(f"Received notification for new block(s) from {peer_url}")
                    for i in range(current_length, new_length):
                        block = chain[i]
                        miner = "unknown"
                        
                        # Finde den Miner (Empfänger der Mining-Belohnung)
                        for tx in block['transactions']:
                            if tx.get('from') == 'network' and tx.get('type') == 'reward':
                                miner = tx.get('to', 'unknown')
                                break
                        
                        blocks_logger.info(
                            f"New Block #{i} notification - "
                            f"Hash: {block['hash'][:10]}... | "
                            f"Mined by: {miner} | "
                            f"Difficulty: {block.get('difficulty', 4)}"
                        )
                        
                        print(f"Received new Block #{i} - Mined by: {miner} - Difficulty: {block.get('difficulty', 4)}")
                    
                    logger.info(f"Updating chain from peer {peer_url}, new length: {len(chain)}")
                    self._replace_chain(chain)
                    return True
        except requests.RequestException as e:
            logger.warning(f"Error fetching blockchain from {peer_url}: {str(e)}")
            
        return False

if __name__ == "__main__":
    node = Node()
    node.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Node shutting down...")
        print("Node shutting down...")