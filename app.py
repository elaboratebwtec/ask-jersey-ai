import os
from flask import Flask, jsonify, Blueprint, render_template

# Initialize the Flask application
app = Flask(__name__)

# Define a Blueprint for our API routes.
# This helps in organizing routes, especially as the application grows.
# All routes defined in this blueprint will be prefixed with /api.
api_bp = Blueprint('api', __name__, url_prefix='/api')

# This is the placeholder for your main AI query endpoint.
# It's set up to receive POST requests (as user queries will likely send data).
@api_bp.route('/query', methods=['POST'])
def handle_query():
    # TODO: This is where your RAG (Retrieval Augmented Generation) logic will go.
    # For now, it just returns a confirmation message.
    return jsonify({"message": "API query endpoint for Ask Jersey AI is active"}), 200

# Register the blueprint with the main Flask app.
# This makes the routes defined in api_bp (like /api/query) accessible.
app.register_blueprint(api_bp)

# This is your /ping route to check if the server is alive.
# It returns a JSON response.

# NEW ROUTE to serve the HTML page
@app.route('/')
def home():
    return render_template('index.html')

@app.route("/ping")
def ping():
    return jsonify({"status": "alive", "message": "pong"})

# This block ensures the Flask development server runs only when 
# the script is executed directly (e.g., using "python app.py").
if __name__ == "__main__":
    # Get the PORT from environment variables, defaulting to 5000 for local development.
    # Railway will set the 'PORT' environment variable when deployed.
    port = int(os.environ.get('PORT', 5000))
    
    # Run the Flask development server.
    # host='0.0.0.0' makes the server accessible from any network interface on your Mac,
    # not just localhost. This is important for some deployment setups and testing.
    # debug=True enables Flask's debugger and auto-reloader, which is very useful during development.
    app.run(debug=True, host='0.0.0.0', port=port)
