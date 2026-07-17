# Sakila Movie Rental Portal Pro - Fixed

Full-stack Docker app using React + Node.js Express + MySQL Sakila.

## Docker Run

```powershell
cd C:\Users\skred\GitHub\sakila-movie-rental-portal-pro
docker compose down -v
docker compose up -d --build
docker ps
```

Open:

- Frontend: http://localhost:3000
- Backend Health: http://localhost:5000/api/health

## Kubernetes Run

First build images:

```powershell
docker build -t sakila-backend:local ./backend
docker build -t sakila-frontend:local ./frontend
kubectl apply -f k8s
kubectl get pods
kubectl get svc
```

Open:

- Frontend: http://localhost:30081
- Backend: http://localhost:30080/api/health

Cleanup:

```powershell
kubectl delete -f k8s
docker compose down -v
```
