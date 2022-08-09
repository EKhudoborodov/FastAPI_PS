import os, psycopg2, uvicorn, app.functional
from fastapi import FastAPI, Depends, HTTPException, status, Query
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
def sign_up(fullname: str, username: str = Query(min_length=4, max_length=50), password: str = Query(min_length=8, max_length=50), confirm_password: str = Query(min_length=8, max_length=50)):
    if functional.field_check(username) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BADREQUEST,
            detail="You can't use space or apostrophe in username.",
            headers={"WWW-Authenticate": "Bearer"},
        ) 
    if functional.field_check(password) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BADREQUEST,
            detail="You can't use space or apostrophe in password.",
            headers={"WWW-Authenticate": "Bearer"},
        )      
    if password != confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BADREQUEST,
            detail="Passwords are different!",
            headers={"WWW-Authenticate": "Bearer"},
        )
    else:
        cursor.execute(f"SELECT * FROM public.users WHERE login='{username}'", (str(username), str(password)))
        records = list(cursor.fetchall())
        if records != []:
            raise HTTPException(
                status_code=status.HTTP_400_BADREQUEST,
                detail="This username has already taken.",
                headers={"WWW-Authenticate": "Bearer"},
            )
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
            return {"username": username, "password": password}

@app.get("/users/me")
def read_current_user(credentials: OAuth2PasswordRequestForm = Depends(security)):
    return credentials
    
@app.get("/role")
def update_role(username: str, role: str = Query(default="writer", description="Print 'writer', 'moderator' or 'ban'."), action: str = Query(default="add", description="Print 'add' or 'remove'."), credentials: OAuth2PasswordRequestForm = Depends(security)):
    if credentials[0] != '1':
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="You aren't administrator.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    else:
        if functional.field_check(username) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BADREQUEST,
                detail="You can't use space or apostrophe in username.",
                headers={"WWW-Authenticate": "Bearer"},
            ) 
        else:
            cursor.execute(f"SELECT * FROM public.users WHERE login='{username}'")
            records = list(cursor.fetchall())
            if records == []:
                raise HTTPException(
                    status_code=status.HTTP_400_BADREQUEST,
                    detail="There is no such user in database.",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            elif role != "writer" and role != "moderator" and role != "ban":
                raise HTTPException(
                    status_code=status.HTTP_400_BADREQUEST,
                    detail="Print 'writer', 'moderator' or 'ban' in role field.",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            elif action != "add" and action != "remove":
                raise HTTPException(
                    status_code=status.HTTP_400_BADREQUEST,
                    detail="Print 'add' or 'remove'. in action field.",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            else:
                role_id = functional.crypt_role(role)
                if role_id != 5:
                    if action == 'remove':
                        #removing user's role
                        cursor.execute(f"DELETE FROM public.role_user WHERE user_id={user_id} and role_id={role_id}")
                        conn.commit()
                        #checking if user has any other roles
                        cursor.execute(f"SELECT * FROM public.role_user WHERE user_id={user_id}")
                        records = list(cursor.fetchall())
                        #if user has not other roles add Reader role
                        if records == []:
                            cursor.execute(f"INSERT INTO public.role_user (user_id, role_id) VALUES ({user_id}, 4)")
                            conn.commit()
                            return "Role is seccessfuly removed."
                    else:
                        #adding role to user
                        cursor.execute(f"INSERT INTO public.role_user (user_id, role_id) VALUES ({user_id}, {role_id})")
                        conn.commit()
                        return "Role is seccessfuly added."
                else:
                    #if administrator want to ban user or remove user from ban list
                    if action == 'remove':
                        #giving user Reader role back
                        cursor.execute(f"UPDATE public.role_user SET role_id=4 WHERE user_id={user_id} and role_id={role_id}")
                        cursor.execute(f"UPDATE public.users SET banned={False} WHERE id={user_id}")
                        conn.commit()
                        return f"{username} is removed from banlist."
                    else:
                        #sending user into ban list
                        cursor.execute(f"UPDATE public.role_user SET role_id={role_id} WHERE user_id={user_id}")
                        cursor.execute(f"UPDATE public.users SET banned={True} WHERE id={user_id}")
                        conn.commit()
                        return f"{username} is banned now."

    