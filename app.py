from flask import Flask, render_template, request, redirect, flash, session, jsonify
import sqlite3
from datetime import datetime
from functools import wraps
import secrets
import hashlib

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)  # FIX: secret_key segura e aleatória


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def get_db():
    conn = sqlite3.connect('demandas.db')
    conn.row_factory = sqlite3.Row
    return conn


def hash_senha(senha):
    """Retorna SHA-256 da senha para armazenamento seguro."""
    return hashlib.sha256(senha.encode()).hexdigest()


def parse_data(data_str):
    """FIX: aceita datas com ou sem microssegundos."""
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(data_str, fmt)
        except ValueError:
            continue
    return None


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
    """Decorator de autenticação para rotas da API REST."""
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
        # Tenta login com senha hasheada primeiro; fallback para texto puro
        # (compatibilidade com usuários criados antes do fix)
        user = conn.execute(
            "SELECT * FROM usuarios WHERE nome=? AND (senha=? OR senha=?)",
            (nome, hash_senha(senha), senha)
        ).fetchone()
        conn.close()

        if user:
            session['usuario_id']   = user['id']
            session['usuario_nome'] = user['nome']
            return redirect('/')
        else:
            flash("Login inválido")

    return render_template('login.html')


@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        nome  = request.form['nome']
        senha = request.form['senha']

        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO usuarios (nome, senha) VALUES (?, ?)",
                (nome, hash_senha(senha))   # FIX: armazena hash
            )
            conn.commit()
        except sqlite3.IntegrityError:       # FIX: captura exceção específica
            flash("Usuário já existe")
            return redirect('/cadastro')
        finally:
            conn.close()

        return redirect('/login')

    return render_template('cadastro.html')


@app.route('/logout')
def logout():
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
        try:                                  # FIX: garante fechamento em erro
            conn.execute("""
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
        return redirect('/')

    demanda = conn.execute("SELECT * FROM demandas WHERE id=?", (id,)).fetchone()
    conn.close()

    if not demanda:
        return redirect('/')

    return render_template('editar.html', demanda=demanda)


@app.route('/deletar/<int:id>', methods=['POST'])   # FIX: POST em vez de GET
@login_required
def deletar(id):
    conn = get_db()
    conn.execute("DELETE FROM demandas WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect('/')


@app.route('/buscar')
@login_required
def buscar():
    termo = request.args.get('q', '').strip()

    if not termo:                             # FIX: termo vazio redireciona
        return redirect('/')

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
    conn     = get_db()
    demanda  = conn.execute("SELECT * FROM demandas WHERE id=?", (id,)).fetchone()

    if not demanda:
        conn.close()
        return redirect('/')

    comentarios = conn.execute(
        "SELECT * FROM comentarios WHERE demanda_id=?", (id,)
    ).fetchall()
    conn.close()

    # FIX: parse_data aceita datas com e sem microssegundos
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
    conn.execute("""
        INSERT INTO comentarios (demanda_id, comentario, autor, data)
        VALUES (?, ?, ?, ?)
    """, (
        id,
        request.form['comentario'],
        session['usuario_nome'],
        datetime.now()
    ))
    conn.commit()
    conn.close()
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
        FROM demandas
        GROUP BY mes
        ORDER BY mes DESC
        LIMIT 6
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
# ROTA WEB — GERAÇÃO DE TOKEN API (painel do usuário logado)
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
            flash(f"Token gerado: {novo_token}")

        elif acao == 'revogar':
            conn.execute(
                "UPDATE api_tokens SET ativo=0 WHERE usuario_id=?",
                (session['usuario_id'],)
            )
            conn.commit()
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
# Autenticação: header  X-API-Key: <token>
# ===========================================================================

# ── GET /api/v1/demandas ────────────────────────────────────────────────────
@app.route('/api/v1/demandas', methods=['GET'])
@api_key_required
def api_listar_demandas():
    """
    Lista todas as demandas.
    Query params opcionais: prioridade, solicitante, limit (padrão 50)
    """
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

    return jsonify({
        'total': len(rows),
        'demandas': [dict(r) for r in rows]
    }), 200


# ── GET /api/v1/demandas/<id> ───────────────────────────────────────────────
@app.route('/api/v1/demandas/<int:id>', methods=['GET'])
@api_key_required
def api_obter_demanda(id):
    """Retorna uma demanda pelo ID, incluindo seus comentários."""
    conn    = get_db()
    demanda = conn.execute("SELECT * FROM demandas WHERE id=?", (id,)).fetchone()

    if not demanda:
        conn.close()
        return jsonify({'erro': f'Demanda {id} não encontrada.'}), 404

    comentarios = conn.execute(
        "SELECT * FROM comentarios WHERE demanda_id=?", (id,)
    ).fetchall()
    conn.close()

    resultado = dict(demanda)
    resultado['comentarios'] = [dict(c) for c in comentarios]
    return jsonify(resultado), 200


# ── POST /api/v1/demandas ───────────────────────────────────────────────────
@app.route('/api/v1/demandas', methods=['POST'])
@api_key_required
def api_criar_demanda():
    """
    Cria uma nova demanda.
    Body JSON: { titulo, descricao, solicitante, prioridade }
    """
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
        dados['titulo'],
        dados['descricao'],
        dados['solicitante'],
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        dados['prioridade']
    ))
    conn.commit()
    novo_id = cursor.lastrowid

    demanda = conn.execute("SELECT * FROM demandas WHERE id=?", (novo_id,)).fetchone()
    conn.close()

    return jsonify({'mensagem': 'Demanda criada com sucesso.', 'demanda': dict(demanda)}), 201


# ── PUT /api/v1/demandas/<id> ───────────────────────────────────────────────
@app.route('/api/v1/demandas/<int:id>', methods=['PUT'])
@api_key_required
def api_atualizar_demanda(id):
    """
    Atualiza título, descrição e/ou prioridade de uma demanda.
    Body JSON: { titulo?, descricao?, prioridade? }
    """
    conn    = get_db()
    demanda = conn.execute("SELECT * FROM demandas WHERE id=?", (id,)).fetchone()

    if not demanda:
        conn.close()
        return jsonify({'erro': f'Demanda {id} não encontrada.'}), 404

    dados = request.get_json() or {}

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

    return jsonify({'mensagem': 'Demanda atualizada.', 'demanda': dict(atualizada)}), 200


# ── DELETE /api/v1/demandas/<id> ────────────────────────────────────────────
@app.route('/api/v1/demandas/<int:id>', methods=['DELETE'])
@api_key_required
def api_deletar_demanda(id):
    """Deleta uma demanda e seus comentários associados."""
    conn    = get_db()
    demanda = conn.execute("SELECT * FROM demandas WHERE id=?", (id,)).fetchone()

    if not demanda:
        conn.close()
        return jsonify({'erro': f'Demanda {id} não encontrada.'}), 404

    conn.execute("DELETE FROM comentarios WHERE demanda_id=?", (id,))
    conn.execute("DELETE FROM demandas WHERE id=?", (id,))
    conn.commit()
    conn.close()

    return jsonify({'mensagem': f'Demanda {id} deletada com sucesso.'}), 200


# ── GET /api/v1/demandas/<id>/comentarios ───────────────────────────────────
@app.route('/api/v1/demandas/<int:id>/comentarios', methods=['GET'])
@api_key_required
def api_listar_comentarios(id):
    """Lista todos os comentários de uma demanda."""
    conn    = get_db()
    demanda = conn.execute("SELECT id FROM demandas WHERE id=?", (id,)).fetchone()

    if not demanda:
        conn.close()
        return jsonify({'erro': f'Demanda {id} não encontrada.'}), 404

    comentarios = conn.execute(
        "SELECT * FROM comentarios WHERE demanda_id=? ORDER BY data ASC", (id,)
    ).fetchall()
    conn.close()

    return jsonify({'demanda_id': id, 'comentarios': [dict(c) for c in comentarios]}), 200


# ── POST /api/v1/demandas/<id>/comentarios ──────────────────────────────────
@app.route('/api/v1/demandas/<int:id>/comentarios', methods=['POST'])
@api_key_required
def api_criar_comentario(id):
    """
    Adiciona um comentário a uma demanda.
    Body JSON: { comentario, autor }
    """
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

    return jsonify({'mensagem': 'Comentário adicionado.', 'comentario': dict(novo)}), 201


# ── GET /api/v1/stats ───────────────────────────────────────────────────────
@app.route('/api/v1/stats', methods=['GET'])
@api_key_required
def api_stats():
    """Retorna os indicadores gerenciais do SGDI."""
    conn = get_db()

    total = conn.execute('SELECT COUNT(*) as n FROM demandas').fetchone()['n']

    por_prioridade = {
        r['prioridade']: r['qtd']
        for r in conn.execute(
            'SELECT prioridade, COUNT(*) as qtd FROM demandas GROUP BY prioridade'
        ).fetchall()
    }

    por_mes = [
        dict(r) for r in conn.execute("""
            SELECT strftime('%Y-%m', data_criacao) as mes, COUNT(*) as qtd
            FROM demandas GROUP BY mes ORDER BY mes DESC LIMIT 6
        """).fetchall()
    ]

    top_solicitantes = [
        dict(r) for r in conn.execute("""
            SELECT solicitante, COUNT(*) as qtd FROM demandas
            GROUP BY solicitante ORDER BY qtd DESC LIMIT 5
        """).fetchall()
    ]

    conn.close()

    return jsonify({
        'total_demandas':   total,
        'por_prioridade':   por_prioridade,
        'por_mes':          por_mes,
        'top_solicitantes': top_solicitantes
    }), 200


# ---------------------------------------------------------------------------

if __name__ == '__main__':
    app.run(debug=True)
