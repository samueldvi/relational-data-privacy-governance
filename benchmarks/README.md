# Benchmark della pipeline

I benchmark usano soltanto il dataset sintetico versionato e non appartengono
alla CI principale. Avviare PostgreSQL, attivare la virtualenv e usare:

```bash
python benchmarks/run_pipeline_benchmark.py --profile baseline
python benchmarks/run_pipeline_benchmark.py
```

Il primo comando è rapido. Il secondo esegue anche i workload cumulativi da
circa 20k e 100k righe e aggiorna `output/benchmark_results.json` e
`docs/PERFORMANCE_BASELINE.md`. Non usare i risultati per dichiarazioni di
capacità enterprise o per confronti tra hardware non equivalenti.
