import multiprocessing
import os

# Configuración de Gunicorn para Render
bind = "0.0.0.0:" + os.environ.get("PORT", "5000")
workers = 1  # Reducir workers para evitar problemas de memoria en plan free
threads = 2
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50
timeout = 120
keepalive = 2

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Pre-load app para mejor performance
preload_app = True

# Server hooks
def pre_fork(server, worker):
    pass

def pre_exec(server):
    server.log.info("Forked child, re-executing.")

def when_ready(server):
    server.log.info("Server is ready. Spawning workers")

def worker_int(worker):
    worker.log.info("worker received INT or QUIT signal")

def worker_abort(worker):
    worker.log.info("worker received SIGABRT signal")
