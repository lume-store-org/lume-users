CREATE TABLE IF NOT EXISTS usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    senha_hash VARCHAR(255) NOT NULL,
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
-- Senha padrão: senha123 (hash scrypt com salt, gerado pelo werkzeug)
INSERT INTO usuarios (id, nome, email, senha_hash, endereco, telefone, data_cadastro)
VALUES (
    1, 
    'Usuário Teste', 
    'usuario@teste.com', 
    'scrypt:32768:8:1$hGuvljWT0CpqClSt$ca52c7149a7c8fb30f74844d0a3eabbc80a61b87ee7f06235ae46efd914d25472d643551ce96b796d7a5bd7a2c39d7f5771a0b8bc855027e2e56de22a3bc8bf5', 
    'Rua de Teste, 123', 
    '(11) 98765-4321',
    '2025-04-01 14:30:00'
);