# Makefile für Kryptowährungsprojekt

# Variablen
PYTHON = python3
PORT = 5000
HOST = 0.0.0.0
WALLET_FILE = mywallet.json
DEFAULT_DIFFICULTY = 4

# Installation von Abhängigkeiten
install:
	pip install -r requirements.txt

# Tests ausführen
test:
	pytest tests/ -v

# Einzelnen Test ausführen
# Verwendung: make test-one TEST=test_blockchain
test-one:
	pytest tests/$(TEST).py -v

# Node starten
start-node:
	$(PYTHON) main.py start-node --port $(PORT) --host $(HOST)

# Mehrere Nodes starten (für Multi-Mining-Setups)
# Verwendung: make start-node-1 für Port 5000
start-node-1:
	$(PYTHON) main.py start-node --port 5000 --host $(HOST)

# Verwendung: make start-node-2 für Port 5001
start-node-2:
	$(PYTHON) main.py start-node --port 5001 --host $(HOST)

# Verwendung: make start-node-3 für Port 5002
start-node-3:
	$(PYTHON) main.py start-node --port 5002 --host $(HOST)

# Nodes miteinander verbinden
# Verwendung: make connect-nodes um alle lokalen Nodes (Ports 5000-5002) zu verbinden
connect-nodes:
	@echo "Verbinde Nodes miteinander..."
	curl -s -X POST -H "Content-Type: application/json" \
	-d '{"nodes": ["http://localhost:5001", "http://localhost:5002"]}' \
	http://localhost:5000/nodes/register
	curl -s -X POST -H "Content-Type: application/json" \
	-d '{"nodes": ["http://localhost:5000", "http://localhost:5002"]}' \
	http://localhost:5001/nodes/register
	curl -s -X POST -H "Content-Type: application/json" \
	-d '{"nodes": ["http://localhost:5000", "http://localhost:5001"]}' \
	http://localhost:5002/nodes/register
	@echo "Nodes verbunden!"

# Mining auf einem bestimmten Node starten
# Verwendung: make start-mining-on-node-1 ADDRESS=Ihre_Mining_Adresse
start-mining-on-node-1:
	curl -s -X POST -H "Content-Type: application/json" \
	-d '{"address": "$(ADDRESS)"}' http://localhost:5000/mining/start | python -m json.tool

# Verwendung: make start-mining-on-node-2 ADDRESS=Ihre_Mining_Adresse
start-mining-on-node-2:
	curl -s -X POST -H "Content-Type: application/json" \
	-d '{"address": "$(ADDRESS)"}' http://localhost:5001/mining/start | python -m json.tool

# Verwendung: make start-mining-on-node-3 ADDRESS=Ihre_Mining_Adresse
start-mining-on-node-3:
	curl -s -X POST -H "Content-Type: application/json" \
	-d '{"address": "$(ADDRESS)"}' http://localhost:5002/mining/start | python -m json.tool

# Mining auf einem bestimmten Node stoppen
stop-mining-on-node-1:
	curl -s -X POST http://localhost:5000/mining/stop | python -m json.tool

stop-mining-on-node-2:
	curl -s -X POST http://localhost:5001/mining/stop | python -m json.tool

stop-mining-on-node-3:
	curl -s -X POST http://localhost:5002/mining/stop | python -m json.tool

pause-node:
	$(PYTHON) main.py pause-node

resume-node:
	$(PYTHON) main.py resume-node

# Wallet erstellen
create-wallet:
	$(PYTHON) main.py create-wallet

# Wallet speichern
save-wallet:
	$(PYTHON) main.py save-wallet --file $(WALLET_FILE)

# Wallet laden
load-wallet:
	$(PYTHON) main.py load-wallet --file $(WALLET_FILE)

# Kontostand abfragen (ADDRESS als Parameter erforderlich)
# Verwendung: make check-balance ADDRESS=Ihre_Wallet_Adresse
check-balance:
	$(PYTHON) main.py balance --address $(ADDRESS)

# Transaktion senden (benötigt Parameter)
# Verwendung: make send-transaction FROM=Adresse_Sender TO=Adresse_Empfänger AMOUNT=Betrag KEY=Private_Key
send-transaction:
	$(PYTHON) main.py send --from $(FROM) --to $(TO) --amount $(AMOUNT) --key $(KEY)

# Einzelnen Block minen
# Verwendung: make mine ADDRESS=Ihre_Mining_Adresse
mine:
	$(PYTHON) main.py mine --address $(ADDRESS)

# Kontinuierliches Mining starten
# Verwendung: make start-mining ADDRESS=Ihre_Mining_Adresse
start-mining:
	$(PYTHON) main.py start-mining --address $(ADDRESS)

# Mining stoppen
stop-mining:
	$(PYTHON) main.py stop-mining

# Mining-Statistiken anzeigen
mining-stats:
	$(PYTHON) main.py mining-stats

# Mining-Schwierigkeit setzen
# Verwendung: make set-difficulty DIFFICULTY=5
set-difficulty:
	$(PYTHON) main.py set-difficulty --difficulty $(DIFFICULTY)

# Blockchain anzeigen
print-chain:
	$(PYTHON) main.py print-chain

# Ganze Blockchain über API abrufen
get-blockchain:
	curl -s http://localhost:$(PORT)/blockchain | python -m json.tool

# Einzelnen Block über API abrufen (benötigt HASH oder INDEX)
# Verwendung: make get-block HASH=block_hash oder make get-block INDEX=1
get-block:
ifdef HASH
	curl -s http://localhost:$(PORT)/block/$(HASH) | python -m json.tool
else ifdef INDEX
	curl -s http://localhost:$(PORT)/block/index/$(INDEX) | python -m json.tool
else
	@echo "Entweder HASH oder INDEX Parameter angeben"
endif

# Offene Transaktionen anzeigen
pending-transactions:
	curl -s http://localhost:$(PORT)/transactions/pending | python -m json.tool

# Transaktionshistorie für eine Adresse anzeigen
# Verwendung: make transaction-history ADDRESS=Ihre_Adresse
transaction-history:
	curl -s http://localhost:$(PORT)/transactions/history/$(ADDRESS) | python -m json.tool

# Nodes registrieren
# Verwendung: make register-node NODE=http://andere-node-ip:port
register-node:
	curl -s -X POST -H "Content-Type: application/json" \
	-d '{"nodes": ["$(NODE)"]}' http://localhost:$(PORT)/nodes/register | python -m json.tool

# Alle registrierten Nodes anzeigen
list-nodes:
	curl -s http://localhost:$(PORT)/nodes/list | python -m json.tool

# Konsensus-Algorithmus ausführen (Konflikte lösen)
resolve-conflicts:
	curl -s http://localhost:$(PORT)/nodes/resolve | python -m json.tool

# Node-Status prüfen
health-check:
	curl -s http://localhost:$(PORT)/health | python -m json.tool

# Node-Info anzeigen
node-info:
	curl -s http://localhost:$(PORT)/node/info | python -m json.tool

# Smart Contract deployen
# Verwendung: make deploy-contract FILE=contract.py OWNER=Adresse BALANCE=10.0
deploy-contract:
	@if [ ! -f "$(FILE)" ]; then \
		echo "Contract-Datei nicht gefunden: $(FILE)"; \
		exit 1; \
	fi; \
	CONTRACT=$$(cat $(FILE)); \
	curl -s -X POST -H "Content-Type: application/json" \
	-d "{\"code\": \"$$CONTRACT\", \"owner\": \"$(OWNER)\", \"initial_balance\": $(BALANCE)}" \
	http://localhost:$(PORT)/contracts/deploy | python -m json.tool

# Smart Contract Methode aufrufen
# Verwendung: make call-contract ID=contract_id METHOD=method_name SENDER=sender_address VALUE=0.0
call-contract:
	curl -s -X POST -H "Content-Type: application/json" \
	-d "{\"method\": \"$(METHOD)\", \"sender\": \"$(SENDER)\", \"args\": [], \"value\": $(VALUE)}" \
	http://localhost:$(PORT)/contracts/call/$(ID) | python -m json.tool

# Smart Contract Status abrufen
# Verwendung: make contract-state ID=contract_id
contract-state:
	curl -s http://localhost:$(PORT)/contracts/state/$(ID) | python -m json.tool

# Liste aller Smart Contracts
list-contracts:
	curl -s http://localhost:$(PORT)/contracts/list?detailed=true | python -m json.tool

# Hilfe anzeigen
help:
	@echo "Verwendung des Makefile für das Kryptowährungsprojekt:"
	@echo ""
	@echo "Tests:"
	@echo "  make test                    - Führt alle Tests aus"
	@echo "  make test-one TEST=test_name - Führt einen bestimmten Test aus"
	@echo ""
	@echo "Installation:"
	@echo "  make install                  - Installiert alle Abhängigkeiten"
	@echo ""
	@echo "Node-Verwaltung:"
	@echo "  make start-node               - Startet einen Blockchain-Node"
	@echo "  make start-node-1             - Startet Node auf Port 5000"
	@echo "  make start-node-2             - Startet Node auf Port 5001"
	@echo "  make start-node-3             - Startet Node auf Port 5002"
	@echo "  make connect-nodes            - Verbindet alle lokalen Nodes miteinander"
	@echo "  make register-node NODE=URL   - Registriert einen anderen Node"
	@echo "  make list-nodes               - Zeigt alle verbundenen Nodes"
	@echo "  make resolve-conflicts        - Führt den Konsensus-Algorithmus aus"
	@echo "  make health-check             - Prüft den Status des Nodes"
	@echo "  make node-info                - Zeigt Informationen über den Node"
	@echo ""
	@echo "Wallet-Verwaltung:"
	@echo "  make create-wallet            - Erstellt ein neues Wallet"
	@echo "  make save-wallet              - Speichert das Wallet in eine Datei"
	@echo "  make load-wallet              - Lädt ein Wallet aus einer Datei"
	@echo "  make check-balance ADDRESS=X  - Zeigt den Kontostand einer Adresse"
	@echo ""
	@echo "Transaktionen:"
	@echo "  make send-transaction FROM=X TO=Y AMOUNT=Z KEY=K  - Sendet eine Transaktion"
	@echo "  make pending-transactions      - Zeigt alle ausstehenden Transaktionen"
	@echo "  make transaction-history ADDRESS=X - Zeigt die Transaktionshistorie einer Adresse"
	@echo ""
	@echo "Mining:"
	@echo "  make mine ADDRESS=X           - Mined einen einzelnen Block"
	@echo "  make start-mining ADDRESS=X   - Startet kontinuierliches Mining"
	@echo "  make stop-mining              - Stoppt das Mining"
	@echo "  make start-mining-on-node-1 ADDRESS=X - Startet Mining auf Node 1 (Port 5000)"
	@echo "  make start-mining-on-node-2 ADDRESS=X - Startet Mining auf Node 2 (Port 5001)"
	@echo "  make start-mining-on-node-3 ADDRESS=X - Startet Mining auf Node 3 (Port 5002)"
	@echo "  make stop-mining-on-node-1    - Stoppt Mining auf Node 1"
	@echo "  make stop-mining-on-node-2    - Stoppt Mining auf Node 2"
	@echo "  make stop-mining-on-node-3    - Stoppt Mining auf Node 3"
	@echo "  make mining-stats             - Zeigt Mining-Statistiken"
	@echo "  make set-difficulty DIFFICULTY=X - Setzt die Mining-Schwierigkeit"
	@echo ""
	@echo "Blockchain-Informationen:"
	@echo "  make print-chain              - Zeigt die komplette Blockchain"
	@echo "  make get-blockchain           - Ruft die Blockchain über API ab"
	@echo "  make get-block HASH=X         - Zeigt einen Block anhand des Hash"
	@echo "  make get-block INDEX=X        - Zeigt einen Block anhand des Index"
	@echo ""
	@echo "Smart Contracts:"
	@echo "  make deploy-contract FILE=X OWNER=Y BALANCE=Z - Deployt einen Contract aus einer Datei"
	@echo "  make call-contract ID=X METHOD=Y SENDER=Z VALUE=W - Ruft eine Contract-Methode auf"
	@echo "  make contract-state ID=X      - Zeigt den Zustand eines Contracts"
	@echo "  make list-contracts           - Listet alle deployt Contracts auf"

.PHONY: install test test-one start-node start-node-1 start-node-2 start-node-3 connect-nodes start-mining-on-node-1 start-mining-on-node-2 start-mining-on-node-3 stop-mining-on-node-1 stop-mining-on-node-2 stop-mining-on-node-3 create-wallet save-wallet load-wallet check-balance send-transaction mine start-mining stop-mining mining-stats set-difficulty print-chain get-blockchain get-block pending-transactions transaction-history register-node list-nodes resolve-conflicts health-check node-info help deploy-contract call-contract contract-state list-contracts