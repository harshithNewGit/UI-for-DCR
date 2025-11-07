from waitress import serve
from app import app

if __name__ == '__main__':
    # This script will serve the Flask app using the Waitress WSGI server.
    # It's the entry point for our production environment managed by PM2.
    print("Starting production server with Waitress on http://0.0.0.0:5000")
    serve(app, host='0.0.0.0', port=5000)