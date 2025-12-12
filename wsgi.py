from app import create_app

app = create_app()

if __name__ == "__main__":
    # Bind to 0.0.0.0 and use environment PORT
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
