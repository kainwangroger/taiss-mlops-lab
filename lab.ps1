<#
.SYNOPSIS
    Les commandes du lab MLOps, sous Windows.

.DESCRIPTION
    `make` n'est pas installe par defaut sous Windows. Ce script expose
    exactement les memes cibles que le Makefile, avec les memes noms :

        .\lab.ps1 smoke
        .\lab.ps1 console
        .\lab.ps1 up

    Partout ou la documentation ecrit `make <cible>`, ecrivez `.\lab.ps1 <cible>`.

.EXAMPLE
    .\lab.ps1 help
#>

param(
    [Parameter(Position = 0)]
    [ValidateSet('help', 'install', 'install-console', 'smoke', 'train', 'evaluate',
                 'test', 'lint', 'serve', 'console', 'replay', 'drift',
                 'up', 'down', 'logs', 'clean')]
    [string]$Cible = 'help'
)

$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

function Ecrire($message) { Write-Host $message }

function Verifier-CodeRetour($quoi) {
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "ECHEC : $quoi (code $LASTEXITCODE)" -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

switch ($Cible) {

    'help' {
        Ecrire "Cibles disponibles :"
        Ecrire "  .\lab.ps1 install          installe les dependances"
        Ecrire "  .\lab.ps1 install-console  installe les dependances de la console"
        Ecrire "  .\lab.ps1 smoke            verifie que le poste est pret   <- a lancer en premier"
        Ecrire "  .\lab.ps1 train            entraine le modele"
        Ecrire "  .\lab.ps1 test             lance toute la suite de tests"
        Ecrire "  .\lab.ps1 lint             verifie le style"
        Ecrire "  .\lab.ps1 serve            demarre l'API en local sur le port 8000"
        Ecrire "  .\lab.ps1 console          ouvre la console du participant sur le port 8501"
        Ecrire "  .\lab.ps1 up               demarre console + API + Prometheus + Grafana"
        Ecrire "  .\lab.ps1 replay           rejoue du trafic normal"
        Ecrire "  .\lab.ps1 drift            rejoue le trafic 2026 et produit le rapport"
        Ecrire "  .\lab.ps1 logs             affiche la fin du journal logs\lab.log"
        Ecrire "  .\lab.ps1 down             arrete la pile"
        Ecrire "  .\lab.ps1 clean            supprime modele, rapports et journaux"
    }

    'install' {
        python -m pip install -r requirements.txt
        Verifier-CodeRetour "installation des dependances"
    }

    'install-console' {
        python -m pip install -r requirements-console.txt
        Verifier-CodeRetour "installation des dependances de la console"
    }

    'smoke' {
        Ecrire "1/4  version de Python"
        python -c "import sys; v=sys.version_info; assert v[:2]>=(3,11), 'Python 3.11 requis'; print('     ', sys.version.split()[0])"
        Verifier-CodeRetour "version de Python"

        Ecrire "2/4  dependances"
        python -c "import pandas, sklearn, fastapi, prometheus_client, yaml; print('      OK')"
        Verifier-CodeRetour "dependances"

        Ecrire "3/4  jeux de donnees"
        python -c "import pandas as pd; d=pd.read_csv('data/reference_2025.csv'); print(f'      reference_2025.csv : {len(d)} lignes')"
        Verifier-CodeRetour "jeux de donnees"

        Ecrire "4/4  entrainement rapide"
        python -m src.train | Out-Null
        Verifier-CodeRetour "entrainement"
        Ecrire "      modele entraine"

        Ecrire ""
        Write-Host "OK - votre poste est pret." -ForegroundColor Green
    }

    'train'    { python -m src.train;    Verifier-CodeRetour "entrainement" }
    'evaluate' { python -m src.evaluate; Verifier-CodeRetour "porte de qualite" }
    'test'     { python -m pytest tests/ -q; Verifier-CodeRetour "tests" }
    'lint'     { python -m ruff check src tests; Verifier-CodeRetour "lint" }

    'serve' {
        python -m uvicorn src.serve:app --host 0.0.0.0 --port 8000 --reload
    }

    'console' {
        # Lancee ici, la console voit l'environnement Python reel du poste :
        # c'est le seul mode qui valide l'onglet « Mon poste » en entier.
        python -m streamlit run src/console.py --server.port 8501 --browser.gatherUsageStats false
    }

    'replay' {
        python -m src.replay --n 500 --url http://localhost:8001
        Verifier-CodeRetour "rejeu du trafic normal"
    }

    'drift' {
        python -m src.replay --input data/drifted_2026.csv --n 800 --url http://localhost:8001
        Verifier-CodeRetour "rejeu du trafic 2026"
        python -m src.drift_report
        Verifier-CodeRetour "rapport de derive"
        Ecrire ""
        Ecrire "Ouvrez reports\derive.html dans votre navigateur."
    }

    'up' {
        docker compose up -d --build
        Verifier-CodeRetour "demarrage de la pile"
        Ecrire ""
        Ecrire "  Console    http://localhost:8502     <- commencez ici"
        Ecrire "  API        http://localhost:8001/docs"
        Ecrire "  Prometheus http://localhost:9091"
        Ecrire "  Grafana    http://localhost:3002"
    }

    'down' {
        docker compose down
        Verifier-CodeRetour "arret de la pile"
    }

    'logs' {
        $journal = Join-Path $PSScriptRoot "logs\lab.log"
        if (Test-Path $journal) {
            Get-Content $journal -Tail 40
        } else {
            Ecrire "Aucun journal pour l'instant. Lancez .\lab.ps1 train."
        }
    }

    'clean' {
        Remove-Item models\*.pkl, reports\*.json, reports\*.html, reports\*.csv `
            -ErrorAction SilentlyContinue
        Remove-Item logs\*.log, logs\*.log.* -ErrorAction SilentlyContinue
        Get-ChildItem -Path . -Include __pycache__ -Recurse -Directory |
            Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
        Ecrire "Modele, rapports, journaux et caches supprimes."
    }
}
