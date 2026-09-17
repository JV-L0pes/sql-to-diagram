[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

# SQL to ER Diagram

Transforme scripts SQL em diagramas entidade-relacionamento (ER) de forma automática, visual e intuitiva.  
Automatically transform SQL scripts into intuitive and visual entity-relationship (ER) diagrams.

---

## 🚀 Features | Funcionalidades

- Suporte a PostgreSQL, MySQL e SQL Server  
  Support for PostgreSQL, MySQL, and SQL Server
- Detecção automática de tabelas, chaves primárias e estrangeiras  
  Automatic detection of tables, primary and foreign keys
- Visualização clara e responsiva do diagrama  
  Clear and responsive diagram visualization
- Exportação em PNG, SVG e PDF (em breve)  
  Export to PNG, SVG, and PDF (coming soon)

---

## 🖥️ Como usar | How to use

### 1. Instale as dependências | Install dependencies

```bash
npm install
# ou | or
yarn install
```

### 2. Rode o servidor de desenvolvimento | Run the development server

```bash
npm run dev
# ou | or
yarn dev
```

Acesse [http://localhost:3000](http://localhost:3000) no seu navegador.  
Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## ✨ Exemplo de uso | Usage Example

Cole seu script SQL na área indicada e clique em "Gerar Diagrama".  
Paste your SQL script and click "Generate Diagram".

```sql
CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  email VARCHAR(100) UNIQUE
);

CREATE TABLE posts (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL,
  title VARCHAR(200) NOT NULL,
  content TEXT,
  FOREIGN KEY (user_id) REFERENCES users(id)
);
```

---

## 🛠️ Tecnologias | Technologies

- [Next.js](https://nextjs.org/)
- [TypeScript](https://www.typescriptlang.org/)
- [Tailwind CSS](https://tailwindcss.com/)

---

## Development

This is a pnpm monorepo:

- `apps/web` — Vite + React frontend
- `apps/api` — FastAPI backend
- `packages/ui` — shared React components
- `packages/api-client` — TS types generated from the API's OpenAPI schema

### Setup

```bash
pnpm install
cd apps/api && python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"
```

Create `apps/api/.env` with a Neon connection string (see `docs/superpowers/specs/2026-09-16-foundation-design.md`).

### Run locally

```bash
# terminal 1
cd apps/api && uvicorn src.main:app --reload

# terminal 2
pnpm --filter web dev
```

### Test

```bash
pnpm --filter web test
cd apps/api && pytest
```

---

## 📄 Licença | License

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.  
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
