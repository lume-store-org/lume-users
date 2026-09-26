import secrets
from datetime import datetime, timedelta

from flask import jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from database import get_db_connection

TOKEN_TTL = timedelta(days=1)
CAMPOS = 'id, nome, email, endereco, telefone, is_admin, data_cadastro'


def row_to_usuario(row):
    return {
        'id': row[0],
        'nome': row[1],
        'email': row[2],
        'endereco': row[3],
        'telefone': row[4],
        'is_admin': bool(row[5]),
        'data_cadastro': row[6].isoformat() if isinstance(row[6], datetime) else row[6],
    }


def usuario_atual():
    """Usuário autenticado, repassado pelo API Gateway nos headers internos."""
    uid = request.headers.get('X-Usuario-Id')
    return (int(uid) if uid else None), request.headers.get('X-Usuario-Admin') == '1'


def pode_acessar(id):
    uid, admin = usuario_atual()
    return admin or uid == id


def buscar_usuario(cur, id):
    cur.execute(f'SELECT {CAMPOS} FROM usuarios WHERE id = %s', (id,))
    row = cur.fetchone()
    return row_to_usuario(row) if row else None


def register_routes(app):
    @app.route('/usuarios', methods=['GET'])
    def listar_usuarios():
        if not usuario_atual()[1]:
            return jsonify({"erro": "Apenas administradores"}), 403
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(f'SELECT {CAMPOS} FROM usuarios ORDER BY id')
        usuarios = [row_to_usuario(r) for r in cur.fetchall()]
        cur.close()
        conn.close()
        return jsonify({"usuarios": usuarios})

    @app.route('/usuarios', methods=['POST'])
    def cadastrar_usuario():
        dados = request.get_json(silent=True) or {}
        nome = (dados.get('nome') or '').strip()
        email = (dados.get('email') or '').strip().lower()
        senha = dados.get('senha') or ''

        if not nome or not email or not senha:
            return jsonify({"erro": "Nome, email e senha são obrigatórios"}), 400
        if len(senha) < 6:
            return jsonify({"erro": "A senha deve ter pelo menos 6 caracteres"}), 400

        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute('SELECT id FROM usuarios WHERE email = %s', (email,))
            if cur.fetchone():
                return jsonify({"erro": "Email já cadastrado"}), 409
            cur.execute(
                'INSERT INTO usuarios (nome, email, senha_hash, endereco, telefone) VALUES (%s, %s, %s, %s, %s)',
                (nome, email, generate_password_hash(senha), dados.get('endereco', ''), dados.get('telefone', '')),
            )
            conn.commit()
            return jsonify(buscar_usuario(cur, cur.lastrowid)), 201
        finally:
            cur.close()
            conn.close()

    @app.route('/usuarios/me', methods=['GET'])
    def meu_perfil():
        uid, _ = usuario_atual()
        if uid is None:
            return jsonify({"erro": "Não autenticado"}), 401
        return obter_usuario(uid)

    @app.route('/usuarios/me', methods=['PUT'])
    def atualizar_meu_perfil():
        uid, _ = usuario_atual()
        if uid is None:
            return jsonify({"erro": "Não autenticado"}), 401
        return atualizar_usuario(uid)

    @app.route('/usuarios/me/senha', methods=['PATCH'])
    def atualizar_minha_senha():
        uid, _ = usuario_atual()
        if uid is None:
            return jsonify({"erro": "Não autenticado"}), 401
        dados = request.get_json(silent=True) or {}
        senha_atual = dados.get('senha_atual')
        nova_senha = dados.get('nova_senha') or ''
        if not senha_atual or not nova_senha:
            return jsonify({"erro": "Senha atual e nova senha são obrigatórias"}), 400
        if len(nova_senha) < 6:
            return jsonify({"erro": "A nova senha deve ter pelo menos 6 caracteres"}), 400

        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute('SELECT senha_hash FROM usuarios WHERE id = %s', (uid,))
            row = cur.fetchone()
            if row is None or not check_password_hash(row[0], senha_atual):
                return jsonify({"erro": "Senha atual incorreta"}), 401
            cur.execute('UPDATE usuarios SET senha_hash = %s WHERE id = %s', (generate_password_hash(nova_senha), uid))
            # Encerra as outras sessões
            cur.execute('DELETE FROM tokens WHERE usuario_id = %s AND token != %s', (uid, bearer_token() or ''))
            conn.commit()
            return jsonify({"mensagem": "Senha atualizada com sucesso"})
        finally:
            cur.close()
            conn.close()

    @app.route('/usuarios/<int:id>', methods=['GET'])
    def obter_usuario(id):
        if not pode_acessar(id):
            return jsonify({"erro": "Acesso negado"}), 403
        conn = get_db_connection()
        cur = conn.cursor()
        usuario = buscar_usuario(cur, id)
        cur.close()
        conn.close()
        if usuario is None:
            return jsonify({"erro": "Usuário não encontrado"}), 404
        return jsonify(usuario)

    @app.route('/usuarios/<int:id>', methods=['PUT'])
    def atualizar_usuario(id):
        if not pode_acessar(id):
            return jsonify({"erro": "Acesso negado"}), 403
        dados = request.get_json(silent=True) or {}

        conn = get_db_connection()
        cur = conn.cursor()
        try:
            atual = buscar_usuario(cur, id)
            if atual is None:
                return jsonify({"erro": "Usuário não encontrado"}), 404

            nome = (dados.get('nome') or atual['nome']).strip()
            email = (dados.get('email') or atual['email']).strip().lower()
            endereco = dados.get('endereco', atual['endereco'])
            telefone = dados.get('telefone', atual['telefone'])

            cur.execute('SELECT id FROM usuarios WHERE email = %s AND id != %s', (email, id))
            if cur.fetchone():
                return jsonify({"erro": "Email já está em uso por outro usuário"}), 409

            cur.execute(
                'UPDATE usuarios SET nome = %s, email = %s, endereco = %s, telefone = %s WHERE id = %s',
                (nome, email, endereco, telefone, id),
            )
            conn.commit()
            return jsonify(buscar_usuario(cur, id))
        finally:
            cur.close()
            conn.close()

    @app.route('/usuarios/<int:id>', methods=['DELETE'])
    def remover_usuario(id):
        if not pode_acessar(id):
            return jsonify({"erro": "Acesso negado"}), 403
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute('DELETE FROM usuarios WHERE id = %s', (id,))  # tokens saem por CASCADE
            conn.commit()
            if cur.rowcount == 0:
                return jsonify({"erro": "Usuário não encontrado"}), 404
            return jsonify({"mensagem": f"Usuário {id} removido com sucesso"})
        finally:
            cur.close()
            conn.close()

    @app.route('/auth/login', methods=['POST'])
    def login():
        dados = request.get_json(silent=True) or {}
        email = (dados.get('email') or '').strip().lower()
        senha = dados.get('senha') or ''
        if not email or not senha:
            return jsonify({"erro": "Email e senha são obrigatórios"}), 400

        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute(f'SELECT {CAMPOS}, senha_hash FROM usuarios WHERE email = %s', (email,))
            row = cur.fetchone()
            if row is None or not check_password_hash(row[7], senha):
                return jsonify({"erro": "Credenciais inválidas"}), 401

            token = secrets.token_urlsafe(32)
            cur.execute(
                'INSERT INTO tokens (token, usuario_id, expiracao) VALUES (%s, %s, %s)',
                (token, row[0], datetime.now() + TOKEN_TTL),
            )
            cur.execute('DELETE FROM tokens WHERE expiracao < NOW()')
            conn.commit()
            return jsonify({"token": token, "usuario": row_to_usuario(row)})
        finally:
            cur.close()
            conn.close()

    @app.route('/auth/verificar', methods=['POST'])
    def verificar_token():
        token = (request.get_json(silent=True) or {}).get('token') or bearer_token()
        if not token:
            return jsonify({"valido": False, "erro": "Token não fornecido"}), 400

        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                '''SELECT u.id, u.nome, u.email, u.is_admin, t.expiracao
                   FROM tokens t JOIN usuarios u ON u.id = t.usuario_id
                   WHERE t.token = %s''',
                (token,),
            )
            row = cur.fetchone()
            if row is None:
                return jsonify({"valido": False, "erro": "Token inválido"}), 401
            if datetime.now() > row[4]:
                cur.execute('DELETE FROM tokens WHERE token = %s', (token,))
                conn.commit()
                return jsonify({"valido": False, "erro": "Token expirado"}), 401
            return jsonify({
                "valido": True,
                "usuario": {"id": row[0], "nome": row[1], "email": row[2], "is_admin": bool(row[3])},
            })
        finally:
            cur.close()
            conn.close()

    @app.route('/auth/logout', methods=['POST'])
    def logout():
        token = (request.get_json(silent=True) or {}).get('token') or bearer_token()
        if token:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute('DELETE FROM tokens WHERE token = %s', (token,))
            conn.commit()
            cur.close()
            conn.close()
        return jsonify({"mensagem": "Logout realizado com sucesso"})

    @app.route('/health', methods=['GET'])
    def health():
        try:
            conn = get_db_connection()
            conn.close()
            return jsonify({"status": "ok", "database": "connected"}), 200
        except Exception:
            return jsonify({"status": "erro", "database": "disconnected"}), 500


def bearer_token():
    auth = request.headers.get('Authorization', '')
    return auth[7:] if auth.startswith('Bearer ') else None
