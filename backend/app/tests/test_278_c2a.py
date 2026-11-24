"""Paso 27.8 C2.1.

Pruebas de inicializacion y separacion arquitectonica.

No modifican datos financieros.
No contactan Fuseki ni Gemini.
"""

import subprocess
import sys

from pathlib import Path

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.persistence.database import (
    SesionFinanciera,
)

from app.services import (
    semantica_auto_sync as sync,
)


BACKEND = (
    Path(__file__).resolve().parents[2]
)

APP = BACKEND / "app"


def test_278c2a_persistence_no_importa_services():

    codigo = (
        "import sys\n"
        "import app.persistence.database\n"
        "assert "
        "'app.services.semantica_auto_sync' "
        "not in sys.modules\n"
    )

    resultado = subprocess.run(
        [
            sys.executable,
            "-c",
            codigo,
        ],

        cwd=str(BACKEND),

        capture_output=True,

        text=True,

        timeout=30,
    )

    assert resultado.returncode == 0, (
        "Persistence no debe importar "
        "automaticamente el sincronizador."
    )


def test_278c2a_eventos_siguen_registrados():

    eventos = (
        (
            "before_flush",
            sync._marcar_cambios,
        ),
        (
            "after_commit",
            sync._publicar_despues_de_commit,
        ),
        (
            "after_rollback",
            sync._limpiar_rollback,
        ),
    )

    for nombre, funcion in eventos:

        assert event.contains(
            SesionFinanciera,
            nombre,
            funcion,
        ), (
            f"Evento financiero no registrado: {nombre}"
        )

        assert not event.contains(
            Session,
            nombre,
            funcion,
        ), (
            f"Evento registrado indebidamente "
            f"en la sesion base: {nombre}"
        )


def test_278c2a_recuperador_obsoleto_eliminado():

    vigente = (
        APP
        / "business"
        / "rag_retrieval_service.py"
    )

    obsoleto = (
        APP
        / "services"
        / "rag_retrieval_service.py"
    )

    assert vigente.is_file(), (
        "Debe conservarse el recuperador de Business."
    )

    assert not obsoleto.exists(), (
        "El recuperador anterior de Services "
        "todavia existe."
    )