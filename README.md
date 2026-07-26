# Topic of your semestral work

# KeydMapper

KeydMapper je desktopová aplikace s grafickým uživatelským rozhraním sloužící pro pohodlné vytváření, úpravu a celkovou správu konfiguračních souborů nástroje keyd. Aplikace umožní uživateli interaktivně naklikat konfiguraci a mapování tlačítek, přičemž výsledek bude zapisovat přímo do konfiguračních souborů ve složce /etc/keyd/.

Při úpravě mapování je ve spodní části pravého Inspectoru současně vidět
**Generated config**. Změna Bindingu tak ihned zvýrazní odpovídající řádek
výsledného keyd configu. Náhled je standardně pouze pro čtení, lze jej skrýt,
zvětšit nebo přepnout tlačítkem **Edit config** do ruční editace. Změny se
obousměrně promítají mezi textovým a vizuálním editorem. Editor nabízí zvýraznění
syntaxe, čísla řádků a našeptávání kláves, akcí, globálních voleb i existujících
vrstev (našeptávání lze kdykoliv otevřít pomocí `Ctrl+Space`). Ručně vložené
komentáře, direktivy `include` a ostatní neupravované části souboru zůstávají při
generování zachované. Správnost rozpracovaného textu ověřuje přímo `keyd check`.

Fyzické rozmístění kláves je součástí stejného pracovního prostoru. Položka
**Physical layout** dole v levé navigaci přepne společné plátno do režimu
přesouvání a pojmenování kláves; pravý Inspector se změní na nástroje vybrané
klávesy. Uživatel se tedy nepřesouvá do samostatné záložky ani obrazovky.
Úvodní obrazovka zobrazuje konfigurace v kompaktním seznamu společně se
zařízením a stavem Enabled/Disabled.

## Požadavky a Závislosti

Pokud chcete aby remapování fungovalo, musíte mít nainstalovaný [keyd](https://github.com/rvaiya/keyd) a být na linuxu.
Pokud při přemapování klávesnice dojde k užítí konfigurace která znemožňuje používání počítače pro jistotu připisuji panickou sequenci přímo z [dokumentace keyd](https://github.com/rvaiya/keyd) která keyd zastaví: `backspace+escape+enter`

Aplikace je spustitelná na linuxu i na windows. Ale keyd není na windows podporovaný, takže aplikace nebude fungovat. Aplikace využívá knihovnu na grafické rozhraní PySide6 založené na Qt6. Všechny potřebné knihovny jsou definovány v `requirements.txt` a `pyproject.toml`.


## Instalace

### 1. Vytvoření virtuálního prostředí
V kořenovém adresáři projektu vytvořte nové virtuální prostředí:
```bash
python3 -m venv .venv
```

### 2. Aktivace virtuálního prostředí
* **Linux / macOS:**
  ```bash
  source .venv/bin/activate
  ```
* **Windows (PowerShell):**
  ```powershell
  .venv\Scripts\Activate.ps1
  ```

### 3. Instalace projektu do virtuálního prostření v editable režimu
Aplikace bude dostupná pod globálním příkazem `keyd-mapper` přímo v terminálu:
```bash
pip install -e .
```

## Spuštění

### a. Spuštění z terminálu (Bash / pwsh):
```bash
keyd-mapper
```

### b. Alternativní spuštění přes Python skript (bez insalace):
```bash
python KeydMapper/src/main.py
```

## Testy

### Spuštění všech testů:
```bash
pytest KeydMapper/tests
```

### Spuštění konkrétního testovacího scriptu:
```bash
pytest KeydMapper/tests/test_config.py
```
