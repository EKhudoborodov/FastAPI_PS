import os, psycopg2, uvicorn, src.functional
from pydantic import BaseModel
from src.exceptions import exception
from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
app = FastAPI()

conn = psycopg2.connect(database="server_db",
                        user="postgres",
                        password="postgres",
                        host="localhost",
                        port="5432")

cursor = conn.cursor()

class Draft(BaseModel):
    title: str = ""
    article_text: str = ""

class Review(BaseModel):
    review_text : str = ""

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
        token = ""
        for desc in user_desc:
            if desc[1] != 5:
                token += f"{desc[1]}"
            else:
                token = 5
                break
        token += " " + form_data.username
        return {'access_token': token}
    else:
        return exception(status.HTTP_401_UNAUTHORIZED, "Incorrect username or password")
        
@app.get("/sign_up")
def sign_up(fullname: str, username: str = Query(min_length=4, max_length=50), password: str = Query(min_length=8, max_length=50), confirm_password: str = Query(min_length=8, max_length=50)):
    if src.functional.field_check(username, 1) == 0:
        return exception(status.HTTP_400_BAD_REQUEST, "You can't use space or apostrophe in username.")
    if src.functional.field_check(password, 1) == 0:
        return exception(status.HTTP_400_BAD_REQUEST, "You can't use space or apostrophe in password.")   
    if password != confirm_password:
        return exception(status.HTTP_400_BAD_REQUEST, "Passwords are different.")   
    else:
        cursor.execute(f"SELECT * FROM public.users WHERE login='{username}'", (str(username), str(password)))
        records = list(cursor.fetchall())
        if records != []:
            return exception(status.HTTP_400_BAD_REQUEST, "This username has already taken.") 
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

@app.get("/home")
def home(
            search_value: str = None,
            search_field: str = Query(description="Print 'name', 'author', 'topic' or 'date'.", default = None),
            topic_filter: str = Query(description="Print 'science', 'art', 'history' or 'news'.", default = None),
            rate_filter: str = Query(description="Print number from 1 to 5. Additional: Print '>' or '<' at the beggining.", default = None),
            views_filter: str = Query(description="Print '>' or '<' at the begining and then number of views.", default = None),
            credentials: OAuth2PasswordRequestForm = Depends(security)
        ):
    home_array = src.functional.select_table_recent(credentials)
    return src.functional.search_start(home_array, search_field, search_value, topic_filter, rate_filter, views_filter)

@app.get("/archive")
def archive(
                search_value: str = None,
                search_field: str = Query(description="Print 'name', 'author', 'topic' or 'date'.", default = None),
                topic_filter: str = Query(description="Print 'science', 'art', 'history' or 'news'.", default = None),
                rate_filter: str = Query(description="Print number from 1 to 5. Additional: Print '>' or '<' at the beggining.", default = None),
                views_filter: str = Query(description="Print '>' or '<' at the begining and then number of views.", default = None),
                credentials: OAuth2PasswordRequestForm = Depends(security)
            ):
    archive_array = src.functional.select_table_desc(credentials)
    return src.functional.search_start(archive_array, search_field, search_value, topic_filter, rate_filter, views_filter)

@app.get("/role")
def update_role(
                    username: str,
                    role: str = Query(description="Print 'writer', 'moderator' or 'ban'.", default = "writer"),
                    action: str = Query(description="Print 'add' or 'remove'.", default = "add"),
                    credentials: OAuth2PasswordRequestForm = Depends(security)
                ):
    if credentials[0] == '5':
        return exception(status.HTTP_423_LOCKED, "You are banned on server.")
    elif credentials[0] != '1':
        return exception(status.HTTP_423_LOCKED, "You aren't administrator.")
    else:
        if src.functional.field_check(username, 1) == 0:
            return exception(status.HTTP_400_BAD_REQUEST, "You can't use space or apostrophe in username.")
        else:
            cursor.execute(f"SELECT * FROM public.users WHERE login='{username}'")
            records = list(cursor.fetchall())
            if records == []:
                return exception(status.HTTP_400_BAD_REQUEST, "There is no such user in database.")
            elif role != "writer" and role != "moderator" and role != "ban":
                return exception(status.HTTP_400_BAD_REQUEST, "Print 'writer', 'moderator' or 'ban' in role field.")
            elif action != "add" and action != "remove":
                return exception(status.HTTP_400_BAD_REQUEST, "Print 'add' or 'remove'. in action field.")
            else:
                role_id = src.functional.crypt_role(role)
                user_id = records[0][0]
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
                        cursor.execute(f"DELETE FROM public.role_user WHERE user_id={user_id} and role_id={4}")
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

@app.get("/workshop")
def workshop(
                search_value: str = None,
                search_field: str = Query(description="Print 'name', 'author', 'topic' or 'date'.", default = None),
                topic_filter: str = Query(description="Print 'science', 'art', 'history' or 'news'.", default = None),
                rate_filter: str = Query(description="Print number from 1 to 5. Additional: Print '>' or '<' at the beggining.", default = None),
                views_filter: str = Query(description="Print '>' or '<' at the begining and then number of views.", default = None),
                credentials: OAuth2PasswordRequestForm = Depends(security)
            ):
    workshop_array = src.functional.select_table_personal(credentials)
    return src.functional.search_start(workshop_array, search_field, search_value, topic_filter, rate_filter, views_filter)

@app.get("/published")
def published(
                search_value: str = None,
                search_field: str = Query(description="Print 'name', 'author', 'topic' or 'date'.", default = None),
                topic_filter: str = Query(description="Print 'science', 'art', 'history' or 'news'.", default = None),
                rate_filter: str = Query(description="Print number from 1 to 5. Additional: Print '>' or '<' at the beggining.", default = None),
                views_filter: str = Query(description="Print '>' or '<' at the begining and then number of views.", default = None),
                credentials: OAuth2PasswordRequestForm = Depends(security)
             ):
    published_array = src.functional.select_table_published(credentials)
    return src.functional.search_start(published_array, search_field, search_value, topic_filter, rate_filter, views_filter)

@app.get("/create")
def create(article_name: str = Query(min_length=3, max_length=50), title: str = Query(min_length=3, max_length=50), topic:str = Query(default="science", description="Print 'science', 'art', 'history' or 'news'"), credentials: OAuth2PasswordRequestForm = Depends(security)):
    topic = topic.lower()
    if credentials[0] == '5':
        return exception(status.HTTP_423_LOCKED, "You are banned on server.")
    elif credentials[0] != '1' and credentials[0] != '3' and credentials[1] != '3':
        return exception(status.HTTP_423_LOCKED, "You aren't administrator or writer.")
    elif topic != "science" and topic != "art" and topic != "history" and topic != "news":
        return exception(status.HTTP_400_BAD_REQUEST, "Print 'science', 'art', 'history' or 'news' in topic field.")
    elif src.functional.field_check(article_name, 0) == 0:
        return exception(status.HTTP_400_BAD_REQUEST, "You can't use apostrophe in article name.")
    elif src.functional.field_check(title, 0) == 0:
        return exception(status.HTTP_400_BAD_REQUEST, "You can't use apostrophe in title.")
    else:
        cursor.execute(f"SELECT * FROM public.article WHERE name='{article_name}'")
        records = list(cursor.fetchall())
        if records != []:
            return exception(status.HTTP_400_BAD_REQUEST, "This article name has already taken.")
        else:
            topic_id = src.functional.get_topic_id(topic)
            user_id = src.functional.get_user_id(credentials)
            path = f".\\articles\\{article_name}.txt"
            time = src.functional.get_current_date()
            cursor.execute(f"INSERT INTO public.article (name, title, description, isdeleted, date) VALUES ('{article_name}', '{title}', '{path}', {False}, '{time}')")
            conn.commit()
            cursor.execute(f"SELECT * FROM public.article WHERE name='{article_name}'")
            records = list(cursor.fetchall())
            cursor.execute(f"INSERT INTO public.article_status (article_id, status_id) VALUES ({records[0][0]}, 1)")
            cursor.execute(f"INSERT INTO public.article_writer (article_id, user_id, isauthor) VALUES ({records[0][0]}, {user_id}, {True})")
            cursor.execute(f"INSERT INTO public.article_topic (article_id, topic_id) VALUES ({records[0][0]}, {topic_id})")
            conn.commit()
            with open(path, "w") as file:
                file.write("")
            return "Article is created."

@app.get("/{article_name}")
def read_article_desc(article_name, credentials: OAuth2PasswordRequestForm = Depends(security)):
    return src.functional.authorization_check_article(credentials, article_name)

@app.post("/{article_name}")
def send_review(article_name, rate: int = Query(ge=1, le=5), review_text: Review = Review(), credentials: OAuth2PasswordRequestForm = Depends(security)):
    return {'rate': rate, 'review_text': review_text.review_text}


@app.get("/create/{article_name}")
def get_article_info(article_name, credentials: OAuth2PasswordRequestForm = Depends(security)):
    article_desc = src.functional.authorization_check_draft(credentials, article_name)
    return article_desc
   
@app.post("/create/{article_name}")
def update_draft(article_name, action: str = Query(default="save", description="Print 'save', 'publish' or 'delete'."),article: Draft = Draft(), credentials: OAuth2PasswordRequestForm = Depends(security)):
    article_desc = src.functional.authorization_check_draft(credentials, article_name)
    path = f".\\articles\\{article_name}.txt"
    cursor.execute(f"SELECT * FROM public.article WHERE name='{article_name}'")
    records=list(cursor.fetchall())
    if action == "delete":
        cursor.execute(f"UPDATE public.article SET isdeleted={True} WHERE name='{article_name}'")
        cursor.execute(f"UPDATE public.article_status SET status_id={5} WHERE article_id={records[0][0]}")
    elif article_desc['article_status'] != 1:
        return {'warning': "You can't update published or deleted article.", 'article_info': article_desc}
    elif action == "save":
        if article.title != "":
            article_desc['title'] = article.title
            cursor.execute(f"UPDATE public.article SET title='{article.title}' WHERE name='{article_name}'")
        if article.article_text != "":
            article_desc['article_text'] = article.article_text
            with open(path, "w") as file:
                file.writelines(article_desc['article_text'])
    elif action == "publish":
        if article.title != "":
            article_desc['title'] = article.title
            cursor.execute(f"UPDATE public.article SET title='{article.title}' WHERE name='{article_name}'")
        if article.article_text != "":
            article_desc['article_text'] = article.article_text
            with open(path, "w") as file:
                file.writelines(article_desc['article_text'])
        article_desc['article_status'] = 2
        cursor.execute(f"UPDATE public.article_status SET status_id={2} WHERE article_id={records[0][0]}")
        cursor.execute(f"UPDATE public.article SET date='{src.functional.get_current_date()}' WHERE name='{article_name}'")  
    else:
        return exception(status.HTTP_400_BAD_REQUEST, "Print 'save', 'publish' or 'delete'. in action field.")
    conn.commit()
    return article_desc