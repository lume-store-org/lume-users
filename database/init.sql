SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    senha_hash VARCHAR(255) NOT NULL,
    endereco TEXT,
    telefone VARCHAR(20),
    is_admin BOOLEAN NOT NULL DEFAULT FALSE,
    data_cadastro TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS tokens (
    token VARCHAR(100) PRIMARY KEY,
    usuario_id INT NOT NULL,
    expiracao TIMESTAMP NOT NULL,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
);

-- Contas de demonstração (dados fictícios). Hashes scrypt com salt, gerados pelo werkzeug.
--   admin@loja.dev   / admin123  (administrador: gerencia o catálogo e todos os pedidos)
--   cliente@loja.dev / senha123  (cliente)
INSERT INTO usuarios (id, nome, email, senha_hash, endereco, telefone, is_admin, data_cadastro) VALUES
    (1, 'Admin da Loja', 'admin@loja.dev',
     'scrypt:32768:8:1$hbMh7bNk1AW6ByOk$87934d8ab2ed3bd34179111ac3b150d30af34242cbb0420dd199f5b8fe9f14c38f208a4b9bd9bb1aa57833a599b298e4811424d65a357e98938cb3999201c670',
     'Av. Exemplo, 1000 - São Paulo/SP', '(11) 90000-0000', TRUE, '2025-04-01 09:00:00'),
    (2, 'Cliente Demo', 'cliente@loja.dev',
     'scrypt:32768:8:1$2qDXVaFACQvfUYtx$a459a830bcbb0b997d03776db1550f2402199d2d55cf01e7ced45de71d66f05d19c5688ac74d12821a4c8b1ca7aed9fbfe8c09436339414bcfbe32c1216ff4c1',
     'Rua de Teste, 123 - São Paulo/SP', '(11) 91111-1111', FALSE, '2025-04-01 14:30:00');
