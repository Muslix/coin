#!/usr/bin/env python3
"""
Start-Skript für mehrere Blockchain-Nodes auf verschiedenen Ports
"""
import subprocess
import time
import sys
import os
import signal
import threading
import requests
import json

# Liste der zu startenden Ports
PORTS = [5000, 5001, 5002]
# Prozesse speichern
processes = []

def start_node(port):
    """Startet einen Node auf dem angegebenen Port"""
    cmd = f"python main.py start-node --port {port}"
    print(f"Starte Node auf Port {port}...")
    
    # Starte den Node im Hintergrund und speichere den Prozess
    process = subprocess.Popen(cmd, shell=True)
    processes.append(process)
    
    # Warte, bis der Node erreichbar ist
    start_time = time.time()
    while time.time() - start_time < 10:  # Timeout nach 10 Sekunden
        try:
            response = requests.get(f"http://localhost:{port}/health", timeout=1)
            if response.status_code == 200:
                print(f"Node auf Port {port} bereit: {response.json()}")
                return True
        except requests.RequestException:
            time.sleep(0.5)
    
    print(f"Timeout beim Starten des Node auf Port {port}")
    return False

def connect_nodes():
    """Verbindet alle Nodes miteinander"""
    print("\nVerbinde Nodes miteinander...")
    all_connected = True
    
    for port in PORTS:
        # Liste aller anderen Ports
        other_ports = [p for p in PORTS if p != port]
        nodes_list = [f"http://localhost:{p}" for p in other_ports]
        
        try:
            response = requests.post(
                f"http://localhost:{port}/nodes/register", 
                json={"nodes": nodes_list},
                timeout=2
            )
            
            if response.status_code == 200:
                print(f"Node {port} verbunden mit: {', '.join(map(str, other_ports))}")
            else:
                print(f"Fehler beim Verbinden von Node {port}: {response.text}")
                all_connected = False
                
        except requests.RequestException as e:
            print(f"Fehler bei der Verbindung zu Node {port}: {e}")
            all_connected = False
    
    return all_connected

def cleanup(signum=None, frame=None):
    """Beendet alle Node-Prozesse"""
    print("\nBeende alle Nodes...")
    for process in processes:
        try:
            process.terminate()
            process.wait(timeout=2)
        except:
            # Falls terminate nicht funktioniert, kill verwenden
            try:
                process.kill()
            except:
                pass
    
    print("Alle Nodes beendet.")
    sys.exit(0)

def main():
    # Signal-Handlers registrieren
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)
    
    print("=== Blockchain Multi-Node-System ===")
    
    # Starte jeden Node
    for port in PORTS:
        if not start_node(port):
            print(f"Node auf Port {port} konnte nicht gestartet werden.")
            cleanup()
            return
    
    # Kleine Pause zum Starten der Server
    print("\nWarte 2 Sekunden, bis alle Nodes vollständig gestartet sind...")
    time.sleep(2)
    
    # Verbinde die Nodes
    if connect_nodes():
        print("\nAlle Nodes erfolgreich gestartet und verbunden!")
        print("\nFür jeden Node kannst du jetzt Mining in verschiedenen Terminals starten:")
        for port in PORTS:
            print(f"curl -s -X POST -H \"Content-Type: application/json\" -d '{{\"address\": \"DEINE_ADRESSE\"}}' http://localhost:{port}/mining/start")
        
        print("\nDrücke Ctrl+C, um alle Nodes zu beenden.")
        
        # Warte auf Benutzerabbruch
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Keyboard-Interrupt empfangen.")
            cleanup()
    else:
        print("\nFehler beim Verbinden der Nodes.")
        cleanup()

if __name__ == "__main__":
    main()