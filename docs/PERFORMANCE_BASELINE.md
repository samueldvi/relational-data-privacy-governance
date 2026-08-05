# Performance baseline

> Benchmark locale su dati esclusivamente sintetici; non è una validazione di capacità enterprise.

## Ambiente

- Data UTC: `2026-08-05T08:02:07+00:00`
- Commit: `3502ecfa7c960af85fde896c775724d2d759be98`
- Python: `3.12.10`
- Sistema: `macOS-26.3.1-arm64-arm-64bit`

## Risultati locali

| Profilo | Iterazioni | Righe cumulative | Secondi | Righe/s | Picco memoria | Output |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 1 | 2063 | 7.023 | 293.76 | 69730304 B | 202770 B |
| cumulative_20k | 10 | 20630 | 69.641 | 296.23 | 71417856 B | 202770 B |
| cumulative_100k | 49 | 101087 | 341.857 | 295.70 | 71499776 B | 202770 B |

## Durate per fase

Le durate aggregate includono generazione, inventory, profiling, classificazione, masking e validazione.
Il JSON allegato conserva il dettaglio numerico per fase.

## Limiti

I profili 20k e 100k rappresentano rispettivamente 10 e 49 esecuzioni complete cumulative del dataset baseline da 2.063 righe. Non dimostrano il comportamento di un singolo database con 20k o 100k righe, né concorrenza, saturazione, SLA o capacità enterprise. Tempi e memoria dipendono da hardware, Docker, carico del sistema e stato delle cache. Il benchmark non usa dati reali e non appartiene alla CI principale.
