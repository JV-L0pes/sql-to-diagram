# Makefile - Docker Commands
.PHONY: help build build-dev build-prod up up-dev up-prod down clean logs shell test

# Default target
help:
	@echo "SQL Architect - Docker Commands"
	@echo "================================"
	@echo "Development:"
	@echo "  dev          - Start development environment"
	@echo "  dev-build    - Build and start development"
	@echo "  dev-logs     - Show development logs"
	@echo "  dev-shell    - Access development container shell"
	@echo ""
	@echo "Production:"
	@echo "  prod         - Start production environment"
	@echo "  prod-build   - Build and start production"
	@echo "  prod-logs    - Show production logs"
	@echo ""
	@echo "General:"
	@echo "  build        - Build all images"
	@echo "  down         - Stop all containers"
	@echo "  clean        - Remove containers and images"
	@echo "  prune        - Clean Docker system"

# Development
dev:
	docker-compose up app-dev

dev-build:
	docker-compose up --build app-dev

dev-logs:
	docker-compose logs -f app-dev

dev-shell:
	docker-compose exec app-dev sh

# Production
prod:
	docker-compose --profile production up -d

prod-build:
	docker-compose --profile production up --build -d

prod-logs:
	docker-compose --profile production logs -f

# Build commands
build:
	docker-compose build

build-dev:
	docker-compose build app-dev

build-prod:
	docker-compose build app-prod

# Control commands
down:
	docker-compose down

stop:
	docker-compose stop

restart:
	docker-compose restart

# Cleanup commands
clean:
	docker-compose down --rmi all --volumes --remove-orphans

prune:
	docker system prune -af --volumes

# Database/Cache
redis:
	docker-compose --profile cache up redis -d

# Health check
health:
	docker-compose ps

# Update dependencies
update:
	docker-compose exec app-dev npm update

# Install new dependency
install:
	docker-compose exec app-dev npm install $(PACKAGE)

# Run tests
test:
	docker-compose exec app-dev npm test

# Lint code
lint:
	docker-compose exec app-dev npm run lint

# TypeScript check
typecheck:
	docker-compose exec app-dev npm run type-check