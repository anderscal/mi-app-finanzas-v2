param(
    [string]$FusekiHome = "C:\Users\User\Documents\apache-jena-fuseki-6.2.0",
    [ValidateRange(1, 65535)]
    [int]$Puerto = 3030
)

$ErrorActionPreference = "Stop"

# ---------------------------------------
# 1. Ubicacion del servidor Apache Jena
# ---------------------------------------

if ([string]::IsNullOrWhiteSpace($FusekiHome)) {
    $FusekiHome = "C:\Users\User\Documents\apache-jena-fuseki-6.2.0"
}

$archivoFuseki = Join-Path `
    $FusekiHome `
    "fuseki-server.bat"

if (-not (Test-Path -LiteralPath $archivoFuseki)) {
    throw (
        "No se encontro fuseki-server.bat en: " +
        $FusekiHome +
        ". Verifica donde descomprimiste Fuseki."
    )
}

# ---------------------------------------
# 2. Ubicacion del TTL del proyecto
# ---------------------------------------

$archivoTTL = Join-Path `
    $PSScriptRoot `
    "ontologia\modeloConceptualFinal_v2.ttl"

if (-not (Test-Path -LiteralPath $archivoTTL)) {
    throw (
        "No se encontro la ontologia final: " +
        $archivoTTL
    )
}

$archivoTTL = (Resolve-Path `
    -LiteralPath $archivoTTL).Path

# ---------------------------------------
# 3. Comprobar Java
# ---------------------------------------

$comandoJava = Get-Command java `
    -ErrorAction SilentlyContinue

if (-not $comandoJava) {
    throw (
        "Java no esta disponible en PATH. " +
        "Instala Java 21 o superior."
    )
}

Write-Host ""
Write-Host "Version de Java:" -ForegroundColor Cyan
& java -version

# ---------------------------------------
# 4. Informacion del servidor
# ---------------------------------------

Write-Host ""
Write-Host "INICIANDO FUSEKI 6.2.0" -ForegroundColor Green

Write-Host ("Ontologia: " + $archivoTTL)
Write-Host "Dataset: finanzas_demo"

Write-Host (
    "Endpoint SPARQL: " +
    "http://127.0.0.1:$Puerto/finanzas_demo/sparql"
)

Write-Host (
    "Interfaz: http://localhost:$Puerto/"
)

Write-Host ""
Write-Host (
    "Deja esta ventana abierta mientras " +
    "ejecutas las pruebas."
) -ForegroundColor Yellow

Write-Host (
    "Para detener Fuseki, presiona Ctrl+C."
)

Write-Host ""

# ---------------------------------------
# 5. Iniciar el servidor
# ---------------------------------------

Push-Location -LiteralPath $FusekiHome

try {
    & $archivoFuseki `
        "--localhost" `
        "--port=$Puerto" `
        "--file=$archivoTTL" `
        "/finanzas_demo"

    if ($LASTEXITCODE -ne 0) {
        throw (
            "Fuseki finalizo con codigo: " +
            $LASTEXITCODE
        )
    }
}
finally {
    Pop-Location
}