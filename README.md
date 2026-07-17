# Leilão Calebe

Aplicação web FastAPI para o Leilão Calebe com dinheiro fictício, participantes autenticados por código de 5 dígitos, painel administrativo, SQLite e WebSocket em tempo real.

## Capacidade esperada

Para um evento presencial com cerca de 80 participantes conectados ao mesmo tempo, a VPS Lightsail informada, com 512 MB RAM, 2 vCPUs e Ubuntu, deve suportar o uso normal desta aplicação.

Condições importantes:

- usar `workers = 1` no Gunicorn por causa do SQLite;
- manter poucos uploads durante o evento;
- abrir as portas 80 e 443 no firewall do Lightsail;
- criar 1 GB de swap na VPS para evitar falta de memória;
- não usar o painel admin em várias abas fazendo muitas ações simultâneas.

O tráfego em WebSocket é leve: a tela só recebe eventos quando muda rodada, lance, cancelamento ou encerramento.

## Rodar localmente

```powershell
cd C:\Users\user\Documents\github\leilao-calebe
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -m app.create_db
python -m app.seed
python -m uvicorn app.main:app --reload
```

Acesse:

- Participante: <http://127.0.0.1:8000>
- Admin: <http://127.0.0.1:8000/admin/login>

Credenciais padrão do `.env.example`:

- Admin: `admin`
- Senha: `senha-forte`

Códigos de teste:

- João: `12345`
- Maria: `23456`
- Pedro: `34567`
- Ana: `45678`

## Testes

```powershell
python -m pytest
```

## CSV

Participantes:

```csv
nome,codigo,valor
Joao,12345,10000
Maria,,15000
```

Itens:

```csv
nome,descricao,ordem
Cesta gourmet,Produtos especiais,1
```

## Deploy na sua VPS Lightsail

Dados usados neste projeto:

- Instância: `leilao-calebe`
- IP público IPv4: `54.207.248.135`
- Usuário Ubuntu: `ubuntu`
- Chave: `C:\Users\user\Downloads\leilao\LightsailDefaultKey-sa-east-1.pem`

No PowerShell local, envie o projeto:

```powershell
cd C:\Users\user\Documents\github
scp -i C:\Users\user\Downloads\leilao\LightsailDefaultKey-sa-east-1.pem -r .\leilao-calebe ubuntu@54.207.248.135:/home/ubuntu/leilao-calebe
```

Entre na VPS:

```powershell
ssh -i C:\Users\user\Downloads\leilao\LightsailDefaultKey-sa-east-1.pem ubuntu@54.207.248.135
```

Na VPS:

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip nginx sqlite3 certbot python3-certbot-nginx
sudo mkdir -p /opt/leilao-calebe
sudo rsync -a --delete /home/ubuntu/leilao-calebe/ /opt/leilao-calebe/
sudo chown -R ubuntu:www-data /opt/leilao-calebe
cd /opt/leilao-calebe
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env
python -m app.create_db
python -m app.seed
```

No `.env`, troque pelo menos:

```env
EVENT_NAME=Leilão Calebe
SECRET_KEY=gere-uma-chave-grande-e-aleatoria
ADMIN_USERNAME=admin
ADMIN_PASSWORD=troque-esta-senha
DATABASE_URL=sqlite:///./app/leilao.db
```

## Swap recomendado para 512 MB RAM

```bash
sudo fallocate -l 1G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

## Gunicorn

```bash
cd /opt/leilao-calebe
. .venv/bin/activate
gunicorn -c gunicorn.conf.py app.main:app
```

Para SQLite, mantenha `workers = 1`.

## systemd

```bash
sudo cp /opt/leilao-calebe/systemd/leilao.service /etc/systemd/system/leilao.service
sudo systemctl daemon-reload
sudo systemctl enable --now leilao
sudo systemctl status leilao
```

## Nginx

```bash
sudo cp /opt/leilao-calebe/nginx/leilao.conf /etc/nginx/sites-available/leilao
sudo ln -sf /etc/nginx/sites-available/leilao /etc/nginx/sites-enabled/leilao
sudo nginx -t
sudo systemctl reload nginx
```

Acesse:

- <http://54.207.248.135>
- <http://54.207.248.135/admin/login>

O arquivo de Nginx já inclui proxy para WebSocket.

## HTTPS com Certbot

Quando apontar um domínio para `54.207.248.135`, edite `nginx/leilao.conf`, troque o `server_name` pelo domínio e rode:

```bash
sudo certbot --nginx -d seu-dominio.com
```

Com IP puro, navegador não terá HTTPS válido por Certbot; use domínio para HTTPS.

## Backup SQLite

Backup manual seguro:

```bash
cd /opt/leilao-calebe
mkdir -p backups
sqlite3 app/leilao.db ".backup 'backups/leilao-$(date +%F-%H%M).db'"
```

Cron diário:

```bash
0 2 * * * cd /opt/leilao-calebe && sqlite3 app/leilao.db ".backup 'backups/leilao-$(date +\%F).db'"
```

## Docker opcional

```bash
cp .env.example .env
docker compose up --build
```

## Fluxo do evento

1. Cadastre ou importe participantes.
2. Cadastre ou importe itens.
3. No dashboard admin, inicie a rodada de um item.
4. Participantes conectados veem o item em tempo real.
5. Cada participante confirma interesse com seu valor fixo.
6. Admin encerra a rodada.
7. O maior valor vence; em empate vence quem confirmou primeiro.
8. O vencedor fica bloqueado para próximas rodadas.