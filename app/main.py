import os, psycopg2, uvicorn
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
app = FastAPI()

conn = psycopg2.connect(database="server_db",
                        user="postgres",
                        password="postgres",
                        host="localhost",
                        port="5432")

cursor = conn.cursor()

"""
users: {id, login, password, fullname, isbanned}
role_user: {user_id, role_id}
article: {id, name, title, description, isdeleted, date}
article_writer: {article_id, user_id, isauthor}
article_status: {article_id, status_id}
article_topic: {article_id, topic_id}
topic: {id, name}
rating: {id, user_id, article_id, date, rate, isdeleted}
user_read: {user_id, article_id, isread}
"""

security = OAuth2PasswordBearer(tokenUrl="sign_in")

@app.post('/sign_in')
async def token(form_data: OAuth2PasswordRequestForm = Depends()):
    cursor.execute(f"SELECT * FROM public.users WHERE login='{form_data.username}' AND password='{form_data.password}'")
    records = list(cursor.fetchall())
    if records != []:
        cursor.execute(f"SELECT * FROM public.role_user WHERE user_id={records[0][0]}")
        user_desc = list(cursor.fetchall())
        return {'access_token': f"{user_desc[0][1]}" + " " + form_data.username}
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
@app.get("/sign_up")
def sign_up(fullname:str, username:str, password:str, confirm_password:str):
    for char in username:
        if char == " " or char == "'":
            return "You can't use space or apostrophe in username."
    for char in password:
        if char == " " or char == "'":
            return "You can't use space or apostrophe in password."       
    if password != confirm_password:
        return "Passwords are different!"
    else:
        cursor.execute(f"SELECT * FROM public.users WHERE login='{username}'", (str(username), str(password)))
        records = list(cursor.fetchall())
        if records != []:
            return "This username has already taken."
        else:
            cursor.execute(f"INSERT INTO public.users (login, password, fullname, banned) VALUES ('{username}', '{password1}', '{fullname}', {False})")
            conn.commit()
            cursor.execute(f"SELECT * FROM public.users WHERE login='{username}'")
            records = list(cursor.fetchall())
            cursor.execute(f"INSERT INTO public.role_user (user_id, role_id) VALUES ('{records[0][0]}', 4)")
            conn.commit()
            cursor.execute(f"SELECT * FROM public.article WHERE isdeleted={False}")
            article_desc = list(cursor.fetchall())
            for article in article_desc:
                article_id = article[0]
                cursor.execute(f"SELECT * FROM public.article_status WHERE article_id={article_id}")
                status_desc = list(cursor.fetchall())
                if status_desc[0][1] == 3:
                    cursor.execute(f"INSERT INTO public.user_read (user_id, article_id, isread) VALUES ({records[0][0]}, {article_id}, {False})")
            conn.commit()
            return {"username":username, "password":password}

@app.get("/users/me")
def read_current_user(credentials: OAuth2PasswordRequestForm = Depends(security)):
    return credentials


    