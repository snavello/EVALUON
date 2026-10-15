#Requires -RunAsAdministrator
<#
.SYNOPSIS
Aplica el acceso por red de EVALUON: Caddy como servicio, el Caddyfile desde el .env y la regla del
firewall de Windows (plan 007, T-269; REQ-109, REQ-110, REQ-116; ADR-0061).

.DESCRIPTION
Se corre en PowerShell como administrador, desde la raíz del repositorio:

    powershell -ExecutionPolicy Bypass -File scripts\red\aplicar-red.ps1

La primera vez baja Caddy (la versión de scripts\red\caddy.sha512), comprueba su suma SHA-512 con la
publicada, lo deja en C:\EVALUON-red\ y lo registra como servicio EVALUON-Caddy con arranque
automático. Es el único paso con internet.

Siempre:
  1. arma C:\EVALUON-red\Caddyfile desde el .env (scripts\red\caddy.py, que valida la lista);
  2. lo comprueba con caddy.exe validate;
  3. crea o actualiza la regla de entrada «EVALUON» del firewall: TCP 80 y 443, solo caddy.exe,
     solo desde las computadoras de la lista y este equipo, en todos los perfiles de red;
  4. reinicia el servicio;
  5. muestra la lista y el resultado.

Para agregar o quitar una computadora, o para poner el certificado del área de sistemas: editar el
.env (o reemplazar los dos archivos de C:\EVALUON-red\certificados\) y volver a correrlo. Los pasos
están en specs\007-acceso-por-red\entorno.md.
#>
[CmdletBinding()]
param(
    # El .env de EVALUON (por omisión, el de la raíz del repositorio).
    [string]$EnvFile = (Join-Path (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) '.env'),
    # La carpeta de Caddy y del certificado, fuera del repositorio.
    [string]$Carpeta = 'C:\EVALUON-red'
)

$ErrorActionPreference = 'Stop'
# Sin la barra de progreso, Invoke-WebRequest baja el archivo mucho más rápido.
$ProgressPreference = 'SilentlyContinue'

$Servicio = 'EVALUON-Caddy'
$Regla = 'EVALUON'
$Caddy = Join-Path $Carpeta 'caddy.exe'
$Caddyfile = Join-Path $Carpeta 'Caddyfile'
$Sumas = Join-Path $PSScriptRoot 'caddy.sha512'
$LineaDeSuma = '^([0-9a-f]{128})\s+\*?(caddy_([0-9.]+)_windows_amd64\.zip)$'

function Paso([string]$Texto) {
    Write-Host ''
    Write-Host "== $Texto" -ForegroundColor Cyan
}

function Falla([string]$Texto) {
    Write-Host ''
    Write-Host "ERROR: $Texto" -ForegroundColor Red
    exit 1
}

# Corre un programa y devuelve lo que escribió (salida y errores) como texto, sin cortar el script
# porque escriba en la salida de errores; el resultado se mira en $LASTEXITCODE.
function Ejecutar([string]$Programa, [string[]]$Argumentos) {
    $anterior = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $texto = & $Programa @Argumentos 2>&1 | ForEach-Object { "$_" }
    } finally {
        $ErrorActionPreference = $anterior
    }
    return $texto
}

if (-not (Test-Path -LiteralPath $EnvFile -PathType Leaf)) {
    Falla "No se encontró el .env en $EnvFile."
}
if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    Falla 'No se encontró Python (el lanzador py). Instalar Python 3 para todos los usuarios y volver a correr.'
}
New-Item -ItemType Directory -Force -Path $Carpeta | Out-Null

# --- La primera vez: bajar Caddy y comprobarlo --------------------------------------------------
if (-not (Test-Path -LiteralPath $Caddy -PathType Leaf)) {
    Paso 'Bajando Caddy (solo la primera vez)'
    $linea = Get-Content -LiteralPath $Sumas | Where-Object { $_ -match $LineaDeSuma } | Select-Object -First 1
    if (-not $linea) { Falla "No está la suma SHA-512 del zip de Windows en $Sumas." }
    $null = $linea -match $LineaDeSuma
    $suma = $Matches[1]
    $zip = $Matches[2]
    $version = $Matches[3]
    $url = "https://github.com/caddyserver/caddy/releases/download/v$version/$zip"
    $temporal = Join-Path $env:TEMP "evaluon-caddy-$version"
    if (Test-Path -LiteralPath $temporal) { Remove-Item -LiteralPath $temporal -Recurse -Force }
    New-Item -ItemType Directory -Path $temporal | Out-Null
    $archivo = Join-Path $temporal $zip
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    Write-Host "Caddy $version desde $url"
    Invoke-WebRequest -Uri $url -OutFile $archivo -UseBasicParsing
    $real = (Get-FileHash -Algorithm SHA512 -LiteralPath $archivo).Hash.ToLowerInvariant()
    if ($real -ne $suma) {
        Remove-Item -LiteralPath $temporal -Recurse -Force
        Falla "La suma SHA-512 del archivo bajado no coincide con la publicada ($Sumas). No se instaló nada."
    }
    Write-Host 'Suma SHA-512 comprobada: coincide con la publicada.'
    Expand-Archive -LiteralPath $archivo -DestinationPath $temporal -Force
    Copy-Item -LiteralPath (Join-Path $temporal 'caddy.exe') -Destination $Caddy
    Remove-Item -LiteralPath $temporal -Recurse -Force
}

if (-not (Get-Service -Name $Servicio -ErrorAction SilentlyContinue)) {
    Paso "Registrando el servicio $Servicio (arranque automático)"
    New-Service -Name $Servicio -DisplayName 'EVALUON Caddy (acceso por red)' `
        -Description "Intermediario cifrado de EVALUON (plan 007). Configuración: $Caddyfile" `
        -BinaryPathName "`"$Caddy`" run --config `"$Caddyfile`" --adapter caddyfile" `
        -StartupType Automatic | Out-Null
}

# --- Siempre: Caddyfile, comprobación, firewall y reinicio -----------------------------------------
Paso 'Armando el Caddyfile desde el .env'
# Los errores de caddy.py salen directo en la pantalla; la salida es una línea JSON.
$salida = & py -3 (Join-Path $PSScriptRoot 'caddy.py') --env $EnvFile --carpeta $Carpeta --json
if ($LASTEXITCODE -ne 0) { Falla 'Corregir lo que se indica arriba y volver a correr este script.' }
$red = ($salida -join "`n") | ConvertFrom-Json
Write-Host "Caddyfile escrito en $Caddyfile."

Paso 'Comprobando el Caddyfile con Caddy'
$comprobacion = Ejecutar $Caddy @('validate', '--config', $Caddyfile, '--adapter', 'caddyfile')
if ($LASTEXITCODE -ne 0) {
    $comprobacion | ForEach-Object { Write-Host $_ }
    Falla 'Caddy no aceptó la configuración (arriba, el motivo). Si habla del certificado, revisar los dos archivos de la carpeta certificados.'
}
Write-Host 'Caddy acepta la configuración.'

Paso "Regla del firewall «$Regla»"
$permitidas = @($red.allowed_ips)
Get-NetFirewallRule -DisplayName $Regla -ErrorAction SilentlyContinue | Remove-NetFirewallRule
New-NetFirewallRule -DisplayName $Regla `
    -Description 'EVALUON (plan 007): solo las computadoras de la lista y este equipo llegan a Caddy por TCP 80 y 443. La arma scripts\red\aplicar-red.ps1.' `
    -Direction Inbound -Action Allow -Protocol TCP -LocalPort 80, 443 -Program $Caddy `
    -RemoteAddress $permitidas -Profile Any | Out-Null
Write-Host "Entrada por TCP 80 y 443 solo desde: $($permitidas -join ', ')"

# Si alguien corrió este caddy.exe a mano y no permitió el aviso del firewall, Windows creó solo
# reglas de entrada «Block» para él. Ganan sobre la regla «EVALUON» y dejan afuera a todas las
# computadoras, sin ningún mensaje. Son de este mismo programa: se quitan, y se dice.
$programa = [IO.Path]::GetFullPath($Caddy)
$bloqueos = @(Get-NetFirewallApplicationFilter |
    Where-Object { $_.Program -and [Environment]::ExpandEnvironmentVariables($_.Program) -eq $programa } |
    Get-NetFirewallRule | Where-Object { $_.Action -eq 'Block' })
foreach ($bloqueo in $bloqueos) {
    $bloqueo | Remove-NetFirewallRule
    Write-Host "Se quitó la regla «$($bloqueo.DisplayName)» ($($bloqueo.Direction), Block), que Windows creó para $Caddy y que bloqueaba la entrada." -ForegroundColor Yellow
}

Paso "Reiniciando el servicio $Servicio"
try {
    Restart-Service -Name $Servicio
} catch {
    Falla 'El servicio no arrancó. Ver «Si algo no anda» en specs\007-acceso-por-red\entorno.md (por ejemplo, otro programa ya usa el puerto 80 o 443).'
}
$escucha = $false
for ($i = 0; $i -lt 10 -and -not $escucha; $i++) {
    Start-Sleep -Seconds 1
    $escucha = [bool](Get-NetTCPConnection -State Listen -LocalPort 443 -ErrorAction SilentlyContinue)
}
$estado = (Get-Service -Name $Servicio).Status
if ($estado -ne 'Running' -or -not $escucha) {
    Falla "El servicio quedó $estado y el puerto 443 no atiende. Ver «Si algo no anda» en specs\007-acceso-por-red\entorno.md."
}

Paso 'Listo'
$computadoras = @($red.computers)
Write-Host "Dirección: https://$($red.address)"
Write-Host "Este equipo: $($red.server_ip) (entra como equipo-del-sistema)"
Write-Host "Computadoras de la lista ($($computadoras.Count) de 10):"
if ($computadoras.Count -eq 0) { Write-Host '  ninguna: solo entra este equipo' }
foreach ($computadora in $computadoras) {
    Write-Host ('  {0,-24} {1}' -f $computadora.name, $computadora.ip)
}
Write-Host "Servicio ${Servicio}: $estado, atiende en 80 y 443."
Write-Host 'Si se cambió DJANGO_ALLOWED_HOSTS en el .env, recrear la aplicación desde la raíz del repositorio: docker compose up -d'
