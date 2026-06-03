from flask import Flask, render_template, request, redirect, flash, session, jsonify
import sqlite3
from datetime import datetime
from functools import wraps
import secrets
import hashlib

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def get_db():
    conn = sqlite3.connect('demandas.db')
    conn.row_factory = sqlite3.Row
    return conn


def hash_senha(senha):
    return hashlib.sha256(senha.encode()).hexdigest()


def parse_data(data_str):
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(data_str, fmt)
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# SISTEMA DE LOGS / AUDITORIA
# ---------------------------------------------------------------------------

def registrar_log(acao, entidade=None, entidade_id=None, detalhe=None, origem='web'):
    """
    Registra um evento de auditoria na tabela logs.

    Parâmetros:
        acao        — ex: 'LOGIN', 'CRIAR_DEMANDA', 'DELETAR_DEMANDA'
        entidade    — ex: 'demanda', 'usuario', 'comentario', 'token'
        entidade_id — ID do registro afetado (opcional)
        detalhe     — texto livre com contexto adicional
        origem      — 'web' (sessão) ou 'api' (token)
    """
    try:
        usuario_id   = session.get('usuario_id')
        usuario_nome = session.get('usuario_nome', 'sistema')
        ip           = request.remote_addr
        user_agent   = request.headers.get('User-Agent', '')[:200]

        # Para chamadas via API, identifica o token usado
        if origem == 'api':
            token_header = request.headers.get('X-API-Key', '')
            usuario_nome = f'api:{token_header[:8]}...' if token_header else 'api'

        conn = get_db()
        conn.execute("""
            INSERT INTO logs
                (usuario_id, usuario_nome, acao, entidade, entidade_id,
                 detalhe, ip, user_agent, origem, criado_em)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            usuario_id,
            usuario_nome,
            acao,
            entidade,
            entidade_id,
            detalhe,
            ip,
            user_agent,
            origem,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        conn.commit()
        conn.close()
    except Exception:
        pass  # log nunca deve quebrar a requisição principal


# ---------------------------------------------------------------------------
# DECORATORS
# ---------------------------------------------------------------------------

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'usuario_id' not in session:
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated


def api_key_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('X-API-Key') or request.args.get('api_key')
        if not token:
            return jsonify({'erro': 'Token ausente. Envie X-API-Key no header.'}), 401

        conn = get_db()
        registro = conn.execute(
            "SELECT * FROM api_tokens WHERE token=? AND ativo=1", (token,)
        ).fetchone()
        conn.close()

        if not registro:
            registrar_log('API_ACESSO_NEGADO', detalhe='Token inválido ou inativo', origem='api')
            return jsonify({'erro': 'Token inválido ou inativo.'}), 403

        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# ROTAS WEB — AUTENTICAÇÃO
# ---------------------------------------------------------------------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        nome  = request.form['nome']
        senha = request.form['senha']

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM usuarios WHERE nome=? AND (senha=? OR senha=?)",
            (nome, hash_senha(senha), senha)
        ).fetchone()
        conn.close()

        if user:
            session['usuario_id']   = user['id']
            session['usuario_nome'] = user['nome']
            registrar_log('LOGIN', entidade='usuario', entidade_id=user['id'],
                          detalhe=f'Login bem-sucedido: {nome}')
            return redirect('/')
        else:
            registrar_log('LOGIN_FALHA', entidade='usuario',
                          detalhe=f'Tentativa de login falhou para: {nome}')
            flash("Login inválido")

    return render_template('login.html')


@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        nome  = request.form['nome']
        senha = request.form['senha']

        conn = get_db()
        try:
            cursor = conn.execute(
                "INSERT INTO usuarios (nome, senha) VALUES (?, ?)",
                (nome, hash_senha(senha))
            )
            conn.commit()
            novo_id = cursor.lastrowid
            session['usuario_id']   = novo_id
            session['usuario_nome'] = nome
            registrar_log('CADASTRO_USUARIO', entidade='usuario', entidade_id=novo_id,
                          detalhe=f'Novo usuário cadastrado: {nome}')
        except sqlite3.IntegrityError:
            registrar_log('CADASTRO_FALHA', entidade='usuario',
                          detalhe=f'Tentativa de cadastro com nome duplicado: {nome}')
            flash("Usuário já existe")
            return redirect('/cadastro')
        finally:
            conn.close()

        return redirect('/login')

    return render_template('cadastro.html')


@app.route('/logout')
def logout():
    registrar_log('LOGOUT', entidade='usuario', entidade_id=session.get('usuario_id'),
                  detalhe=f'Logout: {session.get("usuario_nome")}')
    session.clear()
    return redirect('/login')


# ---------------------------------------------------------------------------
# ROTAS WEB — DEMANDAS
# ---------------------------------------------------------------------------

@app.route('/')
@login_required
def index():
    prioridade = request.args.get('prioridade')
    usuario    = request.args.get('usuario')

    conn   = get_db()
    query  = "SELECT * FROM demandas WHERE 1=1"
    params = []

    if prioridade and prioridade != 'Todas':
        query += " AND prioridade=?"
        params.append(prioridade)

    if usuario:
        query += " AND solicitante LIKE ?"
        params.append(f'%{usuario}%')

    query += """
    ORDER BY
        CASE prioridade
            WHEN 'Alta'  THEN 1
            WHEN 'Media' THEN 2
            WHEN 'Baixa' THEN 3
        END,
        datetime(data_criacao) DESC
    """

    demandas = conn.execute(query, params).fetchall()
    conn.close()
    return render_template('index.html', demandas=demandas)


@app.route('/nova_demanda', methods=['GET', 'POST'])
@login_required
def nova_demanda():
    conn     = get_db()
    usuarios = conn.execute("SELECT nome FROM usuarios").fetchall()

    if request.method == 'POST':
        try:
            cursor = conn.execute("""
                INSERT INTO demandas (titulo, descricao, solicitante, data_criacao, prioridade)
                VALUES (?, ?, ?, ?, ?)
            """, (
                request.form['titulo'],
                request.form['descricao'],
                request.form['solicitante'],
                datetime.now(),
                request.form['prioridade']
            ))
            conn.commit()
            novo_id = cursor.lastrowid
            registrar_log('CRIAR_DEMANDA', entidade='demanda', entidade_id=novo_id,
                          detalhe=f'Título: {request.form["titulo"]} | Prioridade: {request.form["prioridade"]}')
        finally:
            conn.close()
        return redirect('/')

    conn.close()
    return render_template('nova_demanda.html', usuarios=usuarios)


@app.route('/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar(id):
    conn = get_db()

    if request.method == 'POST':
        # Captura valores anteriores para o log
        antes = conn.execute("SELECT titulo, prioridade FROM demandas WHERE id=?", (id,)).fetchone()

        conn.execute("""
            UPDATE demandas
            SET titulo=?, descricao=?, prioridade=?
            WHERE id=?
        """, (
            request.form['titulo'],
            request.form['descricao'],
            request.form['prioridade'],
            id
        ))
        conn.commit()
        conn.close()

        detalhe = (
            f'Antes: título="{antes["titulo"]}" prioridade={antes["prioridade"]} | '
            f'Depois: título="{request.form["titulo"]}" prioridade={request.form["prioridade"]}'
        ) if antes else f'Demanda {id} atualizada'

        registrar_log('EDITAR_DEMANDA', entidade='demanda', entidade_id=id, detalhe=detalhe)
        return redirect('/')

    demanda = conn.execute("SELECT * FROM demandas WHERE id=?", (id,)).fetchone()
    conn.close()

    if not demanda:
        return redirect('/')

    return render_template('editar.html', demanda=demanda)


@app.route('/deletar/<int:id>', methods=['POST'])
@login_required
def deletar(id):
    conn = get_db()
    demanda = conn.execute("SELECT titulo FROM demandas WHERE id=?", (id,)).fetchone()
    titulo  = demanda['titulo'] if demanda else f'ID {id}'

    conn.execute("DELETE FROM demandas WHERE id=?", (id,))
    conn.commit()
    conn.close()

    registrar_log('DELETAR_DEMANDA', entidade='demanda', entidade_id=id,
                  detalhe=f'Demanda deletada: "{titulo}"')
    return redirect('/')


@app.route('/buscar')
@login_required
def buscar():
    termo = request.args.get('q', '').strip()

    if not termo:
        return redirect('/')

    registrar_log('BUSCA', detalhe=f'Termo buscado: "{termo}"')

    conn = get_db()
    demandas = conn.execute("""
        SELECT * FROM demandas
        WHERE titulo LIKE ? OR solicitante LIKE ?
    """, (f'%{termo}%', f'%{termo}%')).fetchall()
    conn.close()

    return render_template('index.html', demandas=demandas)


@app.route('/detalhes/<int:id>')
@login_required
def detalhes(id):
    conn    = get_db()
    demanda = conn.execute("SELECT * FROM demandas WHERE id=?", (id,)).fetchone()

    if not demanda:
        conn.close()
        return redirect('/')

    comentarios = conn.execute(
        "SELECT * FROM comentarios WHERE demanda_id=?", (id,)
    ).fetchall()
    conn.close()

    registrar_log('VER_DEMANDA', entidade='demanda', entidade_id=id,
                  detalhe=f'Visualizou: "{demanda["titulo"]}"')

    dt = parse_data(demanda['data_criacao'])
    data_formatada = dt.strftime("%d/%m/%Y %H:%M") if dt else demanda['data_criacao']

    return render_template(
        'detalhes.html',
        demanda=demanda,
        comentarios=comentarios,
        data_formatada=data_formatada
    )


@app.route('/adicionar_comentario/<int:id>', methods=['POST'])
@login_required
def comentar(id):
    conn = get_db()
    cursor = conn.execute("""
        INSERT INTO comentarios (demanda_id, comentario, autor, data)
        VALUES (?, ?, ?, ?)
    """, (
        id,
        request.form['comentario'],
        session['usuario_nome'],
        datetime.now()
    ))
    conn.commit()
    novo_id = cursor.lastrowid
    conn.close()

    registrar_log('CRIAR_COMENTARIO', entidade='comentario', entidade_id=novo_id,
                  detalhe=f'Comentário na demanda #{id}')
    return redirect(f'/detalhes/{id}')


# ---------------------------------------------------------------------------
# ROTA WEB — DASHBOARD
# ---------------------------------------------------------------------------

@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db()

    total = conn.execute('SELECT COUNT(*) as total FROM demandas').fetchone()['total']

    por_prioridade = conn.execute(
        'SELECT prioridade, COUNT(*) as qtd FROM demandas GROUP BY prioridade'
    ).fetchall()

    try:
        por_status = conn.execute(
            'SELECT status, COUNT(*) as qtd FROM demandas GROUP BY status'
        ).fetchall()
    except Exception:
        por_status = []

    recentes = conn.execute(
        'SELECT * FROM demandas ORDER BY data_criacao DESC LIMIT 5'
    ).fetchall()

    por_solicitante = conn.execute(
        'SELECT solicitante, COUNT(*) as qtd FROM demandas GROUP BY solicitante ORDER BY qtd DESC LIMIT 5'
    ).fetchall()

    por_mes = conn.execute("""
        SELECT strftime('%Y-%m', data_criacao) as mes, COUNT(*) as qtd
        FROM demandas GROUP BY mes ORDER BY mes DESC LIMIT 6
    """).fetchall()

    conn.close()

    return render_template('dashboard.html',
        total=total,
        por_prioridade=por_prioridade,
        por_status=por_status,
        recentes=recentes,
        por_solicitante=por_solicitante,
        por_mes=list(reversed(por_mes))
    )


# ---------------------------------------------------------------------------
# ROTA WEB — AUDITORIA (visualização de logs)
# ---------------------------------------------------------------------------

@app.route('/auditoria')
@login_required
def auditoria():
    acao    = request.args.get('acao', '')
    usuario = request.args.get('usuario', '')
    origem  = request.args.get('origem', '')
    limit   = int(request.args.get('limit', 100))

    conn   = get_db()
    query  = "SELECT * FROM logs WHERE 1=1"
    params = []

    if acao:
        query += " AND acao LIKE ?"
        params.append(f'%{acao}%')

    if usuario:
        query += " AND usuario_nome LIKE ?"
        params.append(f'%{usuario}%')

    if origem:
        query += " AND origem=?"
        params.append(origem)

    query += " ORDER BY criado_em DESC LIMIT ?"
    params.append(limit)

    logs = conn.execute(query, params).fetchall()

    # Contadores para o resumo
    total_logs   = conn.execute("SELECT COUNT(*) as n FROM logs").fetchone()['n']
    acoes_unicas = conn.execute("SELECT DISTINCT acao FROM logs ORDER BY acao").fetchall()
    conn.close()

    registrar_log('VER_AUDITORIA', detalhe=f'Consultou logs (filtros: acao={acao}, usuario={usuario})')

    return render_template('auditoria.html',
        logs=logs,
        total_logs=total_logs,
        acoes_unicas=acoes_unicas,
        filtro_acao=acao,
        filtro_usuario=usuario,
        filtro_origem=origem
    )


# ---------------------------------------------------------------------------
# ROTA WEB — TOKEN API
# ---------------------------------------------------------------------------

@app.route('/meu_token', methods=['GET', 'POST'])
@login_required
def meu_token():
    conn = get_db()

    if request.method == 'POST':
        acao = request.form.get('acao')

        if acao == 'gerar':
            novo_token = secrets.token_hex(32)
            conn.execute(
                "UPDATE api_tokens SET ativo=0 WHERE usuario_id=?",
                (session['usuario_id'],)
            )
            conn.execute(
                "INSERT INTO api_tokens (usuario_id, token, criado_em, ativo) VALUES (?, ?, ?, 1)",
                (session['usuario_id'], novo_token, datetime.now())
            )
            conn.commit()
            registrar_log('GERAR_TOKEN_API', entidade='token',
                          detalhe=f'Token API gerado para usuário {session["usuario_nome"]}')
            flash(f"Token gerado: {novo_token}")

        elif acao == 'revogar':
            conn.execute(
                "UPDATE api_tokens SET ativo=0 WHERE usuario_id=?",
                (session['usuario_id'],)
            )
            conn.commit()
            registrar_log('REVOGAR_TOKEN_API', entidade='token',
                          detalhe=f'Token API revogado para usuário {session["usuario_nome"]}')
            flash("Token revogado com sucesso.")

        conn.close()
        return redirect('/meu_token')

    token = conn.execute(
        "SELECT * FROM api_tokens WHERE usuario_id=? AND ativo=1",
        (session['usuario_id'],)
    ).fetchone()
    conn.close()

    return render_template('meu_token.html', token=token)


# ===========================================================================
# API REST — /api/v1/
# ===========================================================================

@app.route('/api/v1/demandas', methods=['GET'])
@api_key_required
def api_listar_demandas():
    prioridade  = request.args.get('prioridade')
    solicitante = request.args.get('solicitante')
    limit       = min(int(request.args.get('limit', 50)), 200)

    conn   = get_db()
    query  = "SELECT * FROM demandas WHERE 1=1"
    params = []

    if prioridade:
        query += " AND prioridade=?"
        params.append(prioridade)

    if solicitante:
        query += " AND solicitante LIKE ?"
        params.append(f'%{solicitante}%')

    query += " ORDER BY datetime(data_criacao) DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()

    registrar_log('API_LISTAR_DEMANDAS',
                  detalhe=f'Filtros: prioridade={prioridade} solicitante={solicitante} limit={limit}',
                  origem='api')
    return jsonify({'total': len(rows), 'demandas': [dict(r) for r in rows]}), 200


@app.route('/api/v1/demandas/<int:id>', methods=['GET'])
@api_key_required
def api_obter_demanda(id):
    conn    = get_db()
    demanda = conn.execute("SELECT * FROM demandas WHERE id=?", (id,)).fetchone()

    if not demanda:
        conn.close()
        registrar_log('API_DEMANDA_NAO_ENCONTRADA', entidade='demanda', entidade_id=id, origem='api')
        return jsonify({'erro': f'Demanda {id} não encontrada.'}), 404

    comentarios = conn.execute(
        "SELECT * FROM comentarios WHERE demanda_id=?", (id,)
    ).fetchall()
    conn.close()

    registrar_log('API_VER_DEMANDA', entidade='demanda', entidade_id=id, origem='api')
    resultado = dict(demanda)
    resultado['comentarios'] = [dict(c) for c in comentarios]
    return jsonify(resultado), 200


@app.route('/api/v1/demandas', methods=['POST'])
@api_key_required
def api_criar_demanda():
    dados = request.get_json()

    if not dados:
        return jsonify({'erro': 'Body JSON inválido ou ausente.'}), 400

    campos_obrigatorios = ['titulo', 'descricao', 'solicitante', 'prioridade']
    faltando = [c for c in campos_obrigatorios if not dados.get(c)]
    if faltando:
        return jsonify({'erro': f'Campos obrigatórios ausentes: {", ".join(faltando)}'}), 400

    prioridades_validas = {'Alta', 'Media', 'Baixa'}
    if dados['prioridade'] not in prioridades_validas:
        return jsonify({'erro': f'Prioridade inválida. Use: {", ".join(prioridades_validas)}'}), 400

    conn = get_db()
    cursor = conn.execute("""
        INSERT INTO demandas (titulo, descricao, solicitante, data_criacao, prioridade)
        VALUES (?, ?, ?, ?, ?)
    """, (
        dados['titulo'], dados['descricao'], dados['solicitante'],
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"), dados['prioridade']
    ))
    conn.commit()
    novo_id = cursor.lastrowid
    demanda = conn.execute("SELECT * FROM demandas WHERE id=?", (novo_id,)).fetchone()
    conn.close()

    registrar_log('API_CRIAR_DEMANDA', entidade='demanda', entidade_id=novo_id,
                  detalhe=f'Título: {dados["titulo"]} | Prioridade: {dados["prioridade"]}',
                  origem='api')
    return jsonify({'mensagem': 'Demanda criada com sucesso.', 'demanda': dict(demanda)}), 201


@app.route('/api/v1/demandas/<int:id>', methods=['PUT'])
@api_key_required
def api_atualizar_demanda(id):
    conn    = get_db()
    demanda = conn.execute("SELECT * FROM demandas WHERE id=?", (id,)).fetchone()

    if not demanda:
        conn.close()
        return jsonify({'erro': f'Demanda {id} não encontrada.'}), 404

    dados      = request.get_json() or {}
    titulo     = dados.get('titulo',     demanda['titulo'])
    descricao  = dados.get('descricao',  demanda['descricao'])
    prioridade = dados.get('prioridade', demanda['prioridade'])

    prioridades_validas = {'Alta', 'Media', 'Baixa'}
    if prioridade not in prioridades_validas:
        conn.close()
        return jsonify({'erro': f'Prioridade inválida. Use: {", ".join(prioridades_validas)}'}), 400

    conn.execute("""
        UPDATE demandas SET titulo=?, descricao=?, prioridade=? WHERE id=?
    """, (titulo, descricao, prioridade, id))
    conn.commit()
    atualizada = conn.execute("SELECT * FROM demandas WHERE id=?", (id,)).fetchone()
    conn.close()

    registrar_log('API_ATUALIZAR_DEMANDA', entidade='demanda', entidade_id=id,
                  detalhe=f'Campos atualizados: {list(dados.keys())}', origem='api')
    return jsonify({'mensagem': 'Demanda atualizada.', 'demanda': dict(atualizada)}), 200


@app.route('/api/v1/demandas/<int:id>', methods=['DELETE'])
@api_key_required
def api_deletar_demanda(id):
    conn    = get_db()
    demanda = conn.execute("SELECT * FROM demandas WHERE id=?", (id,)).fetchone()

    if not demanda:
        conn.close()
        return jsonify({'erro': f'Demanda {id} não encontrada.'}), 404

    titulo = demanda['titulo']
    conn.execute("DELETE FROM comentarios WHERE demanda_id=?", (id,))
    conn.execute("DELETE FROM demandas WHERE id=?", (id,))
    conn.commit()
    conn.close()

    registrar_log('API_DELETAR_DEMANDA', entidade='demanda', entidade_id=id,
                  detalhe=f'Demanda deletada via API: "{titulo}"', origem='api')
    return jsonify({'mensagem': f'Demanda {id} deletada com sucesso.'}), 200


@app.route('/api/v1/demandas/<int:id>/comentarios', methods=['GET'])
@api_key_required
def api_listar_comentarios(id):
    conn    = get_db()
    demanda = conn.execute("SELECT id FROM demandas WHERE id=?", (id,)).fetchone()

    if not demanda:
        conn.close()
        return jsonify({'erro': f'Demanda {id} não encontrada.'}), 404

    comentarios = conn.execute(
        "SELECT * FROM comentarios WHERE demanda_id=? ORDER BY data ASC", (id,)
    ).fetchall()
    conn.close()

    registrar_log('API_LISTAR_COMENTARIOS', entidade='demanda', entidade_id=id, origem='api')
    return jsonify({'demanda_id': id, 'comentarios': [dict(c) for c in comentarios]}), 200


@app.route('/api/v1/demandas/<int:id>/comentarios', methods=['POST'])
@api_key_required
def api_criar_comentario(id):
    conn    = get_db()
    demanda = conn.execute("SELECT id FROM demandas WHERE id=?", (id,)).fetchone()

    if not demanda:
        conn.close()
        return jsonify({'erro': f'Demanda {id} não encontrada.'}), 404

    dados = request.get_json() or {}
    if not dados.get('comentario') or not dados.get('autor'):
        conn.close()
        return jsonify({'erro': 'Campos obrigatórios: comentario, autor'}), 400

    cursor = conn.execute("""
        INSERT INTO comentarios (demanda_id, comentario, autor, data)
        VALUES (?, ?, ?, ?)
    """, (id, dados['comentario'], dados['autor'], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    novo = conn.execute("SELECT * FROM comentarios WHERE id=?", (cursor.lastrowid,)).fetchone()
    conn.close()

    registrar_log('API_CRIAR_COMENTARIO', entidade='comentario', entidade_id=cursor.lastrowid,
                  detalhe=f'Comentário na demanda #{id} por {dados["autor"]}', origem='api')
    return jsonify({'mensagem': 'Comentário adicionado.', 'comentario': dict(novo)}), 201


@app.route('/api/v1/stats', methods=['GET'])
@api_key_required
def api_stats():
    conn = get_db()

    total = conn.execute('SELECT COUNT(*) as n FROM demandas').fetchone()['n']

    por_prioridade = {
        r['prioridade']: r['qtd']
        for r in conn.execute(
            'SELECT prioridade, COUNT(*) as qtd FROM demandas GROUP BY prioridade'
        ).fetchall()
    }

    por_mes = [dict(r) for r in conn.execute("""
        SELECT strftime('%Y-%m', data_criacao) as mes, COUNT(*) as qtd
        FROM demandas GROUP BY mes ORDER BY mes DESC LIMIT 6
    """).fetchall()]

    top_solicitantes = [dict(r) for r in conn.execute("""
        SELECT solicitante, COUNT(*) as qtd FROM demandas
        GROUP BY solicitante ORDER BY qtd DESC LIMIT 5
    """).fetchall()]

    conn.close()

    registrar_log('API_STATS', detalhe='Consulta de indicadores gerenciais', origem='api')
    return jsonify({
        'total_demandas':   total,
        'por_prioridade':   por_prioridade,
        'por_mes':          por_mes,
        'top_solicitantes': top_solicitantes
    }), 200


# ── GET /api/v1/logs ─────────────────────────────────────────────────────────
@app.route('/api/v1/logs', methods=['GET'])
@api_key_required
def api_logs():
    """Retorna os logs de auditoria. Params: acao, usuario, origem, limit (máx 500)."""
    acao    = request.args.get('acao', '')
    usuario = request.args.get('usuario', '')
    origem  = request.args.get('origem', '')
    limit   = min(int(request.args.get('limit', 100)), 500)

    conn   = get_db()
    query  = "SELECT * FROM logs WHERE 1=1"
    params = []

    if acao:
        query += " AND acao LIKE ?"
        params.append(f'%{acao}%')
    if usuario:
        query += " AND usuario_nome LIKE ?"
        params.append(f'%{usuario}%')
    if origem:
        query += " AND origem=?"
        params.append(origem)

    query += " ORDER BY criado_em DESC LIMIT ?"
    params.append(limit)

    logs = conn.execute(query, params).fetchall()
    conn.close()

    registrar_log('API_CONSULTAR_LOGS', detalhe=f'Consulta de logs via API', origem='api')
    return jsonify({'total': len(logs), 'logs': [dict(l) for l in logs]}), 200


# ---------------------------------------------------------------------------

if __name__ == '__main__':
    app.run(debug=True)
