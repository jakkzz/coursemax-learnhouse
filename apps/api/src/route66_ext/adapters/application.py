"""Supported FastAPI/Uvicorn composition; no native handlers or routes are patched."""

def install_retention(app, **middleware_options):
    from src.core.middleware.cors import configure_cors
    from src.security.csrf import CSRFProtectionMiddleware
    from src.route66_ext.security.syllabus_retention import SyllabusRetentionMiddleware

    app.add_middleware(SyllabusRetentionMiddleware, **middleware_options)
    # Keep native origin policy outside our short-circuit responses as well.
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
