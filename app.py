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
    def decorated_function(*args, **kwargs):
        if 'usuario_id' not in session:
            flash('Faça login primeiro.')
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        nome = request.form['nome']
        senha = request.form['senha']

        conn = get_db()
        cursor = conn.cursor()

        usuario_existente = cursor.execute(
            "SELECT * FROM usuarios WHERE nome=?",
            (nome,)
        ).fetchone()

        if usuario_existente:
            flash('Usuário já cadastrado!')
            conn.close()
            return redirect('/cadastro')

        cursor.execute(
            "INSERT INTO usuarios (nome, senha) VALUES (?, ?)",
            (nome, senha)
        )

        conn.commit()
        conn.close()

        flash('Cadastro realizado com sucesso!')
        return redirect('/login')

    return render_template('cadastro.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        nome = request.form['nome']
        senha = request.form['senha']

        conn = get_db()
        cursor = conn.cursor()

        usuario = cursor.execute(
            "SELECT * FROM usuarios WHERE nome=? AND senha=?",
            (nome, senha)
        ).fetchone()

        conn.close()

        if usuario:
            session['usuario_id'] = usuario['id']
            session['usuario_nome'] = usuario['nome']
            flash('Login realizado com sucesso!')
            return redirect('/')

        flash('Usuário ou senha inválidos!')
        return redirect('/login')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Logout realizado!')
    return redirect('/login')


@app.route('/')
@login_required
def index():
    conn = get_db()
    cursor = conn.cursor()

    prioridade = request.args.get('prioridade')
    usuario = request.args.get('usuario')

    query = "SELECT * FROM demandas WHERE 1=1"
    params = []

    if prioridade and prioridade != 'Todas':
        query += " AND prioridade=?"
        params.append(prioridade)

    if usuario and usuario.strip():
        query += " AND solicitante LIKE ?"
        params.append(f'%{usuario}%')

    query += """
        ORDER BY
            CASE prioridade
                WHEN 'Alta' THEN 1
                WHEN 'Media' THEN 2
                WHEN 'Baixa' THEN 3
            END,
            datetime(data_criacao) ASC
    """

    demandas = cursor.execute(query, params).fetchall()

    conn.close()
    return render_template('index.html', demandas=demandas)

@app.route('/nova_demanda', methods=['GET', 'POST'])
@login_required
def nova_demanda():
    conn = get_db()
    cursor = conn.cursor()

    usuarios = cursor.execute("SELECT nome FROM usuarios").fetchall()

    if request.method == 'POST':
        titulo = request.form['titulo']
        descricao = request.form['descricao']
        solicitante = request.form['solicitante']
        prioridade = request.form.get('prioridade', 'Baixa')

        cursor.execute(
            """
            INSERT INTO demandas
            (titulo, descricao, solicitante, data_criacao, prioridade)
            VALUES (?, ?, ?, ?, ?)
            """,
            (titulo, descricao, solicitante, datetime.now(), prioridade)
        )

        conn.commit()
        conn.close()

        flash('Demanda salva!')
        return redirect('/')

    conn.close()
    return render_template('nova_demanda.html', usuarios=usuarios)


@app.route('/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar(id):
    conn = get_db()
    cursor = conn.cursor()

    if request.method == 'POST':
        titulo = request.form['titulo']
        descricao = request.form['descricao']
        solicitante = request.form['solicitante']
        prioridade = request.form.get('prioridade', 'Baixa')

        cursor.execute(
            """
            UPDATE demandas
            SET titulo=?, descricao=?, solicitante=?, prioridade=?
            WHERE id=?
            """,
            (titulo, descricao, solicitante, prioridade, id)
        )

        conn.commit()
        conn.close()
        flash('Demanda atualizada!')
        return redirect('/')

    demanda = cursor.execute(
        'SELECT * FROM demandas WHERE id=?',
        (id,)
    ).fetchone()

    usuarios = cursor.execute("SELECT nome FROM usuarios").fetchall()

    conn.close()
    return render_template('editar.html', demanda=demanda, usuarios=usuarios)

@app.route('/deletar/<int:id>')
@login_required
def deletar(id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('DELETE FROM demandas WHERE id=?', (id,))

    conn.commit()
    conn.close()

    flash('Deletado!')
    return redirect('/')

@app.route('/buscar')
@login_required
def buscar():
    termo = request.args.get('q')

    conn = get_db()
    cursor = conn.cursor()

    resultados = cursor.execute(
        """
        SELECT * FROM demandas
        WHERE titulo LIKE ?
        OR solicitante LIKE ?
        """,
        (f'%{termo}%', f'%{termo}%')
    ).fetchall()

    conn.close()

    return render_template('index.html', demandas=resultados)

@app.route('/detalhes/<int:id>')
@login_required
def detalhes(id):
    conn = get_db()
    cursor = conn.cursor()

    demanda = cursor.execute(
        'SELECT * FROM demandas WHERE id=?',
        (id,)
    ).fetchone()

    comentarios = cursor.execute(
        'SELECT * FROM comentarios WHERE demanda_id=?',
        (id,)
    ).fetchall()

    conn.close()

    return render_template('detalhes.html', demanda=demanda, comentarios=comentarios)

@app.route('/adicionar_comentario/<int:demanda_id>', methods=['POST'])
@login_required
def adicionar_comentario(demanda_id):
    comentario = request.form['comentario']
    autor = session['usuario_nome']

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO comentarios
        (demanda_id, comentario, autor, data)
        VALUES (?, ?, ?, ?)
        """,
        (demanda_id, comentario, autor, datetime.now())
    )

    conn.commit()
    conn.close()

    return redirect(f'/detalhes/{demanda_id}')


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')