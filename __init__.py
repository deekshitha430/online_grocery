from flask import Flask, session
from project.routes import admin, default


def create_app():
    app = Flask(__name__)
    app.secret_key = "plmoknijbuhvygctfxrdz"
    app.register_blueprint(default)
    app.register_blueprint(admin)

    return app

