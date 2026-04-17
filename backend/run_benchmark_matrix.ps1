#Requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Run-Step {
    param([string]$Label, [scriptblock]$Block)
    Write-Host ""
    Write-Host "══════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host "  $Label" -ForegroundColor Cyan
    Write-Host "══════════════════════════════════════════" -ForegroundColor Cyan
    try {
        & $Block
        if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
            throw "Exit code $LASTEXITCODE"
        }
    }
    catch {
        Write-Host ""
        Write-Host "FAILED at step: $Label" -ForegroundColor Red
        Write-Host $_.Exception.Message -ForegroundColor Red
        exit 1
    }
}

Push-Location $PSScriptRoot

# ── 1. baseline ────────────────────────────────────────────────────
Run-Step "Running baseline..." {
    $env:ENABLE_RERANKING = "false"
    $env:EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    python -m app.eval_benchmark run --name baseline
}

# ── 2. reranker ────────────────────────────────────────────────────
Run-Step "Running reranker..." {
    $env:ENABLE_RERANKING = "true"
    $env:EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    python -m app.eval_benchmark run --name reranker
}

# ── 3. e5 ──────────────────────────────────────────────────────────
Run-Step "Rebuilding vector index with e5 model..." {
    $env:ENABLE_RERANKING = "false"
    $env:EMBEDDING_MODEL = "intfloat/multilingual-e5-large"
    python -m app.embed_store --rebuild
}

Run-Step "Running e5..." {
    $env:ENABLE_RERANKING = "false"
    $env:EMBEDDING_MODEL = "intfloat/multilingual-e5-large"
    python -m app.eval_benchmark run --name e5
}

# ── 4. e5-reranker ─────────────────────────────────────────────────
Run-Step "Running e5-reranker..." {
    $env:ENABLE_RERANKING = "true"
    $env:EMBEDDING_MODEL = "intfloat/multilingual-e5-large"
    python -m app.eval_benchmark run --name e5-reranker
}

# ── 5. compare ─────────────────────────────────────────────────────
Run-Step "Comparing all configurations..." {
    $env:ENABLE_RERANKING = "false"
    $env:EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    python -m app.eval_benchmark compare
}

Pop-Location
Write-Host ""
Write-Host "All benchmark runs completed." -ForegroundColor Green
