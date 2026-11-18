# Boletería

Una API chica de venta de entradas: organizadores que publican eventos y funciones, compradores que
reservan, pagan, transfieren y piden reembolsos, y un panel de administración. FastAPI, con el estado en
memoria: al reiniciarla vuelve a los datos de arranque.

Son tres comandos: levantarla, generar las identidades y, cuando haga falta, reiniciarla.

## 1. Levantarla

Con Docker, que es como la levanta el pipeline:

```bash
docker compose up -d --build
```

Queda en el puerto 8600. `docker compose restart api` la devuelve a los datos de arranque.

Sin Docker:

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn boleteria.app:app --port 8600
```

La documentación interactiva queda en `http://127.0.0.1:8600/docs` y el contrato en `openapi.json`
(se regenera con `python make_openapi.py`).

## 2. Generar las identidades

Con la API arriba, en otra terminal:

```bash
python make_identities.py
```

Inicia sesión con los cuatro usuarios de arranque y escribe `identities.toml` con sus tokens, más una
credencial falsa (`intruso`, un token con la firma cambiada) y el anónimo. Acepta la URL y el archivo de
salida: `python make_identities.py http://127.0.0.1:8600 identities.toml`. Sólo usa la biblioteca estándar.

Los tokens vencen a las doce horas y **dejan de valer cuando la API se reinicia**, porque la clave de
firma se genera al arrancar: hay que volver a correr este comando después de cada arranque. El archivo no
se versiona.

## 3. Reiniciarla

Sin bajar el servidor, vuelve a los datos de arranque:

```bash
curl -X POST http://127.0.0.1:8600/_reset
```

Los tokens de los usuarios de arranque siguen valiendo después de un reinicio de datos, así que
`identities.toml` no se regenera. Los de cuentas creadas con `POST /buyers` dejan de valer, porque esas
cuentas ya no existen.

## Windows

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn boleteria.app:app --port 8600
```

En otra terminal:

```powershell
python make_identities.py
Invoke-RestMethod -Method Post http://127.0.0.1:8600/_reset
```

## Sesiones

`POST /auth/login` recibe `{"email", "password"}` y devuelve `{"token"}`. El token va en
`Authorization: Bearer <token>`; lleva el id de la cuenta, su rol y el vencimiento, firmados. Sin token, o
con uno vencido, mal firmado o de una cuenta que ya no existe, la respuesta es 401.

| Usuario | Rol | Email | Contraseña |
|---|---|---|---|
| ana | compradora (`buyer`) | `ana@example.com` | `ana-2026` |
| beto | comprador (`buyer`) | `beto@example.com` | `beto-2026` |
| carla | compradora (`buyer`) | `carla@example.com` | `carla-2026` |
| olga | organizadora (`organizer`) | `olga@ritmo-producciones.example` | `olga-2026` |
| admin | administración (`admin`) | `admin@boleteria.example` | `admin-2026` |

Un comprador nuevo se da de alta con `POST /buyers` e inicia sesión igual que los demás.

## Datos de arranque

| Qué | Cuáles |
|---|---|
| Salas | Teatro del Puerto, Estadio Central (Buenos Aires), Sala Rivadavia (Rosario) |
| Eventos | Festival Río Sonoro (2 funciones), Hamlet (2 funciones), Noche de Stand-up (1 función), Unplugged en la Terraza (1 función de 12 lugares) |
| Cupones | `VERANO10` (10 %), `AMIGOS20` (20 %) |
| Órdenes | una paga de Ana, una reservada de Beto, dos pagas de Carla (10 de los 12 lugares del Unplugged) |

Los precios son enteros en centavos y las fechas de las funciones son tiempo Unix en segundos.

## Un recorrido

```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8600/auth/login -H "Content-Type: application/json" \
        -d '{"email": "ana@example.com", "password": "ana-2026"}' | python -c "import json,sys; print(json.load(sys.stdin)['token'])")
curl http://127.0.0.1:8600/events
curl -X POST http://127.0.0.1:8600/orders -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" -d '{"show_id": 3, "seats": 2, "coupon_code": "VERANO10"}'
curl -X POST http://127.0.0.1:8600/orders/5/pay -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" -d '{"method": "card"}'
curl http://127.0.0.1:8600/orders -H "Authorization: Bearer $TOKEN"
```

Cada pedido queda anotado en `requests.jsonl`, al lado de este archivo.
