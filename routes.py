from flask import jsonify, request
from database import get_db_connection
from werkzeug.security import check_password_hash, generate_password_hash
import uuid
from datetime import datetime, timedelta

def register_routes(app):
    @app.route('/usuarios', methods=['GET'])
    def listar_usuarios():
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT id, nome, email, endereco, telefone, data_cadastro FROM usuarios')
        rows = cur.fetchall()
        
        usuarios = []
        for row in rows:
            usuario = {
                'id': row[0],
                'nome': row[1],
                'email': row[2],
                'endereco': row[3],
                'telefone': row[4],
                'data_cadastro': row[5].isoformat() if isinstance(row[5], datetime) else row[5]
            }
            usuarios.append(usuario)
            
        cur.close()
        conn.close()
        
        return jsonify({"usuarios": usuarios})

    @app.route('/usuarios/<int:id>', methods=['GET'])
    def obter_usuario(id):
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT id, nome, email, endereco, telefone, data_cadastro FROM usuarios WHERE id = %s', (id,))
        row = cur.fetchone()
        
        if row is None:
            cur.close()
            conn.close()
            return jsonify({"erro": "Usuário não encontrado"}), 404
        
        usuario = {
            'id': row[0],
            'nome': row[1],
            'email': row[2],
            'endereco': row[3],
            'telefone': row[4],
            'data_cadastro': row[5].isoformat() if isinstance(row[5], datetime) else row[5]
        }
        
        cur.close()
        conn.close()
        
        return jsonify(usuario)

    @app.route('/usuarios', methods=['POST'])
    def cadastrar_usuario():
        novo_usuario = request.json
        nome = novo_usuario.get('nome')
        email = novo_usuario.get('email')
        senha = novo_usuario.get('senha')
        endereco = novo_usuario.get('endereco', '')
        telefone = novo_usuario.get('telefone', '')
        
        # Validar campos obrigatórios
        if not nome or not email or not senha:
            return jsonify({"erro": "Nome, email e senha são obrigatórios"}), 400
        
        # Hash da senha
        senha_hash = generate_password_hash(senha)
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            # Verificar se o email já existe
            cur.execute('SELECT id FROM usuarios WHERE email = %s', (email,))
            if cur.fetchone() is not None:
                cur.close()
                conn.close()
                return jsonify({"erro": "Email já cadastrado"}), 400
            
            # Inserir novo usuário
            cur.execute(
                'INSERT INTO usuarios (nome, email, senha_hash, endereco, telefone) VALUES (%s, %s, %s, %s, %s)',
                (nome, email, senha_hash, endereco, telefone)
            )
            # Obter o ID do usuário inserido usando lastrowid (método do MySQL)
            usuario_id = cur.lastrowid
            conn.commit()
            
            # Obter a data de cadastro em uma consulta separada
            cur.execute('SELECT data_cadastro FROM usuarios WHERE id = %s', (usuario_id,))
            data_cadastro = cur.fetchone()[0]
            
            usuario = {
                'id': usuario_id,
                'nome': nome,
                'email': email,
                'endereco': endereco,
                'telefone': telefone,
                'data_cadastro': data_cadastro.isoformat() if isinstance(data_cadastro, datetime) else data_cadastro
            }
            
            cur.close()
            conn.close()
            
            return jsonify(usuario), 201
            
        except Exception as e:
            conn.rollback()
            cur.close()
            conn.close()
            return jsonify({"erro": f"Erro ao cadastrar usuário: {str(e)}"}), 500

    @app.route('/usuarios/<int:id>', methods=['PUT'])
    def atualizar_usuario(id):
        usuario_atualizado = request.json
        nome = usuario_atualizado.get('nome')
        email = usuario_atualizado.get('email')
        senha = usuario_atualizado.get('senha')  # Opcional
        endereco = usuario_atualizado.get('endereco', '')
        telefone = usuario_atualizado.get('telefone', '')
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Verificar se o usuário existe
        cur.execute('SELECT id, data_cadastro FROM usuarios WHERE id = %s', (id,))
        row = cur.fetchone()
        
        if row is None:
            cur.close()
            conn.close()
            return jsonify({"erro": "Usuário não encontrado"}), 404
            
        data_cadastro = row[1]
        
        # Verificar se o email já está em uso por outro usuário
        if email:
            cur.execute('SELECT id FROM usuarios WHERE email = %s AND id != %s', (email, id))
            if cur.fetchone() is not None:
                cur.close()
                conn.close()
                return jsonify({"erro": "Email já está em uso por outro usuário"}), 400
        
        try:
            # Atualizar com ou sem senha
            if senha:
                senha_hash = generate_password_hash(senha)
                cur.execute(
                    'UPDATE usuarios SET nome = %s, email = %s, senha_hash = %s, endereco = %s, telefone = %s WHERE id = %s',
                    (nome, email, senha_hash, endereco, telefone, id)
                )
            else:
                cur.execute(
                    'UPDATE usuarios SET nome = %s, email = %s, endereco = %s, telefone = %s WHERE id = %s',
                    (nome, email, endereco, telefone, id)
                )
                
            conn.commit()
            
            usuario = {
                'id': id,
                'nome': nome,
                'email': email,
                'endereco': endereco,
                'telefone': telefone,
                'data_cadastro': data_cadastro.isoformat() if isinstance(data_cadastro, datetime) else data_cadastro
            }
            
            cur.close()
            conn.close()
            
            return jsonify(usuario)
            
        except Exception as e:
            conn.rollback()
            cur.close()
            conn.close()
            return jsonify({"erro": f"Erro ao atualizar usuário: {str(e)}"}), 500

    @app.route('/usuarios/<int:id>', methods=['DELETE'])
    def remover_usuario(id):
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Verificar se o usuário existe
        cur.execute('SELECT id FROM usuarios WHERE id = %s', (id,))
        if cur.fetchone() is None:
            cur.close()
            conn.close()
            return jsonify({"erro": "Usuário não encontrado"}), 404
            
        try:
            # Excluir o usuário (tokens serão excluídos por CASCADE)
            cur.execute('DELETE FROM usuarios WHERE id = %s', (id,))
            conn.commit()
            
            cur.close()
            conn.close()
            
            return jsonify({"mensagem": f"Usuário {id} removido com sucesso"})
            
        except Exception as e:
            conn.rollback()
            cur.close()
            conn.close()
            return jsonify({"erro": f"Erro ao remover usuário: {str(e)}"}), 500

    @app.route('/auth/login', methods=['POST'])
    def login():
        credenciais = request.json
        email = credenciais.get('email')
        senha = credenciais.get('senha')
        
        if not email or not senha:
            return jsonify({"erro": "Email e senha são obrigatórios"}), 400
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Verificar credenciais
        cur.execute('SELECT id, nome, email, senha_hash FROM usuarios WHERE email = %s', (email,))
        row = cur.fetchone()
        
        if row is None or not check_password_hash(row[3], senha):
            cur.close()
            conn.close()
            return jsonify({"erro": "Credenciais inválidas"}), 401
        
        # Gerar token de autenticação
        token = str(uuid.uuid4())
        expiracao = datetime.now() + timedelta(days=1)
        
        # Armazenar token
        cur.execute(
            'INSERT INTO tokens (token, usuario_id, expiracao) VALUES (%s, %s, %s)',
            (token, row[0], expiracao)
        )
        conn.commit()
        
        # Montar resposta
        response = {
            "token": token,
            "usuario": {
                "id": row[0],
                "nome": row[1],
                "email": row[2]
            }
        }
        
        cur.close()
        conn.close()
        
        return jsonify(response)

    @app.route('/auth/verificar', methods=['POST'])
    def verificar_token():
        token_info = request.json
        token = token_info.get('token')
        
        if not token:
            return jsonify({"valido": False, "erro": "Token não fornecido"}), 400
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Verificar se o token existe e não expirou
        cur.execute('''
            SELECT t.usuario_id, t.expiracao, u.nome, u.email
            FROM tokens t
            JOIN usuarios u ON t.usuario_id = u.id
            WHERE t.token = %s
        ''', (token,))
        
        row = cur.fetchone()
        
        if row is None:
            cur.close()
            conn.close()
            return jsonify({"valido": False, "erro": "Token inválido"}), 401
            
        usuario_id, expiracao, nome, email = row
        
        # Verificar se o token expirou
        if datetime.now() > expiracao:
            # Remover token expirado
            cur.execute('DELETE FROM tokens WHERE token = %s', (token,))
            conn.commit()
            
            cur.close()
            conn.close()
            return jsonify({"valido": False, "erro": "Token expirado"}), 401
            
        # Token válido
        response = {
            "valido": True,
            "usuario": {
                "id": usuario_id,
                "nome": nome,
                "email": email
            }
        }
        
        cur.close()
        conn.close()
        
        return jsonify(response)

    @app.route('/auth/logout', methods=['POST'])
    def logout():
        token_info = request.json
        token = token_info.get('token')
        
        if not token:
            return jsonify({"mensagem": "Logout realizado com sucesso"})
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Remover o token
        cur.execute('DELETE FROM tokens WHERE token = %s', (token,))
        conn.commit()
        
        cur.close()
        conn.close()
        
        return jsonify({"mensagem": "Logout realizado com sucesso"})

    @app.route('/health', methods=['GET'])
    def health():
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute('SELECT 1')
            cur.close()
            conn.close()
            return jsonify({"status": "ok", "database": "connected"}), 200
        except Exception as e:
            return jsonify({"status": "erro", "database": "disconnected", "detalhes": str(e)}), 500

    @app.route('/usuarios/<int:id>/senha', methods=['PATCH'])
    def atualizar_senha(id):
        dados = request.json
        senha_atual = dados.get('senha_atual')
        nova_senha = dados.get('nova_senha')
        
        if not senha_atual or not nova_senha:
            return jsonify({"erro": "Senha atual e nova senha são obrigatórias"}), 400
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Verificar se o usuário existe
        cur.execute('SELECT senha_hash FROM usuarios WHERE id = %s', (id,))
        row = cur.fetchone()
        
        if row is None:
            cur.close()
            conn.close()
            return jsonify({"erro": "Usuário não encontrado"}), 404
        
        # Verificar se a senha atual está correta
        if not check_password_hash(row[0], senha_atual):
            cur.close()
            conn.close()
            return jsonify({"erro": "Senha atual incorreta"}), 401
        
        try:
            # Atualizar a senha
            nova_senha_hash = generate_password_hash(nova_senha)
            cur.execute('UPDATE usuarios SET senha_hash = %s WHERE id = %s', (nova_senha_hash, id))
            conn.commit()
            
            cur.close()
            conn.close()
            
            return jsonify({"mensagem": "Senha atualizada com sucesso"})
            
        except Exception as e:
            conn.rollback()
            cur.close()
            conn.close()
            return jsonify({"erro": f"Erro ao atualizar senha: {str(e)}"}), 500