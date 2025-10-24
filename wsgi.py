from app import app, create_tables

# Crear tablas al iniciar
create_tables()

if __name__ == "__main__":
    app.run()
