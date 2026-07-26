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

Vizuální Binding editor pokrývá také všechny akce keyd (`oneshot`, `swap`,
`toggle`, `setlayout`, `clear`, `repeat`, `overload*`, `lettermod`, `timeout`,
`macro2`, `command` a `noop`). Makro varianty nejsou v nabídce duplikované:
například u běžné akce **Hold layer** lze zapnout **Also run a macro** a
KeydMapper automaticky vygeneruje odpovídající `layerm(...)`. Stejný model platí
pro `oneshotm`, `swapm`, `togglem` a `clearm`; existující ručně zapsané varianty
se zpětně načtou do stejných vizuálních ovládacích prvků.

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

### 4. Instalace systémového helperu (Linux)

Apply, Enable a Disable potřebují bezpečně zapisovat do `/etc/keyd`. Nainstalujte
proto malý privilegovaný helper a jeho Polkit policy:

```bash
sudo ./scripts/install-system-helper.sh
```

Instalátor zkopíruje helper jako rootem vlastněný soubor do `/usr/libexec` a
policy do `/usr/share/polkit-1/actions`. Aplikace nikdy nespouští svou
uživatelsky zapisovatelnou vývojovou kopii jako root.

Při prvním systémovém Apply se zobrazí standardní Polkit dialog.
Potom aplikace používá jeden úzce omezený privilegovaný proces, takže další
Apply, Enable nebo Disable v téže spuštěné instanci už heslo nevyžadují.
Pomocník je připojený pouze přes privátní roury k danému procesu KeydMapperu;
při zavření nebo pádu aplikace dostane EOF a skončí. Při příštím spuštění
aplikace se proto autorizace provede znovu.
Lokální editace a nahrávání kláves žádná zvýšená oprávnění nepotřebují.

Helper nepoužívá shell: přijímá config přes standardní vstup, kontroluje název,
spustí `keyd check`, provede atomickou výměnu v `/etc/keyd` a restartuje
`keyd.service`. Pokud validace nebo restart selže, obnoví předchozí soubory.

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
