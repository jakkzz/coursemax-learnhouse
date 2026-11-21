"""Supported FastAPI/Uvicorn composition; native writers call owned retention hooks."""

def install_retention(app):
    from src.core.middleware.cors import configure_cors
    from src.security.csrf import CSRFProtectionMiddleware
    # Retention uses the native request transaction, never a second middleware
    # session. Keep the existing origin policy and launcher composition unchanged.
    app.add_middleware(CSRFProtectionMiddleware)
    configure_cors(app)
    return app


def create_app():
    from app import app
    return install_retention(app)


def run_api():
    import uvicorn
    from config.config import get_learnhouse_config
    config = get_learnhouse_config()
    uvicorn.run('src.route66_ext.adapters.application:create_app', factory=True,
                host='0.0.0.0', port=config.hosting_config.port,
                reload=config.general_config.development_mode)
