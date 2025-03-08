#!/usr/bin/env python3
import argparse
import sys
import os
import json
from typing import Dict, Any, List, Optional
import requests
import socket

from blockchain import Blockchain
from wallet import Wallet
from node import Node


class CryptoCoin:
    def __init__(self):
        self.blockchain = Blockchain()
        self.wallet = Wallet()
        self.node = None
        self.wallet_created = False
        self.node_url = None
        
    def start_node(self, host: str = '0.0.0.0', port: int = 5000) -> None:
        """Start a blockchain node"""
        # Verwenden der bestehenden Blockchain-Instanz für den Knoten
        self.node = Node(host, port, blockchain=self.blockchain)
        self.node.start()
        self.node_url = f"http://{host}:{port}"
        # Removed duplicated print statement, now only printed once
        
    def create_wallet(self) -> Dict[str, str]:
        """Generate a new wallet with keys"""
        keys = self.wallet.generate_keys()
        self.wallet_created = True
        print(f"New wallet created!")
        print(f"Address: {keys['address']}")
        print(f"Public Key: {keys['public_key']}")
        print(f"Private Key: {keys['private_key']}")
        print("\nSAVE YOUR PRIVATE KEY! If you lose it, you lose access to your funds.")
        
        return keys
        
    def save_wallet(self, filename: str) -> None:
        """Save wallet to file"""
        if not self.wallet_created:
            print("No wallet to save. Creating a new wallet...")
            self.create_wallet()
            
        self.wallet.save_to_file(filename)
        print(f"Wallet saved to {filename}")
        
    def load_wallet(self, filename: str) -> Dict[str, str]:
        """Load wallet from file"""
        keys = self.wallet.load_from_file(filename)
        self.wallet_created = True
        print(f"Wallet loaded successfully!")
        print(f"Address: {keys['address']}")
        return keys
        
    def get_balance(self, address: str) -> float:
        """Get wallet balance"""
        # Check if a node is running locally or on the network
        node_url = self._find_node_url()
        
        if node_url:
            # Use node API to get balance
            try:
                response = requests.get(f"{node_url}/balance", params={"address": address})
                if response.status_code == 200:
                    data = response.json()
                    print(f"Balance for {address}: {data['balance']}")
                    return data['balance']
                else:
                    print(f"Error getting balance from node: {response.text}")
            except requests.RequestException as e:
                print(f"Error connecting to node: {e}")
                
        # Fallback to local blockchain
        balance = self.blockchain.get_balance(address)
        print(f"Balance for {address}: {balance}")
        return balance
        
    def send_transaction(self, sender: str, recipient: str, amount: float, private_key: str) -> None:
        """Create and send a transaction"""
        # Check if a node is running
        node_url = self._find_node_url()
        
        if not node_url:
            print("No node is running. Please start a node first or connect to an existing one.")
            return
            
        # Create transaction data
        transaction = {
            "sender": sender,
            "recipient": recipient,
            "amount": amount
        }
        
        # Load wallet with the private key to sign transaction
        self.wallet.load_keys(private_key)
        
        # Sign transaction
        signature = self.wallet.sign_transaction(transaction)
        
        # Add signature to transaction
        transaction["signature"] = signature
        
        # Send to node API
        try:
            response = requests.post(f"{node_url}/transaction/new", json=transaction)
            if response.status_code == 200:
                print(f"Transaction sent: {amount} coins from {sender} to {recipient}")
                print(response.json()["message"])
            else:
                print(f"Error sending transaction: {response.text}")
        except requests.RequestException as e:
            print(f"Error connecting to node: {e}")
        
    def mine(self, address: str) -> None:
        """Mine pending transactions"""
        # Check if a node is running
        node_url = self._find_node_url()
        
        if node_url:
            # Use node API to mine
            try:
                response = requests.get(f"{node_url}/mine", params={"address": address})
                if response.status_code == 200:
                    data = response.json()
                    print(data["message"])
                    print(f"Block #{data['block_index']} with hash {data['block_hash']}")
                else:
                    print(f"Error mining block: {response.text}")
            except requests.RequestException as e:
                print(f"Error connecting to node: {e}")
                print("Using local blockchain instead...")
                self._mine_local(address)
        else:
            print("No node is running. Using local blockchain...")
            self._mine_local(address)
    
    def _mine_local(self, address: str) -> None:
        """Mine transactions locally without a node"""
        if not self.blockchain.pending_transactions:
            print("No pending transactions to mine.")
            return
            
        print("Mining pending transactions...")
        self.blockchain.mine_pending_transactions(address)
        print(f"Block mined! Reward sent to {address}")
        
    def print_chain(self) -> None:
        """Print the entire blockchain"""
        # Check if a node is running
        node_url = self._find_node_url()
        
        if node_url:
            # Use node API to get blockchain
            try:
                response = requests.get(f"{node_url}/blockchain")
                if response.status_code == 200:
                    data = response.json()
                    chain_data = data["chain"]
                    print("\n========== BLOCKCHAIN ==========")
                    for block in chain_data:
                        print(f"Block #{block['index']}")
                        print(f"Timestamp: {block['timestamp']}")
                        print(f"Previous Hash: {block['previous_hash']}")
                        print(f"Hash: {block['hash']}")
                        print(f"Nonce: {block['nonce']}")
                        print("Transactions:")
                        for tx in block['transactions']:
                            print(f"  From: {tx['from']} To: {tx['to']} Amount: {tx['amount']}")
                        print("------------------------------")
                    print("===============================\n")
                    return
                else:
                    print(f"Error getting blockchain: {response.text}")
            except requests.RequestException as e:
                print(f"Error connecting to node: {e}")
        
        # Fallback to local blockchain
        print("\n========== BLOCKCHAIN ==========")
        for block in self.blockchain.chain:
            print(f"Block #{block.index}")
            print(f"Timestamp: {block.timestamp}")
            print(f"Previous Hash: {block.previous_hash}")
            print(f"Hash: {block.hash}")
            print(f"Nonce: {block.nonce}")
            print("Transactions:")
            for tx in block.transactions:
                print(f"  From: {tx['from']} To: {tx['to']} Amount: {tx['amount']}")
            print("------------------------------")
        print("===============================\n")
    
    def _find_node_url(self) -> Optional[str]:
        """Find a running node URL"""
        # Check if we have a node running in this instance
        if self.node_url:
            return self.node_url
            
        # Try standard localhost address
        try:
            response = requests.get("http://127.0.0.1:5000/blockchain", timeout=1)
            if response.status_code == 200:
                return "http://127.0.0.1:5000"
        except requests.RequestException:
            pass
            
        return None
    
    def start_mining(self, address: str) -> None:
        """Start continuous mining process"""
        node_url = self._find_node_url()
        
        if not node_url:
            print("No node is running. Please start a node first.")
            return
            
        try:
            response = requests.post(f"{node_url}/mining/start", 
                                   json={"address": address})
            
            if response.status_code == 200:
                data = response.json()
                print(data["message"])
                print(f"Mining rewards will be sent to: {address}")
                print(f"Current difficulty: {data['difficulty']}")
            else:
                print(f"Error starting mining: {response.text}")
        except requests.RequestException as e:
            print(f"Error connecting to node: {e}")
            
    def stop_mining(self) -> None:
        """Stop continuous mining process"""
        node_url = self._find_node_url()
        
        if not node_url:
            print("No node is running.")
            return
            
        try:
            response = requests.post(f"{node_url}/mining/stop")
            
            if response.status_code == 200:
                print(response.json()["message"])
            else:
                print(f"Error stopping mining: {response.text}")
        except requests.RequestException as e:
            print(f"Error connecting to node: {e}")
            
    def get_mining_stats(self) -> None:
        """Get mining statistics"""
        node_url = self._find_node_url()
        
        if not node_url:
            print("No node is running.")
            return
            
        try:
            response = requests.get(f"{node_url}/mining/stats")
            
            if response.status_code == 200:
                stats = response.json()["stats"]
                print("\n===== MINING STATISTICS =====")
                print(f"Mining active: {stats['mining_active']}")
                print(f"Current difficulty: {stats['difficulty']}")
                print(f"Chain length: {stats['chain_length']} blocks")
                print(f"Pending transactions: {stats['pending_transactions']}")
                print("=============================\n")
            else:
                print(f"Error getting mining stats: {response.text}")
        except requests.RequestException as e:
            print(f"Error connecting to node: {e}")
            
    def set_difficulty(self, difficulty: int) -> None:
        """Set mining difficulty"""
        node_url = self._find_node_url()
        
        if not node_url:
            print("No node is running.")
            return
            
        try:
            response = requests.post(f"{node_url}/mining/difficulty", 
                                   json={"difficulty": difficulty})
            
            if response.status_code == 200:
                print(response.json()["message"])
            else:
                print(f"Error setting difficulty: {response.text}")
        except requests.RequestException as e:
            print(f"Error connecting to node: {e}")
    
    def pause_node(self, reason: str = "System maintenance") -> None:
        """Pausiert die Blockchain für Updates oder Wartung"""
        node_url = self._find_node_url()
        
        if not node_url:
            print("Kein aktiver Node gefunden. Starte zuerst einen Node.")
            return
            
        try:
            response = requests.post(f"{node_url}/blockchain/pause", 
                                   json={"reason": reason})
            
            if response.status_code == 200:
                print(response.json()["message"])
                print("Die Blockchain wurde sicher pausiert. Du kannst jetzt Updates durchführen.")
            else:
                print(f"Fehler beim Pausieren der Blockchain: {response.text}")
        except requests.RequestException as e:
            print(f"Fehler bei der Verbindung zum Node: {e}")
            
    def resume_node(self, validate: bool = True) -> None:
        """Setzt eine pausierte Blockchain fort"""
        node_url = self._find_node_url()
        
        if not node_url:
            print("Kein aktiver Node gefunden. Starte zuerst einen Node.")
            return
            
        try:
            response = requests.post(f"{node_url}/blockchain/resume", 
                                   json={"validate": validate})
            
            if response.status_code == 200:
                data = response.json()
                print(data["message"])
                
                if "validation_result" in data:
                    if data["validation_result"]["valid"]:
                        print("Blockchain-Validierung erfolgreich!")
                    else:
                        print("WARNUNG: Validierungsprobleme gefunden:")
                        for issue in data["validation_result"]["issues"]:
                            print(f"- {issue}")
            else:
                print(f"Fehler beim Fortsetzen der Blockchain: {response.text}")
        except requests.RequestException as e:
            print(f"Fehler bei der Verbindung zum Node: {e}")
            
    def create_checkpoint(self, reason: str = "Manual backup") -> None:
        """Erstellt einen Checkpoint der Blockchain"""
        node_url = self._find_node_url()
        
        if not node_url:
            print("Kein aktiver Node gefunden. Starte zuerst einen Node.")
            return
            
        try:
            response = requests.post(f"{node_url}/blockchain/checkpoint", 
                                   json={"reason": reason})
            
            if response.status_code == 200:
                print(response.json()["message"])
            else:
                print(f"Fehler beim Erstellen des Checkpoints: {response.text}")
        except requests.RequestException as e:
            print(f"Fehler bei der Verbindung zum Node: {e}")
            
    def validate_blockchain(self) -> None:
        """Führt eine vollständige Validierung der Blockchain durch"""
        node_url = self._find_node_url()
        
        if not node_url:
            print("Kein aktiver Node gefunden. Starte zuerst einen Node.")
            return
            
        try:
            response = requests.get(f"{node_url}/blockchain/validate")
            
            if response.status_code == 200:
                data = response.json()
                if data["valid"]:
                    print("Blockchain ist gültig und konsistent! ✓")
                else:
                    print("WARNUNG: Validierungsprobleme gefunden:")
                    for issue in data["issues"]:
                        print(f"- {issue}")
            else:
                print(f"Fehler bei der Blockchain-Validierung: {response.text}")
        except requests.RequestException as e:
            print(f"Fehler bei der Verbindung zum Node: {e}")


def print_help():
    """Print help information"""
    print("""
CryptoCoin - A simple cryptocurrency implementation in Python

Usage:
  python main.py [command] [options]
  
Commands:
  start-node           Start a blockchain node
  create-wallet        Generate a new wallet
  save-wallet          Save your wallet to a file
  load-wallet          Load a wallet from a file
  balance              Check the balance of an address
  send                 Send coins to another address
  mine                 Mine one block of pending transactions
  start-mining         Start continuous mining process
  stop-mining          Stop continuous mining process
  mining-stats         Get mining statistics
  set-difficulty       Set mining difficulty
  print-chain          Print the blockchain
  
Examples:
  python main.py start-node --port 5000
  python main.py create-wallet
  python main.py save-wallet --file mywallet.json
  python main.py load-wallet --file mywallet.json
  python main.py balance --address 1D3f...
  python main.py send --from 1D3f... --to 1Ab2... --amount 10 --key [private-key]
  python main.py mine --address 1D3f...
  python main.py start-mining --address 1D3f...
  python main.py stop-mining
  python main.py mining-stats
  python main.py set-difficulty --difficulty 5
  python main.py print-chain
    """)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='CryptoCoin - A simple cryptocurrency')
    parser.add_argument('command', help='Command to execute')
    parser.add_argument('--port', type=int, help='Port for the node server')
    parser.add_argument('--host', type=str, help='Host for the node server')
    parser.add_argument('--file', type=str, help='Wallet file')
    parser.add_argument('--address', type=str, help='Wallet address')
    parser.add_argument('--from', dest='sender', type=str, help='Sender address')
    parser.add_argument('--to', dest='recipient', type=str, help='Recipient address')
    parser.add_argument('--amount', type=float, help='Amount to send')
    parser.add_argument('--key', type=str, help='Private key')
    parser.add_argument('--difficulty', type=int, help='Mining difficulty')
    parser.add_argument('--reason', type=str, help='Grund für Checkpoint oder Pause')
    parser.add_argument('--skip-validation', action='store_true', help='Validierung überspringen')
    
    if len(sys.argv) <= 1:
        print_help()
        sys.exit(0)
        
    args = parser.parse_args()
    
    coin = CryptoCoin()
    
    if args.command == 'start-node':
        host = args.host or '0.0.0.0'
        port = args.port or 5000
        coin.start_node(host, port)
        print(f"Node started at http://{host}:{port}")
        try:
            print("Press Ctrl+C to stop the node")
            while True:
                pass
        except KeyboardInterrupt:
            print("Node stopped")
    elif args.command == 'pause-node':
        reason = args.reason or "Manual pause"
        coin.pause_node(reason)
        
    elif args.command == 'resume-node':
        validate = not args.skip_validation
        coin.resume_node(validate)
        
    elif args.command == 'create-checkpoint':
        reason = args.reason or "Manual backup"
        coin.create_checkpoint(reason)
        
    elif args.command == 'validate':
        coin.validate_blockchain()
            
    elif args.command == 'create-wallet':
        coin.create_wallet()
        
    elif args.command == 'save-wallet':
        if not args.file:
            print("Error: --file parameter required")
            sys.exit(1)
        coin.save_wallet(args.file)
        
    elif args.command == 'load-wallet':
        if not args.file:
            print("Error: --file parameter required")
            sys.exit(1)
        coin.load_wallet(args.file)
        
    elif args.command == 'balance':
        if not args.address:
            print("Error: --address parameter required")
            sys.exit(1)
        coin.get_balance(args.address)
        
    elif args.command == 'send':
        if not all([args.sender, args.recipient, args.amount, args.key]):
            print("Error: --from, --to, --amount and --key parameters required")
            sys.exit(1)
        coin.send_transaction(args.sender, args.recipient, args.amount, args.key)
        
    elif args.command == 'mine':
        if not args.address:
            print("Error: --address parameter required")
            sys.exit(1)
        coin.mine(args.address)
        
    elif args.command == 'start-mining':
        if not args.address:
            print("Error: --address parameter required")
            sys.exit(1)
        coin.start_mining(args.address)
        
    elif args.command == 'stop-mining':
        coin.stop_mining()
        
    elif args.command == 'mining-stats':
        coin.get_mining_stats()
        
    elif args.command == 'set-difficulty':
        if not args.difficulty:
            print("Error: --difficulty parameter required")
            sys.exit(1)
        coin.set_difficulty(args.difficulty)
        
    elif args.command == 'print-chain':
        coin.print_chain()
        
    else:
        print(f"Unknown command: {args.command}")
        print_help()
        

if __name__ == "__main__":
    main()