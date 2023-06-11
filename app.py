from flask import Flask, Blueprint
from flask_cors import CORS 
from endpoints import apiRoutes

def createApp():
    app = Flask(__name__)
    CORS(app)
    api_blueprint = Blueprint('api_blueprint', __name__)
    api_blueprint = apiRoutes(api_blueprint)
    app.register_blueprint(api_blueprint, url_prefix='/api')    
    return app

app = createApp()

if __name__ == "__main__":
    app.run(host="0.0.0.0",debug=True)