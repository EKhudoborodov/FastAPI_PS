import os, psycopg2, uvicorn

if __name__ == '__main__':
    uvicorn.run("app.main:app",
                host="0.0.0.0",
                port=8432,
                reload=True,
                ssl_keyfile="./cert/key.pem", 
                ssl_certfile="./cert/cert.pem"
                )