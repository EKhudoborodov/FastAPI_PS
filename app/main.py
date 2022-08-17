import os, psycopg2, uvicorn, src.functional, requests
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
    return src.functional.sign_in_user(form_data)
        
@app.get("/sign_up") # sign up
def sign_up(
                fullname: str,
                username: str = Query(min_length=4, max_length=50),
                password: str = Query(min_length=8, max_length=50),
                confirm_password: str = Query(min_length=8, max_length=50)
           ):
    return src.functional.sign_up_user(fullname, username, password, confirm_password)

@app.get("/sign_in_with_VK")
def VK_sign_in():
    app_id = 81403665
    secret_key = "8JvGjXTibUXRJIv7jumo"
    return None

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
                    action: Action_review, # send, delete
                    rate: int = Query(ge=1, le=5), # 1, 2, 3, 4, 5
                    review_text: Review = Review(), # review_text
                    credentials: OAuth2PasswordRequestForm = Depends(security)
               ):
    return src.functional.send_review(article_name, action, rate, review_text, credentials)

@app.get("/role") # administrator can update user roles here
def update_role(
                    username: str,
                    role: Select_role, # moderator, writer, ban
                    action: Action_role, # add, remove
                    credentials: OAuth2PasswordRequestForm = Depends(security)
                ):
    return src.functional.update_role(username, role, action, credentials)

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
    return src.functional.create_article(topic, article_name, title, credentials)

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
    return src.functional.update_authors(article_name, username, role, action, credentials)

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
    return src.functional.update_draft(article_name, action, article, credentials)

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
def update_article_status(
                            article_name, 
                            action: Published, # aproove, deny
                            reason: str = Query(description="Print reason of rejection here.", default=None),
                            credentials: OAuth2PasswordRequestForm = Depends(security)
                         ):
    return src.functional.update_article_status(article_name, action, reason, credentials)