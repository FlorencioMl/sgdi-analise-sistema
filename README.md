# SGDI - Sistema de Gestão de Demandas Internas

Plataforma web para gerenciamento centralizado de demandas internas, com controle de prioridades, auditoria completa e API REST para integrações externas.

## Como rodar

**Pré-requisitos:** Python 3.8+

```bash
pip install flask
python init_db.py
python app.py
```

Acesse: http://localhost:5000

Usuários padrão (senha: `123`): `admin`, `João Silva`, `Maria Santos`, `Pedro Costa`

## Funcionalidades

- Criar, editar e deletar demandas com priorização (Alta, Média, Baixa)
- Busca e filtro por título, solicitante e prioridade
- Visualização detalhada com histórico de comentários
- Cadastro e autenticação de usuários com senha criptografada (SHA-256)
- Dashboard gerencial com KPIs, gráficos de evolução e top solicitantes
- API REST autenticada via token com CRUD completo de demandas e comentários
- Auditoria e logs centralizados com rastreamento por usuário, IP e timestamp

## API REST

Todas as rotas exigem o header `X-API-Key: <seu_token>` (gerado em `/meu_token`).

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/api/v1/demandas` | Lista demandas |
| GET | `/api/v1/demandas/<id>` | Detalhe com comentários |
| POST | `/api/v1/demandas` | Cria demanda |
| PUT | `/api/v1/demandas/<id>` | Atualiza demanda |
| DELETE | `/api/v1/demandas/<id>` | Deleta demanda |
| GET | `/api/v1/demandas/<id>/comentarios` | Lista comentários |
| POST | `/api/v1/demandas/<id>/comentarios` | Adiciona comentário |
| GET | `/api/v1/stats` | Indicadores gerenciais |
| GET | `/api/v1/logs` | Logs de auditoria |

## Tecnologias

- **Backend:** Python 3 + Flask
- **Banco de dados:** SQLite 3
- **Frontend:** HTML, CSS, Jinja2
- **Gráficos:** Chart.js 4.4
- **Segurança:** SHA-256, tokens via `secrets`

---

*Desenvolvido em 2025*
