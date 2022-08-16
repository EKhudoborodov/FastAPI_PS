import os, psycopg2, uvicorn, src.functional
from enum import Enum
from src.classes import Draft, Review, Action_review, Action_role, Select_role, Select_rate, Select_topic, Select_search_field, Action_create, Published, Editors
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

@app.post('/sign_in') # sign in (get token)
async def token(form_data: OAuth2PasswordRequestForm = Depends()):
    cursor.execute(f"SELECT * FROM public.users WHERE login='{form_data.username}' AND password='{form_data.password}'")
    records = list(cursor.fetchall())
    if records == []: # check if there is user in database
        return exception(status.HTTP_401_UNAUTHORIZED, "Incorrect username or password.")
    cursor.execute(f"SELECT * FROM public.role_user WHERE user_id={records[0][0]}")
    user_desc = list(cursor.fetchall())
    token = "" # form user's token
    for desc in user_desc:
        if desc[1] != 5:
            token += f"{desc[1]}"
        else:
            token = 5
            break
    token += " " + form_data.username
    return {'access_token': token}
        
@app.get("/sign_up") # sign up
def sign_up(
                fullname: str,
                username: str = Query(min_length=4, max_length=50),
                password: str = Query(min_length=8, max_length=50),
                confirm_password: str = Query(min_length=8, max_length=50)
           ):
    if src.functional.field_check(username, 1) == 0:
        return exception(status.HTTP_400_BAD_REQUEST, "You can't use space or apostrophe in username.")
    if src.functional.field_check(password, 1) == 0:
        return exception(status.HTTP_400_BAD_REQUEST, "You can't use space or apostrophe in password.")   
    if password != confirm_password:
        return exception(status.HTTP_400_BAD_REQUEST, "Passwords are different.")
    else:
        cursor.execute(f"SELECT * FROM public.users WHERE login='{username}'")
        records = list(cursor.fetchall())
        if records != []: # check if there is no user in database
            return exception(status.HTTP_400_BAD_REQUEST, "This username has already taken.") 
        else:
            cursor.execute(f"INSERT INTO public.users (login, password, fullname, banned) VALUES ('{username}', '{password1}', '{fullname}', {False})")
            conn.commit() # insert user into database
            cursor.execute(f"SELECT * FROM public.users WHERE login='{username}'")
            records = list(cursor.fetchall()) # get user information (user id)
            cursor.execute(f"INSERT INTO public.role_user (user_id, role_id) VALUES ('{records[0][0]}', 4)")
            conn.commit() # give user 'reader' role
            cursor.execute(f"SELECT * FROM public.article_status WHERE status_id={3}")
            article_desc = list(cursor.fetchall()) # get all aprooved articles
            for article in article_desc: # mark all aprooved as 'unread' for the user
                cursor.execute(f"INSERT INTO public.user_read (user_id, article_id, isread) VALUES ({records[0][0]}, {article[0]}, {False})")
            conn.commit()
            return {"username": username, "password": password}

@app.get("/home") # watch list of recently aprooved articles
def home(
            search_value: str = None,
            search_field: Select_search_field = None, # name, author, topic, date
            topic_filter: Select_topic = None, # science, art, history, news
            rate_filter: Select_rate = None, # 1, 2, 3, 4, 5, >2, >3, >4, <2, <3, <4
            views_filter: str = Query(description="Print '>' or '<' at the begining and then number of views.", default = None),
            credentials: OAuth2PasswordRequestForm = Depends(security)
        ):
    home_array = src.functional.select_table_recent(credentials) # get all recently aprooved articles
    return src.functional.search_start(home_array, search_field, search_value, topic_filter, rate_filter, views_filter) # choose articles according to search filters

@app.get("/archive") # watch list of aprooved articles
def archive(
                search_value: str = None,
                search_field: Select_search_field = None, # name, author, topic, date
                topic_filter: Select_topic = None, # science, art, history, news
                rate_filter: Select_rate = None, # 1, 2, 3, 4, 5, >2, >3, >4, <2, <3, <4
                views_filter: str = Query(description="Print '>' or '<' at the begining and then number of views.", default = None),
                credentials: OAuth2PasswordRequestForm = Depends(security)
            ):
    archive_array = src.functional.select_table_desc(credentials)
    return src.functional.search_start(archive_array, search_field, search_value, topic_filter, rate_filter, views_filter) # choose articles according to search filters

@app.get("/archive/{article_name}") # read article
def read_article_desc(article_name, credentials: OAuth2PasswordRequestForm = Depends(security)):
    return src.functional.authorization_check_article(credentials, article_name) # get article info

@app.post("/archive/{article_name}") # send or edit review
def send_review(
                    article_name,
                    action: Action_review,
                    rate: int = Query(ge=1, le=5),
                    review_text: Review = Review(),
                    credentials: OAuth2PasswordRequestForm = Depends(security)
               ):
    article_desc = src.functional.authorization_check_article(credentials, article_name) # get article info
    user_id = src.functional.get_user_id(credentials)
    user_review = article_desc['user_review']
    article_id = article_desc['article_id']
    date = src.functional.get_current_date()
    path = f".\\reviews\\{article_name}.txt"
    if action == "send": # check if user sends review
        if user_review['rating'] != None: # check if user had already written review for the article
            src.functional.update_reviews(article_name, user_id, article_id, review_text.review_text, path) # update user's review
            cursor.execute(f"UPDATE public.rating SET date='{date}', rate={rate}, isdeleted={False} WHERE user_id={user_id} and article_id={article_id}")
        else:
            with open(path, "r") as file: # read file with reviews
                lines = file.readlines()
            file.close()
            lines += f"{user_id}:{review_text.review_text}\n" # append user review
            text = src.functional.form_article(lines)
            with open(path, "w") as file: # update file with reviews
                file.write(text)
            file.close()
            cursor.execute(f"INSERT INTO public.rating (user_id, article_id, date, rate, isdeleted) VALUES ({user_id}, {article_id}, '{date}', {rate}, {False})")
        event = "Review is sent."
    else: # if user wants to delete his review
        if user_review['rating'] == None: # check if user didn't writte review for the article
            return exception(status.HTTP_400_BAD_REQUEST, "You didn't write review for this article.")
        event = "Review is deleted."
        cursor.execute(f"UPDATE public.rating SET isdeleted={True} WHERE user_id={user_id} and article_id={article_id}") # mark user review as deleted
        src.functional.delete_review(article_name, user_id, article_id, path) # remove user's review from file
    conn.commit()
    article_desc = src.functional.authorization_check_article(credentials, article_name) # update article info
    return {'event': event,'article_desc': article_desc}

@app.get("/role") # administrator can update user roles here
def update_role(
                    username: str,
                    role: Select_role,
                    action: Action_role,
                    credentials: OAuth2PasswordRequestForm = Depends(security)
                ):
    if credentials[0] == '5': # check if user is banned
        return exception(status.HTTP_423_LOCKED, "You are banned on server.")
    elif credentials[0] != '1': # check if user is administrator
        return exception(status.HTTP_423_LOCKED, "You aren't administrator.")
    if src.functional.field_check(username, 1) == 0: # check if administrator inputs username without spaces and apostrophes
        return exception(status.HTTP_400_BAD_REQUEST, "You can't use space or apostrophe in username.")
    cursor.execute(f"SELECT * FROM public.users WHERE login='{username}'")
    records = list(cursor.fetchall())
    if records == []: # check if administrator inputs correct username
         return exception(status.HTTP_400_BAD_REQUEST, "There is no such user in database.")
    role_id = src.functional.crypt_role(role)
    user_id = records[0][0]
    if role_id != 5: # check if administrator doesn't choose 'ban' in role field
        if action == 'remove':
            # removing user's role
            cursor.execute(f"DELETE FROM public.role_user WHERE user_id={user_id} and role_id={role_id}")
            conn.commit()
            # checking if user has any other roles
            cursor.execute(f"SELECT * FROM public.role_user WHERE user_id={user_id}")
            records = list(cursor.fetchall())
            # if user has not other roles add Reader role
            if records == []:
                cursor.execute(f"INSERT INTO public.role_user (user_id, role_id) VALUES ({user_id}, 4)")
                conn.commit()
                return "Role is seccessfuly removed."
        else:
            # adding 'reader' role to user
            cursor.execute(f"INSERT INTO public.role_user (user_id, role_id) VALUES ({user_id}, {role_id})")
            cursor.execute(f"DELETE FROM public.role_user WHERE user_id={user_id} and role_id={4}")
            conn.commit()
            return "Role is seccessfuly added."
    else: # if administrator chooses 'ban' in role field
        # if administrator wants to ban user or remove user from ban list
        if action == 'remove':
            # giving user 'reader' role back
            cursor.execute(f"UPDATE public.role_user SET role_id=4 WHERE user_id={user_id} and role_id={role_id}")
            cursor.execute(f"UPDATE public.users SET banned={False} WHERE id={user_id}")
            conn.commit()
            return f"{username} is removed from banlist."
        else:
            # sending user into banlist
            cursor.execute(f"UPDATE public.role_user SET role_id={role_id} WHERE user_id={user_id}")
            cursor.execute(f"UPDATE public.users SET banned={True} WHERE id={user_id}")
            conn.commit()
            return f"{username} is banned now."

@app.get("/workshop") # get list of articles where user is author or redactor
def workshop(
                search_value: str = None,
                search_field: Select_search_field = None, # name, author, topic, date
                topic_filter: Select_topic = None, # science, art, history, news
                rate_filter: Select_rate = None, # 1, 2, 3, 4, 5, >2, >3, >4, <2, <3, <4
                views_filter: str = Query(description="Print '>' or '<' at the begining and then number of views.", default = None),
                credentials: OAuth2PasswordRequestForm = Depends(security)
            ):
    workshop_array = src.functional.select_table_personal(credentials) # get list of all user's artiles
    return src.functional.search_start(workshop_array, search_field, search_value, topic_filter, rate_filter, views_filter) # choose articles according to search filters

@app.get("/create") # create new article
def create(
                topic: Select_topic, # science, art, history, news
                article_name: str = Query(min_length=3, max_length=50), 
                title: str = Query(min_length=3, max_length=50),
                credentials: OAuth2PasswordRequestForm = Depends(security)
          ):
    topic = topic.lower()
    if credentials[0] == '5': # check if user is banned
        return exception(status.HTTP_423_LOCKED, "You are banned on server.")
    elif credentials[0] != '1' and credentials[0] != '3' and credentials[1] != '3': # check if user is administrator or writer
        return exception(status.HTTP_423_LOCKED, "You aren't administrator or writer.")
    elif src.functional.field_check(article_name, 0) == 0: # check if user inputs article name without apostrophe
        return exception(status.HTTP_400_BAD_REQUEST, "You can't use apostrophe in article name.")
    elif src.functional.field_check(title, 0) == 0: # check if user inputs title without apostrophe
        return exception(status.HTTP_400_BAD_REQUEST, "You can't use apostrophe in title.")
    else:
        cursor.execute(f"SELECT * FROM public.article WHERE name='{article_name}'")
        records = list(cursor.fetchall())
        if records != []: # check if there isn't article in database
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
            with open(path, "w") as file: # create file for this article
                file.write("")
            file.close()
            return "Article is created."

@app.get("/editors/{article_name}") # get list of article authors and redactors (for article's author)
def editors_menu(article_name, credentials: OAuth2PasswordRequestForm = Depends(security)):
    return src.functional.authorization_editors_check(article_name, credentials) # get authors info

@app.post("/editors/{article_name}") # add or remove authors and redactors of your article
def editors_update(
                    article_name, 
                    username: str,
                    role: Editors, # redactor, author
                    action: Action_role, # add, remove
                    credentials: OAuth2PasswordRequestForm = Depends(security)
                ):
    author_desc = src.functional.authorization_editors_check(article_name, credentials) # get authors info
    cursor.execute(f"SELECT * FROM public.users WHERE login='{username}'")
    records = list(cursor.fetchall())
    if records == []: # check if username was inputed right
        return exception(status.HTTP_400_BAD_REQUEST, "There is no such user in database.")
    user_id = records[0][0]
    if action == "add":
        if role == "redactor":
            if username in author_desc['authors']: # if user is author of article he will become a redactor
                cursor.execute(f"UPDATE public.article_writer SET isauthor={False} WHERE article_id={author_desc['article_id']} and user_id={user_id}")
            else: # insert user as redactor if he isn't redactor or author of article
                cursor.execute(f"INSERT INTO public.article_writer (article_id, user_id, isauthor) VALUES ({author_desc['article_id']}, {user_id}, {False})")
            event=f"{username} is now redactor of this article."
        else:
            if username in author_desc['authors']: # if user is redactor of article he will become an author
                cursor.execute(f"UPDATE public.article_writer SET isauthor={True} WHERE article_id={author_desc['article_id']} and user_id={user_id}")
            else: # insert user as author if he isn't redactor or author of article
                cursor.execute(f"INSERT INTO public.article_writer (article_id, user_id, isauthor) VALUES ({author_desc['article_id']}, {user_id}, {True})")
            event=f"{username} is now author of this article."
    elif action == "remove":
        if not username in author_desc['authors']: # check if username was inputed correct
            return exception(status.HTTP_400_BAD_REQUEST, "This user isn't a redactor of this article.")
        else:
            if role == "redactor": # if user is removed from redactors he will lose rights to update article
                event=f"{username} isn't redactor of this article anymore."
                cursor.execute(f"DELETE FROM public.article_writer WHERE article_id={author_desc['article_id']} and user_id={user_id}")
            else: # if user is removed from authors he will become a redactor
                event=f"{username} is now redactor of this article."
                cursor.execute(f"UPDATE public.article_writer SET isauthor={False} WHERE article_id={author_desc['article_id']} and user_id={user_id}")
    conn.commit()
    author_desc = src.functional.authorization_editors_check(article_name, credentials) # update authors info
    return {'event': event, 'author_desc': author_desc}

@app.get("/create/{article_name}")
def get_article_info(article_name, credentials: OAuth2PasswordRequestForm = Depends(security)):
    return src.functional.authorization_check_draft(credentials, article_name) # get article info 
   
@app.post("/create/{article_name}")
def update_draft(
                    article_name, 
                    action: Action_create, # delete, save, publish, back_to_draft
                    article: Draft, # hashtag, title, article text
                    credentials: OAuth2PasswordRequestForm = Depends(security)
                ):
    article_desc = src.functional.authorization_check_draft(credentials, article_name) # get article info
    path = f".\\articles\\{article_name}.txt"
    cursor.execute(f"SELECT * FROM public.article WHERE name='{article_name}'")
    records=list(cursor.fetchall())
    user_id = src.functional.get_user_id(credentials)
    author_check = src.functional.is_author(records[0][0], user_id)
    if action == "delete" and author_check == 1: # check if user wants to delete article
        cursor.execute(f"UPDATE public.article SET isdeleted={True} WHERE name='{article_name}'")
        cursor.execute(f"UPDATE public.article_status SET status_id={5} WHERE article_id={records[0][0]}")
    elif article_desc['article_status'] != 1: # check if article has 'draft' status
        if action == "back_to_draft" and author_check == 1: # check if user wants to send article to draft
            cursor.execute(f"UPDATE public.article SET isdeleted={False} WHERE id={article_desc['article_id']}")
            cursor.execute(f"UPDATE public.article_status SET status_id={1} WHERE article_id={article_desc['article_id']}")
            cursor.execute(f"DELETE FROM public.user_read WHERE article_id={article_desc['article_id']}")
            cursor.execute(f"DELETE FROM public.rating WHERE article_id={article_desc['article_id']}")
            path = f".\\reviews\\{article_name}.txt"
            with open(path, "w") as file:
                file.write("")
            file.close()
            article_desc['article_status'] = 1
            conn.commit()
            return {'event': "Article is draft now.", 'article_info': article_desc}
        else:
            return {'warning': "You can't update published or deleted article.", 'article_info': article_desc}
    elif action == "save": # 'save' is available for redactors
        if article.title != "": # update if 'title' field isn't empty
            article_desc['title'] = article.title
            cursor.execute(f"UPDATE public.article SET title='{article.title}' WHERE name='{article_name}'")
        if article.article_text != "": # update if 'article_text' field isn't empty
            article_desc['article_text'] = article.article_text
            with open(path, "w") as file:
                file.writelines(article_desc['article_text'])
            file.close()
        if article.hashtag != "":
            src.functional.hashtag_add(article_desc['article_id'], article.hashtag)
    elif action == "publish" and author_check == 1:
        if article.title != "": # update if 'title' field isn't empty
            article_desc['title'] = article.title
            cursor.execute(f"UPDATE public.article SET title='{article.title}' WHERE name='{article_name}'")
        if article.article_text != "": # update if 'article_text' field isn't empty
            article_desc['article_text'] = article.article_text
            with open(path, "w") as file:
                file.writelines(article_desc['article_text'])
            file.close()
        if article.hashtag != "":
            src.functional.hashtag_add(article_desc['article_id'], article.hashtag)
        article_desc['article_status'] = 2
        cursor.execute(f"UPDATE public.article_status SET status_id={2} WHERE article_id={records[0][0]}")
        cursor.execute(f"UPDATE public.article SET date='{src.functional.get_current_date()}' WHERE name='{article_name}'")
    elif action == "back_to_draft":
        return exception(status.HTTP_400_BAD_REQUEST, "Article is draft already.")
    else: # if redactor tries do something exept 'save'
        return exception(status.HTTP_423_LOCKED, "You aren't an author of this article.")
    conn.commit()
    return article_desc

@app.get("/published") # get list of articles with 'published' status 
def published(
                search_value: str = None,
                search_field: Select_search_field = None, # name, author, topic, date
                topic_filter: Select_topic = None, # science, art, history, news
                rate_filter: Select_rate = None, # 1, 2, 3, 4, 5, >2, >3, >4, <2, <3, <4
                views_filter: str = Query(description="Print '>' or '<' at the begining and then number of views.", default = None),
                credentials: OAuth2PasswordRequestForm = Depends(security)
             ):
    published_array = src.functional.select_table_published(credentials) # get all articles with 'published' status
    return src.functional.search_start(published_array, search_field, search_value, topic_filter, rate_filter, views_filter) # choose articles according to search filters

@app.get("/published/{article_name}") # read article with 'published' status
def get_published_article(article_name, credentials: OAuth2PasswordRequestForm = Depends(security)):
    return src.functional.authorization_check_published(article_name, credentials) # get article info

@app.post("/published/{article_name}") # aproove or deny article with 'published' status
def get_published_article(
                            article_name, 
                            action: Published, # aproove, deny
                            reason: str = Query(description="Print reason of rejection here.", default=None),
                            credentials: OAuth2PasswordRequestForm = Depends(security)
                         ):
    article_desc = src.functional.authorization_check_published(article_name, credentials) # get article info
    if action == "aproove":
        date = src.functional.get_current_date()
        cursor.execute(f"UPDATE public.article_status SET status_id={3} WHERE article_id={article_desc['article_id']}")
        cursor.execute(f"UPDATE public.article SET date='{date}' WHERE id={article_desc['article_id']}")
        src.functional.form_read_columns(article_desc['article_id'])
        with open(f".\\reviews\\{article_name}.txt", "w") as file:
            file.write("")
        file.close()
        article_desc['article_status'] = 3
        article_desc['date'] = date
        conn.commit()
        return {'event': "Article is aprooved.", 'article_desc': article_desc}
    else:
        if reason == None or reason == "":
            return exception(status.HTTP_400_BAD_REQUEST, "You must enter reason of rejection.")
        date = src.functional.get_current_date()
        cursor.execute(f"UPDATE public.article_status SET status_id={4} WHERE article_id={article_id}")
        cursor.execute(f"UPDATE public.article SET description='{reason}', isdeleted={True}, date='{date}' WHERE id={article_id}")
        conn.commit()
        article_desc['article_status'] = 4
        article_desc['date'] = date
        return {'event': f"Article is denied. Reason: {reason}", 'article_desc': article_desc}


    
