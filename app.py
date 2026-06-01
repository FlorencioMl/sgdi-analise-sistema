from flask import Flask, render_template, request, redirect, flash, session
import sqlite3
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = '123456'



def get_db():
    conn = sqlite3.connect('demandas.db')
    conn.row_factory = sqlite3.Row
    return conn



def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'usuario_id' not in session:
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated



@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        nome = request.form['nome']
        senha = request.form['senha']

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM usuarios WHERE nome=? AND senha=?",
            (nome, senha)
        ).fetchone()
        conn.close()

        if user:
            session['usuario_id'] = user['id']
            session['usuario_nome'] = user['nome']
            return redirect('/')
        else:
            flash("Login inválido")

    return render_template('login.html')



@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        nome = request.form['nome']
        senha = request.form['senha']

        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO usuarios (nome, senha) VALUES (?, ?)",
                (nome, senha)
            )
            conn.commit()
        except:
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



@app.route('/')
@login_required
def index():
    prioridade = request.args.get('prioridade')
    usuario = request.args.get('usuario')

    conn = get_db()
    query = "SELECT * FROM demandas WHERE 1=1"
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
            WHEN 'Alta' THEN 1
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
    conn = get_db()
    usuarios = conn.execute("SELECT nome FROM usuarios").fetchall()

    if request.method == 'POST':
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

    demanda = conn.execute(
        "SELECT * FROM demandas WHERE id=?",
        (id,)
    ).fetchone()

    if not demanda:
        conn.close()
        return redirect('/')

    conn.close()

    return render_template('editar.html', demanda=demanda)



@app.route('/deletar/<int:id>')
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
    termo = request.args.get('q')

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
    conn = get_db()

    demanda = conn.execute(
        "SELECT * FROM demandas WHERE id=?",
        (id,)
    ).fetchone()

    if not demanda:
        conn.close()
        return redirect('/')

    comentarios = conn.execute(
        "SELECT * FROM comentarios WHERE demanda_id=?",
        (id,)
    ).fetchall()

    conn.close()

    data_formatada = datetime.strptime(
        demanda['data_criacao'],
        "%Y-%m-%d %H:%M:%S.%f"
    ).strftime("%d/%m/%Y %H:%M")

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



@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db()

    # Total de demandas
    total = conn.execute('SELECT COUNT(*) as total FROM demandas').fetchone()['total']

    # Demandas por prioridade
    por_prioridade = conn.execute(
        'SELECT prioridade, COUNT(*) as qtd FROM demandas GROUP BY prioridade'
    ).fetchall()

    # Demandas por status (coluna opcional)
    try:
        por_status = conn.execute(
            'SELECT status, COUNT(*) as qtd FROM demandas GROUP BY status'
        ).fetchall()
    except Exception:
        por_status = []

    # Últimas 5 demandas
    recentes = conn.execute(
        'SELECT * FROM demandas ORDER BY data_criacao DESC LIMIT 5'
    ).fetchall()

    # Top 5 solicitantes
    por_solicitante = conn.execute(
        'SELECT solicitante, COUNT(*) as qtd FROM demandas GROUP BY solicitante ORDER BY qtd DESC LIMIT 5'
    ).fetchall()

    # Demandas por mês (últimos 6 meses)
    por_mes = conn.execute(
        """
        SELECT strftime('%Y-%m', data_criacao) as mes, COUNT(*) as qtd
        FROM demandas
        GROUP BY mes
        ORDER BY mes DESC
        LIMIT 6
        """
    ).fetchall()

    conn.close()

    return render_template('dashboard.html',
        total=total,
        por_prioridade=por_prioridade,
        por_status=por_status,
        recentes=recentes,
        por_solicitante=por_solicitante,
        por_mes=list(reversed(por_mes))
    )



if __name__ == '__main__':
    app.run(debug=True)
