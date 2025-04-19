# Colors for terminal output
GREEN := \033[0;32m
YELLOW := \033[1;33m
RED := \033[0;31m
NC := \033[0m # No Color

.PHONY: help env

# Default target
help:
	@echo "${YELLOW}Notes for Goats - Development Utilities${NC}"
	@echo ""
	@echo "${GREEN}Available commands:${NC}"
	@echo "  ${YELLOW}make help${NC}    - Show this help message"
	@echo "  ${YELLOW}make env${NC}     - Create/update .env file with interactive prompts"
	@echo "  ${YELLOW}make build${NC}   - Build Docker images"
	@echo "  ${YELLOW}make up${NC}      - Start Docker containers"
	@echo "  ${YELLOW}make down${NC}    - Stop Docker containers"
	@echo "  ${YELLOW}make restart${NC} - Restart Docker containers"
	@echo "  ${YELLOW}make logs${NC}    - Show Docker logs"
	@echo "  ${YELLOW}make shell${NC}   - Open shell in web container"
	@echo "  ${YELLOW}make migrate${NC} - Run Django migrations"
	@echo "  ${YELLOW}make makemigrations${NC} - Create Django migrations"
	@echo "  ${YELLOW}make superuser${NC} - Create superuser"
	@echo "  ${YELLOW}make test${NC}    - Run tests"

# Create or update the .env file based on .env.example
env:
	@echo "${GREEN}Setting up environment variables...${NC}"
	@bash scripts/setup_env.sh

# Docker-related commands
build:
	@echo "${GREEN}Building Docker images...${NC}"
	docker-compose build

up:
	@echo "${GREEN}Starting Docker containers...${NC}"
	docker-compose up -d

down:
	@echo "${GREEN}Stopping Docker containers...${NC}"
	docker-compose down

restart:
	@echo "${GREEN}Restarting Docker containers...${NC}"
	docker-compose restart

logs:
	@echo "${GREEN}Showing Docker logs...${NC}"
	docker-compose logs -f

shell:
	@echo "${GREEN}Opening shell in web container...${NC}"
	docker-compose exec web bash || docker-compose exec web sh

# Django-related commands
migrate:
	@echo "${GREEN}Running migrations...${NC}"
	docker-compose exec web python notes_for_goats/manage.py migrate

makemigrations:
	@echo "${GREEN}Creating migrations...${NC}"
	docker-compose exec web python notes_for_goats/manage.py makemigrations

superuser:
	@echo "${GREEN}Creating superuser...${NC}"
	docker-compose exec web python notes_for_goats/manage.py createsuperuser

test:
	@echo "${GREEN}Running tests...${NC}"
	docker-compose exec web python notes_for_goats/manage.py test
