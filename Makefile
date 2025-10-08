ifeq (,$(wildcard .env))
$(error .env file is missing. Please create one based on .env.example)
endif

include .env

CHECK_DIRS := .

ava-build:
	docker compose build

ava-run:
	docker compose up --build -d

ava-stop:
	docker compose stop

ava-delete:
	@if [ -d "long_term_memory" ]; then rm -rf long_term_memory; fi
	@if [ -d "short_term_memory" ]; then rm -rf short_term_memory; fi
	@if [ -d "generated_images" ]; then rm -rf generated_images; fi
	docker compose down

format-fix:
	uv run ruff format $(CHECK_DIRS) 
	uv run ruff check --select I --fix $(CHECK_DIRS)

lint-fix:
	uv run ruff check --fix $(CHECK_DIRS)

format-check:
	uv run ruff format --check $(CHECK_DIRS) 
	uv run ruff check -e $(CHECK_DIRS)
	uv run ruff check --select I -e $(CHECK_DIRS)

lint-check:
	uv run ruff check $(CHECK_DIRS)

# Azure deployment commands
azure-deploy:
	@chmod +x deploy-azure-simple.sh
	./deploy-azure-simple.sh

azure-update:
	@chmod +x update-azure.sh
	./update-azure.sh

azure-fix-env:
	@chmod +x fix-env-vars.sh
	./fix-env-vars.sh

azure-webhook-url:
	@if [ ! -f azure-deployment-config.txt ]; then \
		echo "Error: Run 'make azure-deploy' first"; \
		exit 1; \
	fi
	@echo ""; \
	echo "========================================"; \
	echo "  WhatsApp Webhook Configuration"; \
	echo "========================================"; \
	APP_URL=$$(grep "Application URL:" azure-deployment-config.txt | cut -d' ' -f3); \
	echo "Webhook URL (use this in Meta portal):"; \
	echo "  $$APP_URL/whatsapp_response"; \
	echo ""; \
	echo "⚠️  IMPORTANT: Path is /whatsapp_response"; \
	echo "              NOT /webhook"; \
	echo ""; \
	echo "Subscribe to these webhook fields:"; \
	echo "  - messages"; \
	echo "  - messaging_postbacks"; \
	echo "========================================"; \
	echo ""

azure-logs:
	@if [ ! -f azure-deployment-config.txt ]; then \
		echo "Error: Run 'make azure-deploy' first"; \
		exit 1; \
	fi
	@CONTAINER_APP=$$(grep "Container App:" azure-deployment-config.txt | cut -d' ' -f3); \
	RESOURCE_GROUP=$$(grep "Resource Group:" azure-deployment-config.txt | cut -d' ' -f3); \
	az containerapp logs show --name $$CONTAINER_APP --resource-group $$RESOURCE_GROUP --follow

azure-status:
	@if [ ! -f azure-deployment-config.txt ]; then \
		echo "Error: Run 'make azure-deploy' first"; \
		exit 1; \
	fi
	@CONTAINER_APP=$$(grep "Container App:" azure-deployment-config.txt | cut -d' ' -f3); \
	RESOURCE_GROUP=$$(grep "Resource Group:" azure-deployment-config.txt | cut -d' ' -f3); \
	az containerapp show --name $$CONTAINER_APP --resource-group $$RESOURCE_GROUP --query "{name:name,status:properties.runningStatus,url:properties.configuration.ingress.fqdn,replicas:properties.template.scale}"

azure-delete:
	@if [ ! -f azure-deployment-config.txt ]; then \
		echo "Error: No deployment found"; \
		exit 1; \
	fi
	@RESOURCE_GROUP=$$(grep "Resource Group:" azure-deployment-config.txt | cut -d' ' -f3); \
	echo "WARNING: This will delete all Azure resources in $$RESOURCE_GROUP"; \
	read -p "Are you sure? (y/N) " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		az group delete --name $$RESOURCE_GROUP --yes --no-wait; \
		rm -f azure-deployment-config.txt; \
		echo "Azure resources deletion initiated"; \
	fi