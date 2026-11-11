# Uber Simulator

Simula uma frota de motoristas em tempo real. Tem duas telas: um **admin**, que vê
todos os motoristas num mapa mundial e controla a simulação, e um **app de motorista**,
em que uma pessoa entra no mapa e dirige.

## Como rodar

```bash
cp .env.example .env        # só na primeira vez
docker compose up --build
```

| Tela | URL |
|---|---|
| Admin | http://localhost:8080/admin |
| Motorista | http://localhost:8080/driver |
| Saúde da API | http://localhost:8080/health |

Abra as duas lado a lado. Os bots do simulador já aparecem no admin (azuis). Entre
como motorista e mova-se pelas setas, pelo arrasto do marcador ou pelo modo Auto: o
marcador laranja se move no admin.

Para recomeçar do zero, inclusive o banco: `docker compose down -v`.

## Arquitetura

```
 navegador (admin / motorista)       simulador (bots)
            │  WebSocket                  │  WebSocket (1 socket para todos os bots)
            ▼                             ▼
         ┌───────────── nginx :8080 (load balancer) ─────────────┐
         ▼              ▼              ▼              ▼
       api_1          api_2          api_3          api_4      ← iguais e sem estado
         └──────────────┴──────┬───────┴──────────────┘
                 ┌─────────────┴──────────────┐
                 ▼                            ▼
               Redis                       Postgres
   estado atual, pub/sub, cache      histórico de posições e jobs
```

- **Só WebSocket.** Telas e simulador falam com a API por um único endpoint, `/ws`.
  O HTTP serve apenas as páginas, os arquivos estáticos e o `/health`.
- **4 instâncias da API.** O nginx distribui as conexões (`least_conn`). Nenhuma
  instância guarda dado compartilhado na memória: o estado atual fica no Redis e o
  histórico no Postgres.
- **Fanout.** Cada instância só conhece os próprios sockets. Quem recebe uma posição
  a publica no canal `positions` do Redis. Todas as instâncias escutam esse canal e
  repassam o evento aos admins conectados nelas.

## O caminho de uma posição

1. O motorista se move. `publisher.js` decide se vale enviar: no máximo 1 por
   segundo, e só se andou ≥ 10 m ou se passaram 30 s (heartbeat).
2. O navegador manda `{"type":"position","lat":…,"lon":…}` pelo WebSocket.
3. `ws_handler.py` valida a mensagem e confere se o papel `driver` pode mandá-la.
4. `ingest.py` grava a posição no Redis, publica no canal `positions` e insere no
   Postgres. Se o motorista andou menos de 10 m, a mensagem conta só como heartbeat:
   renova o horário, mas não publica nem grava histórico.
5. `events.py`, em cada instância, recebe a publicação e chama `ws.py` → `broadcast`,
   que envia aos admins cuja área visível do mapa contém o ponto.
6. O admin atualiza `fleet.js`, e `map.js` anima o marcador até o novo ponto.

## Protocolo WebSocket

Toda mensagem é JSON com um campo `type`. A primeira mensagem do cliente é sempre `join`.

| Papel | Join | Pode mandar depois |
|---|---|---|
| admin | `{"type":"join","role":"admin"}` → recebe `snapshot` | `subscribe` (área do mapa), `request` |
| driver | `{"type":"join","role":"driver","driver_id","lat","lon"}` → `joined` | `position`, `request` (só ops liberadas) |
| sim | `{"type":"join","role":"sim"}` → `joined` | `sim_position` |

O servidor envia `handshake` (ao conectar), `snapshot`, `position`, `driver_removed`,
`response` e `error`. Erros nunca fecham a conexão.

**Pedido/resposta** (substitui o REST): `{"type":"request","id":"1","op":"jobs.list","payload":{}}`
recebe `{"type":"response","id":"1","ok":true,"data":[…]}`. As ops ficam em `rpc.py`:

| Op | Quem pode |
|---|---|
| `cities.list` | todos, inclusive antes do join |
| `drivers.nearby`, `drivers.history` | admin |
| `analytics.summary`, `analytics.by_city`, `analytics.timeseries` | admin (cache de 5 s) |
| `simulation.state`, `simulation.command` | admin |
| `jobs.list`, `jobs.run` | admin |

## Mapa dos arquivos

### Infraestrutura

| Arquivo | O que faz |
|---|---|
| `docker-compose.yml` | Sobe Redis, Postgres, `migrate` (cria as tabelas e termina), 4 APIs, nginx e simulador. |
| `nginx/nginx.conf` | Load balancer: distribui HTTP e WebSocket entre as 4 APIs. |
| `.env.example` | Modelo do `.env`: senha do Postgres e limites do filtro de movimento. |
| `backend/Dockerfile`, `simulator/Dockerfile` | Imagens Python. `certs/` serve para proxy corporativo (Zscaler). |

### Backend (`backend/app/`)

| Arquivo | O que faz |
|---|---|
| `main.py` | Cria o app FastAPI, as rotas das páginas, o `/health` e o `/ws`. Inicia o fanout ao subir. |
| `settings.py` | Configuração lida do ambiente (URLs, filtro de movimento). |
| `ws_handler.py` | Recebe cada mensagem do WebSocket: valida, autoriza por papel e despacha. |
| `ws.py` | `ConnectionManager`: sockets desta instância, área visível de cada admin, `broadcast`. |
| `rpc.py` | Registro das ops de pedido/resposta e de quem pode chamar cada uma. |
| `schemas.py` | Modelos pydantic das mensagens e dos comandos do simulador (uniões discriminadas por `type`). |
| `ingest.py` | Grava uma posição: Redis + pub/sub + Postgres, com a regra do heartbeat. |
| `events.py` | Pub/sub do Redis: publicar posição/remoção e o loop de fanout. |
| `store.py` | Estado atual no Redis: hash com a última posição + índice geográfico. |
| `db.py`, `models.py` | Conexão com o Postgres e as tabelas `drivers`, `positions`, `job_runs`. |
| `analytics.py` | Consultas SQL do painel Analytics e o histórico de um motorista. |
| `cache.py` | Cache-aside no Redis usado pelo analytics. |
| `jobs.py` | Job `cleanup_stale_drivers` (tira do mapa quem sumiu) e o registro das execuções. |
| `cities.py` | Cidades e seus centros; `nearest_city` classifica uma posição. |
| `geo.py` | Distância haversine em metros. |
| `alembic/` | Migrations: `versions/0001_initial.py` cria o schema. |

### Frontend (`backend/app/static/`)

| Arquivo | O que faz |
|---|---|
| `shared/connection.js` | Abre a conexão (socket + rpc) e mostra o status "conectado a X". Usado pelas duas telas. |
| `shared/socket.js` | Cliente WebSocket: conectar, enviar e receber JSON. |
| `shared/rpc.js` | Transforma `request`/`response` em Promises (casa as mensagens pelo `id`). |
| `shared/geo.js` | Matemática geográfica pura: distância, mover N metros, filtro de movimento. |
| `shared/basemap.js` | Cria o mapa Leaflet com os tiles do OpenStreetMap. |
| `admin/js/api.js` | O socket único do admin, o `join` e as funções `api.getX()` usadas pelos painéis. |
| `admin/js/main.js` | Liga tudo: recebe o stream da frota, envia a área visível, roda o render loop. |
| `admin/js/fleet.js` | Cópia local da frota (`Map` por `driver_id`). |
| `admin/js/map.js` | Marcadores em canvas, animação entre posições e trilha do motorista clicado. |
| `admin/js/sim.js`, `analytics.js`, `jobs.js` | Os três painéis da barra lateral. |
| `driver/js/main.js` | Liga tudo no app do motorista. |
| `driver/js/join.js` | Tela de entrada: validação de lat/lon e atalho de cidade. |
| `driver/js/session.js` | Id do motorista (por aba), última posição e o `join` com o servidor. |
| `driver/js/drive.js` | Tela de direção: mapa, marcador, modos manual/auto e o laço de movimento. |
| `driver/js/controls.js` | Teclado (setas/WASD) como estado: quais teclas estão pressionadas. |
| `driver/js/autodrive.js` | Modo Auto: anda até pontos aleatórios e faz paradas. |
| `driver/js/publisher.js` | Decide quando enviar: limite de 1/s + filtro de 10 m + heartbeat. |

### Simulador (`simulator/`)

| Arquivo | O que faz |
|---|---|
| `simulator.py` | Estado da simulação, os comandos do painel (canal `sim:cmd`) e o `main`. |
| `driver.py` | Um bot: percorre a rota da cidade e envia a posição a cada tick. |
| `telemetry.py` | O WebSocket do simulador, com reconexão (backoff exponencial + jitter). |
| `cities.py` | Cidades com os pontos de início e fim de cada rota. |

## Conceitos para estudar

| Conceito | Onde |
|---|---|
| Escala horizontal / API sem estado | `docker-compose.yml`, `store.py` |
| Load balancing (`least_conn`) | `nginx/nginx.conf` |
| Pub/sub e fanout | `events.py`, `ws.py` |
| Snapshot + eventos sem perder nada | `ws.py` → `finish_sync` |
| União discriminada (validação por `type`) | `schemas.py` |
| Autorização em duas camadas, negar por padrão | `ws_handler.py` (`ALLOWED`), `rpc.py` (`@op`) |
| Pedido/resposta sobre WebSocket | `rpc.py`, `shared/rpc.js` |
| Filtro de movimento (dead-band) + heartbeat | `publisher.js`, `ingest.py` |
| Cache-aside com TTL | `cache.py` |
| Upsert e log append-only | `ingest.py`, `models.py` |
| Índice geográfico | `store.py` (`GEOADD`/`GEOSEARCH`) |
| Backoff exponencial com jitter | `simulator/telemetry.py` |
| Render loop desacoplado + interpolação + canvas | `admin/js/main.js`, `map.js` |

## Limitações conhecidas

- Não há autenticação: qualquer cliente pode entrar como `admin` ou `sim`.
- Admin e motorista não reconectam sozinhos (só o simulador reconecta). Se a conexão
  cair, recarregue a página.
- O job de limpeza só roda pelo botão "Run now" do painel Jobs.

O histórico das decisões, fase a fase, está em `PLANO.md`.
