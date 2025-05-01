CREATE TABLE IF NOT EXISTS usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    senha_hash VARCHAR(100) NOT NULL,
    endereco TEXT,
    telefone VARCHAR(20),
    data_cadastro TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tokens (
    token VARCHAR(100) PRIMARY KEY,
    usuario_id INT NOT NULL,
    expiracao TIMESTAMP NOT NULL,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
);

-- Inserir dados iniciais para testes
-- Senha padrão: senha123 (em SHA-256)
INSERT INTO usuarios (id, nome, email, senha_hash, endereco, telefone, data_cadastro)
VALUES (
    1, 
    'Usuário Teste', 
    'usuario@teste.com', 
    'a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3', 
    'Rua de Teste, 123', 
    '(11) 98765-4321',
    '2025-04-01 14:30:00'
);