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
logger = logging.getLogger('node')

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
        
        # Setup API-Routen
        self.setup_routes()
        
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
            
            # Optional callback to notify about new blocks
            def mining_callback(block):
                self.broadcast_new_block()
            
            # Start continuous mining
            self.blockchain.start_continuous_mining(miner_address, mining_callback)
            
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
                
            for node in nodes:
                parsed_url = urlparse(node)
                if parsed_url.netloc:
                    self.register_node(node)
                    
            # Attempt to notify registered nodes about this node
            self_url = f"http://{self.host}:{self.port}"
            for node in self.peers:
                try:
                    requests.post(f"{node}/nodes/register", json={'nodes': [self_url]}, timeout=2)
                except requests.RequestException:
                    # Ignorieren wenn der Peer nicht erreichbar ist
                    pass
                
            return jsonify({
                'message': 'New nodes have been added',
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
    
    def start(self):
        """Start the node server"""
        threading.Thread(target=self.app.run, 
                         kwargs={'host': self.host, 'port': self.port, 'threaded': True}).start()
        logger.info(f"Node started at http://{self.host}:{self.port}")
        
        # Start periodic peer discovery
        threading.Thread(target=self._periodic_peer_discovery, daemon=True).start()
        
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
        
    def register_node(self, address: str):
        """Add a new node to the list of peers"""
        parsed_url = urlparse(address)
        if parsed_url.netloc:
            node_url = f"{parsed_url.scheme or 'http'}://{parsed_url.netloc}"
            if node_url not in self.peers and node_url != f"http://{self.host}:{self.port}":
                self.peers.add(node_url)
                logger.info(f"Registered peer node: {node_url}")
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
        for peer in list(self.peers):
            try:
                requests.get(f"{peer}/nodes/resolve", timeout=2)
                logger.debug(f"Broadcast new block to {peer}")
            except requests.RequestException as e:
                logger.warning(f"Could not broadcast new block to {peer}: {str(e)}")
                
    def resolve_conflicts(self) -> bool:
        """
        Consensus algorithm: resolve conflicts by replacing our chain with the longest valid chain in the network
        """
        new_chain = None
        max_length = len(self.blockchain.chain)
        
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
                        logger.info(f"Found longer valid chain from {peer} with length {length}")
            except requests.RequestException as e:
                logger.warning(f"Error getting blockchain from {peer}: {str(e)}")
                continue
                
        # Replace our chain if we discovered a new, valid chain longer than ours
        if new_chain:
            # In einer vollständigen Implementierung würde hier die Kette korrekt 
            # konvertiert und validiert werden
            logger.info("Replacing local chain with network chain")
            self._replace_chain(new_chain)
            return True
            
        return False
    
    def _is_chain_valid(self, chain) -> bool:
        """
        Verify if a given blockchain is valid
        Einfache Validierung für Demo-Zwecke
        """
        # In einer echten Implementierung: vollständige Validierung der Kette
        return True
    
    def _replace_chain(self, new_chain):
        """
        Replace the local chain with the given one
        Vereinfachte Version für Demo-Zwecke
        """
        # In einer echten Implementierung würde hier die neue Chain
        # korrekt in Block-Objekte konvertiert werden
        # Für diese Demo-Version vereinfacht
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
        
        logger.info(f"Chain replaced with {len(self.blockchain.chain)} blocks")


if __name__ == "__main__":
    node = Node()
    node.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Node shutting down...")
        print("Node shutting down...")