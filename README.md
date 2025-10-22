# Biblioteca por Email (FastAPI + Worker IMAP/SMTP)

Proyecto sencillo para **gestionar reservas de libros vía correo electrónico**.  
Un **worker** lee tu bandeja (IMAP), interpreta la intención del mensaje (con **reglas** o **LLM opcional** vía LangChain), ejecuta la transacción en una **BD SQLite** y responde por **SMTP** con un texto claro y amable.  
Además, se expone una **API FastAPI** con documentación automática (Swagger).

---

## Construir e iniciar

```bash
docker compose build --no-cache
docker compose up -d
```

## Ver logs

```bash
docker compose logs -f --tail=200 worker
docker compose logs -f --tail=200 api
```

## API Docs

Abre en tu navegador:

- **Swagger:** http://localhost:8000/docs  
- **ReDoc:** http://localhost:8000/redoc

---

## (Opcional) Publicar imágenes en Azure Container Registry (ACR)

Esto solo sube las imágenes a tu registro de Azure. El despliegue en un servicio (ACI/Container Apps/AKS) es un paso aparte. Mantengo los comandos mínimos.

```bash
ACR_NAME=mibibliotecareg
az acr create --name $ACR_NAME --resource-group rg-biblioteca --sku Basic
```
