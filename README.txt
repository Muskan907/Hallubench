# HalluBench Cinema Integration Patch

## Files
- `models/run_models.py`: adds cinema prompt handling and resolves IMDb title IDs to readable titles using the local SQLite database. It does not pass accepted answers or ground-truth values to the model.
- `evaluation/evaluate_response.py`: adds a cinema evaluator using question-level accepted answers. Director/writer IMDb person IDs are resolved to names through `data/processed/cinema/cinema.db`.
- `evaluation/run_evaluation.py`: adds `--domain cinema`, uses the question JSONL file, and avoids loading the large cinema ground-truth JSONL file.
- `tests/test_cinema_integration.py`: small local evaluator tests.

## Install from the Hallubench project root in PowerShell

First back up the current files:

```powershell
Copy-Item models/run_models.py models/run_models.py.bak
Copy-Item evaluation/evaluate_response.py evaluation/evaluate_response.py.bak
Copy-Item evaluation/run_evaluation.py evaluation/run_evaluation.py.bak
```

Extract this ZIP into the Hallubench project root and choose **Replace files**.

## Local checks

```powershell
python -m py_compile models/run_models.py evaluation/evaluate_response.py evaluation/run_evaluation.py
python -m unittest tests.test_cinema_integration -v
```

## Run a 100-question model pilot

This makes API calls and may incur provider costs. Do not run until you are ready and have configured the provider key.

```powershell
python models/run_models.py --provider openai --questions-file data/final/cinema/pilot_sample_100.json --limit 100 --run-name cinema_pilot
```

Replace `openai` with one of: `gemini`, `claude`, `grok`, `deepseek`, `qwen`.

## Evaluate responses

The response filename produced above is `results/responses/openai_cinema_pilot.jsonl`.

```powershell
python evaluation/run_evaluation.py --domain cinema --provider openai --questions data/final/cinema/pilot_sample_100.json --responses results/responses/openai_cinema_pilot.jsonl
```

The evaluator is a conservative exact-lexical baseline, not a semantic judge. Paraphrases can be marked contradicted. Review these results before reporting hallucination rates.

## Important dataset caveats
- IMDb region `IN` is Indian-market listing/release metadata, not proof of Indian film origin.
- IMDb AKA language is not necessarily the original language of the film.
- IMDb director/writer fields in the current ground truth store person IDs. The evaluator resolves those IDs to person names using the local `people` SQLite table.
- The generated questions are template-derived factual questions, not 50,000 independent scenarios.
- Check IMDb licensing restrictions before redistributing IMDb data or derived records.
