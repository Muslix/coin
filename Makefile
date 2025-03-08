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

.PHONY: install test test-one start-node create-wallet save-wallet load-wallet check-balance send-transaction mine start-mining stop-mining mining-stats set-difficulty print-chain get-blockchain get-block pending-transactions transaction-history register-node list-nodes resolve-conflicts health-check node-info help deploy-contract call-contract contract-state list-contracts