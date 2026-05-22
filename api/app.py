from flask import Flask, jsonify, render_template
from flask_cors import CORS
from flask_caching import Cache
from .config import get_config

cache = Cache()


def create_app():
    app = Flask(__name__, static_folder="../frontend/static", template_folder="../frontend/templates")
    app.config.from_object(get_config())

    CORS(app)
    cache.init_app(app)

    # Enregistrement des blueprints
    from .routes.transactions import bp as transactions_bp
    from .routes.estimateur import bp as estimateur_bp
    from .routes.carte import bp as carte_bp
    from .routes.analyses import bp as analyses_bp
    from .routes.opportunites import bp as opportunites_bp
    from .routes.communes import bp as communes_bp

    app.register_blueprint(transactions_bp, url_prefix="/api/transactions")
    app.register_blueprint(estimateur_bp,   url_prefix="/api/estimateur")
    app.register_blueprint(carte_bp,        url_prefix="/api/carte")
    app.register_blueprint(analyses_bp,     url_prefix="/api/analyses")
    app.register_blueprint(opportunites_bp, url_prefix="/api/opportunites")
    app.register_blueprint(communes_bp,     url_prefix="/api/communes")

    # Pages HTML
    @app.route("/")
    def page_index():
        return render_template("index.html")

    @app.route("/carte")
    def page_carte():
        return render_template("carte.html")

    @app.route("/commune")
    def page_commune():
        return render_template("commune.html")

    @app.route("/opportunites")
    def page_opportunites():
        return render_template("opportunites.html")

    @app.route("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Ressource introuvable"}), 404

    @app.errorhandler(422)
    def unprocessable(e):
        return jsonify({"error": "Paramètres invalides"}), 422

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"error": "Erreur serveur interne"}), 500

    return app
