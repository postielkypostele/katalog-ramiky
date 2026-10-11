# Katalóg rámiky – PostielkyPostele.sk

Každý deň ráno sa automaticky:
1. stiahne produktový feed z e-shopu (`facebook.xml`),
2. ku každému produktu sa nakreslí obrázok 1080×1080 s rámikom (logo, cena, kód zľavy, Snívko, výhody),
3. zverejní sa doplnkový feed `feed.csv` (stĺpce `id`, `image_link`) pre katalóg v Meta Commerce Manageri.

E-shop sa nemení – rámik vidno iba v reklamách.

## Čo sa dá meniť (súbor `config.json`)
- `akcia.aktivna` – `true` / `false` (zapnúť/vypnúť kódy zľavy na rámiku)
- `akcia.od`, `akcia.do` – dátumy akcie; mimo nich sa kód nezobrazí
- `akcia.pravidla` – ktorý kód platí pre ktoré produkty
- `vyhody` – texty bielych štítkov vpravo
- `lifestyle` – ID produktu → URL fotky v izbe (použije sa namiesto bielej fotky)

Po uložení zmeny sa obrázky pregenerujú samy do pár minút.

## Ručné spustenie
Záložka **Actions** → **Ramiky pre katalog** → **Run workflow**.

## Adresy
- prehľad: https://postielkypostele.github.io/katalog-ramiky/
- feed pre Metu: https://postielkypostele.github.io/katalog-ramiky/feed.csv
