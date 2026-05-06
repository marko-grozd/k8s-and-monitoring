.PHONY: help dev k8s-up k8s-down k8s-status logs clean

NAMESPACE = skeleton

help: ## Prikazi sve komande
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Docker Compose (lokalni razvoj bez k8s) ───────────────────────────────────
dev: ## Pokreni sa docker-compose (najbrze za razvoj)
	docker compose up --build

dev-down: ## Zaustavi docker-compose
	docker compose down

dev-clean: ## Zaustavi i obrisi volumes
	docker compose down -v

# ── Kubernetes ────────────────────────────────────────────────────────────────
k8s-up: ## Deploy svih manifesta na k8s klaster
	kubectl apply -f k8s/namespace.yaml
	kubectl apply -f k8s/postgres/
	kubectl apply -f k8s/redis/
	kubectl apply -f k8s/backend/
	kubectl apply -f k8s/frontend/
	kubectl apply -f k8s/ingress/
	@echo "✅ Deployed! Cekaj da Podovi budu Ready..."
	kubectl wait --for=condition=ready pod -l app=backend -n $(NAMESPACE) --timeout=120s

k8s-down: ## Obrisi sve k8s resurse
	kubectl delete namespace $(NAMESPACE)

k8s-status: ## Prikazi status svih resursa
	@echo "\n=== Pods ==="
	kubectl get pods -n $(NAMESPACE)
	@echo "\n=== Services ==="
	kubectl get services -n $(NAMESPACE)
	@echo "\n=== Ingress ==="
	kubectl get ingress -n $(NAMESPACE)
	@echo "\n=== HPA ==="
	kubectl get hpa -n $(NAMESPACE) 2>/dev/null || true

# ── Logs ──────────────────────────────────────────────────────────────────────
logs-backend: ## Prati logove backend Podova
	kubectl logs -f -l app=backend -n $(NAMESPACE) --all-containers

logs-frontend: ## Prati logove frontend Podova
	kubectl logs -f -l app=frontend -n $(NAMESPACE)

logs-postgres: ## Prati logove Postgres
	kubectl logs -f -l app=postgres -n $(NAMESPACE)

# ── Port Forward (pristup bez Ingress-a) ──────────────────────────────────────
pf-backend: ## Port-forward backend na localhost:8000
	kubectl port-forward svc/backend-service 8000:8000 -n $(NAMESPACE)

pf-frontend: ## Port-forward frontend na localhost:3000
	kubectl port-forward svc/frontend-service 3000:80 -n $(NAMESPACE)

pf-postgres: ## Port-forward Postgres na localhost:5432
	kubectl port-forward svc/postgres-service 5432:5432 -n $(NAMESPACE)

# ── Skaffold (live dev u k8s) ─────────────────────────────────────────────────
skaffold-dev: ## Pokreni skaffold dev loop (auto-rebuild na promene)
	skaffold dev

# ── Build Docker slika ────────────────────────────────────────────────────────
build: ## Build Docker slike lokalno
	docker build -t k8s-skeleton-frontend:latest ./frontend
	docker build -t k8s-skeleton-backend:latest ./backend

# ── Skaliranje ────────────────────────────────────────────────────────────────
scale-backend: ## Skaliraj backend (make scale-backend REPLICAS=5)
	kubectl scale deployment backend --replicas=$(REPLICAS) -n $(NAMESPACE)
