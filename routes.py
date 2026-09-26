import secrets
from datetime import datetime, timedelta

from flask import jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from database import get_db_connection

SESSION_TTL = timedelta(days=1)
FIELDS = 'id, name, email, address, phone, is_admin, created_at'


def row_to_user(row):
    return {
        'id': row[0],
        'name': row[1],
        'email': row[2],
        'address': row[3],
        'phone': row[4],
        'is_admin': bool(row[5]),
        'created_at': row[6].isoformat() if isinstance(row[6], datetime) else row[6],
    }


def current_user():
    """Authenticated user, forwarded by the API Gateway in internal headers."""
    user_id = request.headers.get('X-User-Id')
    return (int(user_id) if user_id else None), request.headers.get('X-User-Admin') == '1'


def can_access(user_id):
    uid, admin = current_user()
    return admin or uid == user_id


def bearer_token():
    auth = request.headers.get('Authorization', '')
    return auth[7:] if auth.startswith('Bearer ') else None


def find_user(cur, user_id):
    cur.execute(f'SELECT {FIELDS} FROM users WHERE id = %s', (user_id,))
    row = cur.fetchone()
    return row_to_user(row) if row else None


def register_routes(app):
    @app.route('/users', methods=['GET'])
    def list_users():
        if not current_user()[1]:
            return jsonify({'error': 'Apenas administradores'}), 403
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(f'SELECT {FIELDS} FROM users ORDER BY id')
        users = [row_to_user(r) for r in cur.fetchall()]
        cur.close()
        conn.close()
        return jsonify({'users': users})

    @app.route('/users', methods=['POST'])
    def create_user():
        data = request.get_json(silent=True) or {}
        name = (data.get('name') or '').strip()
        email = (data.get('email') or '').strip().lower()
        password = data.get('password') or ''

        if not name or not email or not password:
            return jsonify({'error': 'Nome, e-mail e senha são obrigatórios'}), 400
        if len(password) < 6:
            return jsonify({'error': 'A senha deve ter pelo menos 6 caracteres'}), 400

        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute('SELECT id FROM users WHERE email = %s', (email,))
            if cur.fetchone():
                return jsonify({'error': 'E-mail já cadastrado'}), 409
            cur.execute(
                'INSERT INTO users (name, email, password_hash, address, phone) VALUES (%s, %s, %s, %s, %s)',
                (name, email, generate_password_hash(password), data.get('address', ''), data.get('phone', '')),
            )
            conn.commit()
            return jsonify(find_user(cur, cur.lastrowid)), 201
        finally:
            cur.close()
            conn.close()

    @app.route('/users/me', methods=['GET'])
    def get_me():
        user_id, _ = current_user()
        if user_id is None:
            return jsonify({'error': 'Não autenticado'}), 401
        return get_user(user_id)

    @app.route('/users/me', methods=['PUT'])
    def update_me():
        user_id, _ = current_user()
        if user_id is None:
            return jsonify({'error': 'Não autenticado'}), 401
        return update_user(user_id)

    @app.route('/users/me/password', methods=['PATCH'])
    def change_my_password():
        user_id, _ = current_user()
        if user_id is None:
            return jsonify({'error': 'Não autenticado'}), 401
        data = request.get_json(silent=True) or {}
        current_password = data.get('current_password')
        new_password = data.get('new_password') or ''
        if not current_password or not new_password:
            return jsonify({'error': 'Senha atual e nova senha são obrigatórias'}), 400
        if len(new_password) < 6:
            return jsonify({'error': 'A nova senha deve ter pelo menos 6 caracteres'}), 400

        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute('SELECT password_hash FROM users WHERE id = %s', (user_id,))
            row = cur.fetchone()
            if row is None or not check_password_hash(row[0], current_password):
                return jsonify({'error': 'Senha atual incorreta'}), 401
            cur.execute('UPDATE users SET password_hash = %s WHERE id = %s', (generate_password_hash(new_password), user_id))
            # End every other session
            cur.execute('DELETE FROM sessions WHERE user_id = %s AND token != %s', (user_id, bearer_token() or ''))
            conn.commit()
            return jsonify({'message': 'Senha atualizada'})
        finally:
            cur.close()
            conn.close()

    @app.route('/users/<int:user_id>', methods=['GET'])
    def get_user(user_id):
        if not can_access(user_id):
            return jsonify({'error': 'Acesso negado'}), 403
        conn = get_db_connection()
        cur = conn.cursor()
        user = find_user(cur, user_id)
        cur.close()
        conn.close()
        if user is None:
            return jsonify({'error': 'Usuário não encontrado'}), 404
        return jsonify(user)

    @app.route('/users/<int:user_id>', methods=['PUT'])
    def update_user(user_id):
        if not can_access(user_id):
            return jsonify({'error': 'Acesso negado'}), 403
        data = request.get_json(silent=True) or {}

        conn = get_db_connection()
        cur = conn.cursor()
        try:
            current = find_user(cur, user_id)
            if current is None:
                return jsonify({'error': 'Usuário não encontrado'}), 404

            name = (data.get('name') or current['name']).strip()
            email = (data.get('email') or current['email']).strip().lower()
            address = data.get('address', current['address'])
            phone = data.get('phone', current['phone'])

            cur.execute('SELECT id FROM users WHERE email = %s AND id != %s', (email, user_id))
            if cur.fetchone():
                return jsonify({'error': 'E-mail já está em uso por outra conta'}), 409

            cur.execute(
                'UPDATE users SET name = %s, email = %s, address = %s, phone = %s WHERE id = %s',
                (name, email, address, phone, user_id),
            )
            conn.commit()
            return jsonify(find_user(cur, user_id))
        finally:
            cur.close()
            conn.close()

    @app.route('/users/<int:user_id>', methods=['DELETE'])
    def delete_user(user_id):
        if not can_access(user_id):
            return jsonify({'error': 'Acesso negado'}), 403
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute('DELETE FROM users WHERE id = %s', (user_id,))  # sessions go by CASCADE
            conn.commit()
            if cur.rowcount == 0:
                return jsonify({'error': 'Usuário não encontrado'}), 404
            return jsonify({'message': f'Usuário {user_id} removido'})
        finally:
            cur.close()
            conn.close()

    @app.route('/auth/login', methods=['POST'])
    def login():
        data = request.get_json(silent=True) or {}
        email = (data.get('email') or '').strip().lower()
        password = data.get('password') or ''
        if not email or not password:
            return jsonify({'error': 'E-mail e senha são obrigatórios'}), 400

        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute(f'SELECT {FIELDS}, password_hash FROM users WHERE email = %s', (email,))
            row = cur.fetchone()
            if row is None or not check_password_hash(row[7], password):
                return jsonify({'error': 'E-mail ou senha incorretos'}), 401

            token = secrets.token_urlsafe(32)
            cur.execute(
                'INSERT INTO sessions (token, user_id, expires_at) VALUES (%s, %s, %s)',
                (token, row[0], datetime.now() + SESSION_TTL),
            )
            cur.execute('DELETE FROM sessions WHERE expires_at < NOW()')
            conn.commit()
            return jsonify({'token': token, 'user': row_to_user(row)})
        finally:
            cur.close()
            conn.close()

    @app.route('/auth/verify', methods=['POST'])
    def verify_token():
        token = (request.get_json(silent=True) or {}).get('token') or bearer_token()
        if not token:
            return jsonify({'valid': False, 'error': 'Token não informado'}), 400

        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                '''SELECT u.id, u.name, u.email, u.is_admin, s.expires_at
                   FROM sessions s JOIN users u ON u.id = s.user_id
                   WHERE s.token = %s''',
                (token,),
            )
            row = cur.fetchone()
            if row is None:
                return jsonify({'valid': False, 'error': 'Token inválido'}), 401
            if datetime.now() > row[4]:
                cur.execute('DELETE FROM sessions WHERE token = %s', (token,))
                conn.commit()
                return jsonify({'valid': False, 'error': 'Sessão expirada'}), 401
            return jsonify({
                'valid': True,
                'user': {'id': row[0], 'name': row[1], 'email': row[2], 'is_admin': bool(row[3])},
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
            cur.execute('DELETE FROM sessions WHERE token = %s', (token,))
            conn.commit()
            cur.close()
            conn.close()
        return jsonify({'message': 'Sessão encerrada'})

    @app.route('/health', methods=['GET'])
    def health():
        try:
            conn = get_db_connection()
            conn.close()
            return jsonify({'status': 'ok', 'database': 'connected'}), 200
        except Exception:
            return jsonify({'status': 'error', 'database': 'disconnected'}), 500
