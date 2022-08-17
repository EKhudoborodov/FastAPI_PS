import psycopg2, cv2, datetime
from fastapi import status, HTTPException
from src.exceptions import exception

conn = psycopg2.connect(database="server_db",
                        user="postgres",
                        password="postgres",
                        host="localhost",
                        port="5432")

cursor = conn.cursor()

"""
#FOR SIGN IN AND SIGN UP
def stop_sessions():
    flask.session['user'] = None # session for user_id
    flask.session['fullname'] = None # session for user's fullname
    flask.session['role'] = None # session for user's roles
    flask.session['ban'] = None # session for user's ban status
    flask.session['article'] = None # session for name of latest openned article
    flask.session['article_id'] = None # session for id of latest openned article
    flask.session['title'] = None # session for title of latest oppend article
    return 0
"""

def crypt_role(role):
    cursor.execute(f"SELECT * FROM public.role WHERE name='{role}'")
    records = list(cursor.fetchall())
    return records[0][0]

#AUTHORIZATION
def sign_in_user(form_data):
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

def sign_up_user(fullname, username, password, confirm_password):
    if field_check(username, 1) == 0:
        return exception(status.HTTP_400_BAD_REQUEST, "You can't use space or apostrophe in username.")
    if field_check(password, 1) == 0:
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

#REVIEWS
def send_review(article_name, action, rate, review_text, credentials):
    article_desc = authorization_check_article(credentials, article_name) # get article info
    user_id = get_user_id(credentials)
    user_review = article_desc['user_review']
    article_id = article_desc['article_id']
    date = get_current_date()
    path = f".\\reviews\\{article_name}.txt"
    if action == "send": # check if user sends review
        if user_review['rating'] != None: # check if user had already written review for the article
            update_reviews(article_name, user_id, article_id, review_text.review_text, path) # update user's review
            cursor.execute(f"UPDATE public.rating SET date='{date}', rate={rate}, isdeleted={False} WHERE user_id={user_id} and article_id={article_id}")
        else:
            with open(path, "r") as file: # read file with reviews
                lines = file.readlines()
            file.close()
            lines += f"{user_id}:{review_text.review_text}\n" # append user review
            text = form_article(lines)
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
        delete_review(article_name, user_id, article_id, path) # remove user's review from file
    conn.commit()
    article_desc = authorization_check_article(credentials, article_name) # update article info
    return {'event': event,'article_desc': article_desc}

def update_reviews(article_name, user_id, article_id, review, path):
    with open(path, "r") as file:
        lines = file.readlines()
    file.close()
    new_lines = []
    formed_id = str(user_id)
    for line in lines:
        wrong = 1
        for i in range(len(formed_id)):
            if line[i] == formed_id[i]:
                wrong = 0
            else:
                wrong = 1
                break
        if wrong == 0:
            new_lines += f"{user_id}:{review}\n"
        else:
            new_lines += line
    text = form_article(new_lines)
    with open(path, "w") as file:
        file.write(text)
    file.close()
    return 0

def delete_review(article_name, user_id, article_id, path):
    with open(path, "r") as file:
        lines = file.readlines()
    file.close()
    new_lines = [""]
    formed_id = str(user_id)
    for line in lines:
        wrong = 1
        for i in range(len(formed_id)):
            if line[i] == formed_id[i]:
                wrong = 0
            else:
                wrong = 1
                break
        if wrong == 0:
            continue
        else:
            new_lines += line
    text = form_article(new_lines)
    with open(path, "w") as file:
        file.write(text)
    file.close()
    return 0

#SETTINGS FOR ADMINISTRATOR
def update_role(username, role, action, credentials):
    if credentials[0] == '5': # check if user is banned
        return exception(status.HTTP_423_LOCKED, "You are banned on server.")
    elif credentials[0] != '1': # check if user is administrator
        return exception(status.HTTP_423_LOCKED, "You aren't administrator.")
    if field_check(username, 1) == 0: # check if administrator inputs username without spaces and apostrophes
        return exception(status.HTTP_400_BAD_REQUEST, "You can't use space or apostrophe in username.")
    cursor.execute(f"SELECT * FROM public.users WHERE login='{username}'")
    records = list(cursor.fetchall())
    if records == []: # check if administrator inputs correct username
         return exception(status.HTTP_400_BAD_REQUEST, "There is no such user in database.")
    role_id = crypt_role(role)
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

#ARTICLE EDITS FOR WRITERS
def create_article(topic, article_name, title, credentials):
    if credentials[0] == '5': # check if user is banned
        return exception(status.HTTP_423_LOCKED, "You are banned on server.")
    elif credentials[0] != '1' and credentials[0] != '3' and credentials[1] != '3': # check if user is administrator or writer
        return exception(status.HTTP_423_LOCKED, "You aren't administrator or writer.")
    elif field_check(article_name, 0) == 0: # check if user inputs article name without apostrophe
        return exception(status.HTTP_400_BAD_REQUEST, "You can't use apostrophe in article name.")
    elif field_check(title, 0) == 0: # check if user inputs title without apostrophe
        return exception(status.HTTP_400_BAD_REQUEST, "You can't use apostrophe in title.")
    else:
        cursor.execute(f"SELECT * FROM public.article WHERE name='{article_name}'")
        records = list(cursor.fetchall())
        if records != []: # check if there isn't article in database
            return exception(status.HTTP_400_BAD_REQUEST, "This article name has already taken.")
        else:
            topic_id = get_topic_id(topic)
            user_id = get_user_id(credentials)
            path = f".\\articles\\{article_name}.txt"
            time = get_current_date()
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

def update_authors(article_name, username, role, action, credentials):
    author_desc = authorization_editors_check(article_name, credentials) # get authors info
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
    author_desc = authorization_editors_check(article_name, credentials) # update authors info
    return {'event': event, 'author_desc': author_desc}

def update_draft(article_name, action, article, credentials):
    article_desc = authorization_check_draft(credentials, article_name) # get article info
    path = f".\\articles\\{article_name}.txt"
    cursor.execute(f"SELECT * FROM public.article WHERE name='{article_name}'")
    records=list(cursor.fetchall())
    user_id = get_user_id(credentials)
    author_check = is_author(records[0][0], user_id)
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
            hashtag_add(article_desc['article_id'], article.hashtag)
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
            hashtag_add(article_desc['article_id'], article.hashtag)
        article_desc['article_status'] = 2
        cursor.execute(f"UPDATE public.article_status SET status_id={2} WHERE article_id={records[0][0]}")
        cursor.execute(f"UPDATE public.article SET date='{get_current_date()}' WHERE name='{article_name}'")
    elif action == "back_to_draft":
        return exception(status.HTTP_400_BAD_REQUEST, "Article is draft already.")
    else: # if redactor tries do something exept 'save'
        return exception(status.HTTP_423_LOCKED, "You aren't an author of this article.")
    conn.commit()
    return article_desc

#PUBLISHED FOR MODERATORS
def update_article_status(article_name, action, reason, credentials):
    article_desc = authorization_check_published(article_name, credentials) # get article info
    if action == "aproove":
        date = get_current_date()
        cursor.execute(f"UPDATE public.article_status SET status_id={3} WHERE article_id={article_desc['article_id']}")
        cursor.execute(f"UPDATE public.article SET date='{date}' WHERE id={article_desc['article_id']}")
        form_read_columns(article_desc['article_id'])
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
        date = get_current_date()
        cursor.execute(f"UPDATE public.article_status SET status_id={4} WHERE article_id={article_id}")
        cursor.execute(f"UPDATE public.article SET description='{reason}', isdeleted={True}, date='{date}' WHERE id={article_id}")
        conn.commit()
        article_desc['article_status'] = 4
        article_desc['date'] = date
        return {'event': f"Article is denied. Reason: {reason}", 'article_desc': article_desc}

#CHECK
def field_check(field, space_check):
    for char in field:
        if char == "'" or (char == " " and space_check == 1):
            return 0
    return 1

def authorization_editors_check(article_name, credentials):
    if credentials[0] == '5': # check if user is banned
        return exception(status.HTTP_423_LOCKED, "You are banned on server.")
    user_id = get_user_id(credentials)
    cursor.execute(f"SELECT * FROM public.article WHERE name='{article_name}'")
    article_desc = list(cursor.fetchall())
    if article_desc == []:
        return exception(status.HTTP_404_NOT_FOUND, "There is no such article in database.")
    article_id = article_desc[0][0]
    cursor.execute(f"SELECT * FROM public.article_writer WHERE user_id={user_id} and article_id={article_id}")
    records = list(cursor.fetchall())
    if credentials[0] != '1' and records[0][2] != True:
        return exception(status.HTTP_423_LOCKED, "You aren't administrator or author of this article.")
    cursor.execute(f"SELECT * FROM public.article_status WHERE article_id={article_id}")
    check = list(cursor.fetchall())
    if check[0][1] != 1:
        return exception(status.HTTP_400_BAD_REQUEST, "This article isn't draft.")
    authors=get_authors_username(article_id)
    return {'article_id': article_id, 'authors': authors}

def authorization_check_published(article_name, credentials):
    if credentials[0] == '5': # check if user is banned
        return exception(status.HTTP_423_LOCKED, "You are banned on server.")
    elif credentials[0] != '1' and credentials[0] != '2' and credentials[1] != '2':
        return exception(status.HTTP_423_LOCKED, "You aren't administrator or moderator.")
    cursor.execute(f"SELECT * FROM public.article WHERE name='{article_name}' and isdeleted = {False}")
    records = list(cursor.fetchall())
    if records == []:
        return exception(status.HTTP_404_NOT_FOUND, "There is no such article in database.")
    else:
        article_id = records[0][0]
        title = records[0][2]
        date = records[0][5]
        cursor.execute(f"SELECT * FROM public.article_status WHERE article_id={article_id} and status_id={2}")
        check = list(cursor.fetchall())
        if check == []:
            return exception(status.HTTP_400_BAD_REQUEST, "This article isn't published.")
        user_id = get_user_id(credentials)
        path = f".\\articles\\{article_name}.txt"
        text = form_text(path)
        hashtags = get_hashtags(article_id)
        return {'user_id': user_id, 'article_id': article_id, 'hashtags': hashtags, 'title': title, 'article_text': text, 'article_status': 2, 'date': date}

def authorization_check_draft(credentials, article):
    if credentials[0] == '5':
        return exception(status.HTTP_423_LOCKED, "You are banned on server.")
    elif credentials[0] != '1' and credentials[0] != '3' and credentials[1] != '3':
        return exception(status.HTTP_423_LOCKED, "You aren't administrator or writer.")
    else:
        cursor.execute(f"SELECT * FROM public.article WHERE name='{article}'")
        records = list(cursor.fetchall())
        if records == []:
            return exception(status.HTTP_404_NOT_FOUND, "There is no such article in database.")
        article_id = records[0][0]
        title = records[0][2]
        reason = records[0][3]
        date = records[0][5]
        user_id=get_user_id(credentials)
        cursor.execute(f"SELECT * FROM public.article_writer WHERE article_id={records[0][0]} and user_id={user_id}")
        recs = list(cursor.fetchall())
        if recs == []:
            return exception(status.HTTP_423_LOCKED, "You aren't author or redactor of this article.")
        author = is_author(records[0][0], user_id)
        path = f".\\articles\\{article}.txt"
        text = form_text(path)
        cursor.execute(f"SELECT * FROM public.article_status WHERE article_id={records[0][0]}")
        records = list(cursor.fetchall())
        hashtags = get_hashtags(records[0][0])
        return {'user_id': user_id, 'article_id': article_id, 'hashtags': hashtags, 'title': title, 'article_text': text, 'article_status': records[0][1], 'date': date}
        
def authorization_check_article(credentials, article_name):
    if credentials[0] == '5':
        return exception(status.HTTP_423_LOCKED, "You are banned on server.")
    if field_check(article_name, 0) == 0:
        return exception(status.HTTP_404_NOT_FOUND, "There is no such article in database.")
    cursor.execute(f"SELECT * FROM public.article WHERE name='{article_name}' and isdeleted = {False}")
    records = list(cursor.fetchall())
    if records == []:
        return exception(status.HTTP_404_NOT_FOUND, "There is no such article in database.")       
    user_id = get_user_id(credentials)
    article_id = records[0][0]
    cursor.execute(f"SELECT * FROM public.article_status WHERE article_id={article_id}")
    check = list(cursor.fetchall())
    status_id = check[0][1]
    #checking if article is aprooved.
    if status_id != 3:
        cursor.execute(f"SELECT * FROM public.article_writer WHERE article_id={article_id} and user_id={user_id}")
        check = list(cursor.fetchall())
        if check == []:
            return exception(status.HTTP_400_BAD_REQUEST, "This article isn't aprooved.")
        else:
            title = records[0][2]
            path = f".\\articles\\{article_name}.txt"
            text = form_text(path)
            article_status = get_article_status(status_id)
            {'name': article_name, 'status': article_status, 'title': title, 'article_text': article_text}
    else:
        hashtags = get_hashtags(article_id)
        title = records[0][2]
        path = f".\\articles\\{article_name}.txt"
        text = form_text(path)
        topic = get_topic(article_id)
        rate = get_rating(article_id)
        user_review=review_check(user_id, article_id, article_name)
        reviews = select_reviews(credentials, article_id)
        article_status = get_article_status(status_id)
        cursor.execute(f"UPDATE public.user_read SET isread={True} WHERE user_id={user_id} and article_id={article_id} and isread={False}")
        conn.commit()
        return {'article_id': article_id, 'name': article_name, 'status': article_status, 'topic': topic, 'hashtags': hashtags, 'rating': rate, 'title': title, 'article_text': text, 'user_review': user_review, 'reviews': reviews}
            
"""
def check_writer_uploads():
    cursor.execute(f"SELECT * FROM public.article_status WHERE status_id=2")
    records = list(cursor.fetchall())
    res = 0
    for i in records:
        res+=1
    return res
"""

def review_check(user_id, article_id, article_name): # check if user has already sent his review earlier
    cursor.execute(f"SELECT * FROM public.rating WHERE user_id={user_id} and article_id={article_id} and isdeleted={False}")
    records = list(cursor.fetchall())
    rate = None
    review = None
    date = None
    if records != []:
        rate = records[0][4]
        date = records[0][3]
        path = f".\\reviews\\{article_name}.txt"
        with open(path, "r") as text_file:
            lines = text_file.readlines()
        text_file.close()
        formed_id = str(user_id)
        for line in lines:
            wrong = 1
            for i in range(len(formed_id)):
                if line[i] == formed_id[i]:
                    wrong = 0
                else:
                    wrong = 1
                    break
            if wrong == 0:
                review = line[len(formed_id)+1:]
                break
    return {'rating': rate, 'review': review, 'date': date}

def is_author(article_id, user_id): # check if user is author of article
    cursor.execute(f"SELECT * FROM public.article_writer WHERE article_id='{article_id}' and user_id='{user_id}'")
    records = list(cursor.fetchall())
    if records[0][2] == True:
        return 1
    else:
        return 0

def search_input_check(search_field, topic, rate, views): # check all search filter inputs
    if topic != None and topic != 'science' and topic != 'art' and topic != 'history' and topic != 'news':
        return exception(status.HTTP_400_BAD_REQUEST, "Print 'science', 'art', 'history' or 'news'. in topic filter field.")
    if search_field != None and search_field != 'name' and search_field != 'author' and search_field != 'topic' and search_field != 'date' and search_field != 'hashtags':
        return exception(status.HTTP_400_BAD_REQUEST, "Print 'name', 'author', 'topic' or 'date' in search field.")
    if rate != None and rate != '1' and rate != '2' and rate != '3' and rate != '4' and rate != '5' and rate != '>1' and rate != '>2' and rate != '>3' and rate != '>4' and rate != '>5' and rate != '<1' and rate != '<2' and rate != '<3' and rate != '<4' and rate != '<5':
        return exception(status.HTTP_400_BAD_REQUEST, "Print number from 1 to 5. Additional: Print '>' or '<' at the beggining in rate filter field.")
    if views != None and views[0] != '<' and views[0] != '>' and not views[1:].isdigit():
        return exception(status.HTTP_400_BAD_REQUEST, "Print '>' or '<' at the begining and then number of views in views filter field.")

"""
def workshop_check(user_id, roles, no_article):
    new_publish = f"({check_writer_uploads()})"
    ban = flask.session.get('ban')
    cursor.execute(f"SELECT * FROM public.article_writer WHERE user_id={user_id}")
    records = list(cursor.fetchall())
    if records == []:
        return flask.render_template('workshop.html', a = roles[0], m = roles[1], w = roles[2], new_publish=new_publish)
    else:
        first, second, third = None, None, None
        for i in range (len(records)-1, -1, -1):
            article_id = records[i][0]
            cursor.execute(f"SELECT * FROM public.article WHERE id={article_id}")
            recs = list(cursor.fetchall())
            if recs != []:
                if i == len(records)-1:
                    first = recs[0][1]
                elif i == len(records)-2:
                    second = recs[0][1]
                elif i == len(records)-3:
                    third = recs[0][1]
                else: 
                    break
            else:
                break
        return flask.render_template('workshop.html', ban=ban, a=roles[0], m=roles[1], w=roles[2], new_publish=new_publish, no_article=no_article)
"""


#FORM
def form_text(path): # function that reads file with article text and then puts it in one str
    check = 1
    with open(path, "r") as text_file:
        lines = text_file.readlines()
    text_file.close()
    return form_article(lines)

def form_article(lines): # function that puts article text in one str
    if lines == []:
        return None
    else:
        check = 1
        new_lines = ""
        for line in lines:
            if line != "\n" or check == 1:
                new_lines += line
                check = 0
            else:
                check = 1
        #print(new_lines)
        return new_lines

def form_read_columns(article_id): # function that makes read event for article for each user
    cursor.execute(f"SELECT * FROM public.users")
    records = list(cursor.fetchall())
    for rec in records:
        cursor.execute(f"INSERT INTO public.user_read (user_id, article_id, isread) VALUES ({rec[0]}, {article_id}, {False})")
    conn.commit()
    return 0

def sort_articles(array):  # function that sorts list of articles by topic
    science_array, art_array, history_array, news_array = [], [], [], []
    for record in array: # record is {'name': name, 'author': authors, 'topic': topic, 'hashtags': hashtags, 'views': views, 'reviews': reviews, 'date': date}
        if record['topic'] == "science":
            science_array += {'name': record['name'], 'author': record['author'], 'topic': record['topic'], 'hashtags': record['hashtags'], 'views': record['views'], 'reviews': record['reviews'], 'date': record['date']},
        elif record['topic'] == "art":
            art_array += {'name': record['name'], 'author': record['author'], 'topic': record['topic'], 'hashtags': record['hashtags'], 'views': record['views'], 'reviews': record['reviews'], 'date': record['date']},
        elif record['topic'] == "history":
            history_array += {'name': record['name'], 'author': record['author'], 'topic': record['topic'], 'hashtags': record['hashtags'], 'views': record['views'], 'reviews': record['reviews'], 'date': record['date']},
        elif record['topic'] == "news":
            news_array += {'name': record['name'], 'author': record['author'], 'topic': record['topic'], 'hashtags': record['hashtags'], 'views': record['views'], 'reviews': record['reviews'], 'date': record['date']},
    if science_array == []:
        science_array = None
    if art_array == []:
        art_array = None
    if history_array == []:
        history_array = None
    if news_array == []:
        news_array = None
    return {'science': science_array, 'art': art_array, 'history': history_array, 'news': news_array}

def search_by_name(array, field, value): # choose articles that contain value in name, authors, topic or date.
    search_res = []
    if field == None:
        for record in array: # record is {'name': name, 'author': authors, 'topic': topic, 'hashtags': hashtags, 'views': views, 'reviews': reviews, 'date': date}
            if value in record['name'] or value in record['author'] or value in record['topic'] or value in record['date'] or value in record['hashtags']:
                search_res += {'name': record['name'], 'author': record['author'], 'topic': record['topic'], 'hashtags': record['hashtags'], 'views': record['views'], 'reviews': record['reviews'], 'date': record['date']},
        return sort_articles(search_res)
    else:
        for record in array: # record is {'name': name, 'author': authors, 'topic': topic, 'hashtags': hashtags, 'views': views, 'reviews': reviews, 'date': date}
            if value in record[f"{field}"]:
                search_res += {'name': record['name'], 'author': record['author'], 'topic': record['topic'], 'hashtags': record['hashtags'], 'views': record['views'], 'reviews': record['reviews'], 'date': record['date']},
        return sort_articles(search_res)

def search_by_rate(array, rate_filter):
    search_res = []
    if rate_filter == None:
        return array
    if rate_filter[0].isdigit():
        rate = int(rate_filter)
        for record in array: # record is {'name': name, 'author': authors, 'topic': topic, 'hashtags': hashtags, 'views': views, 'reviews': reviews, 'date': date}
            if record['reviews'] >= rate and record['reviews'] < rate+1:
                search_res += {'name': record['name'], 'author': record['author'], 'topic': record['topic'], 'hashtags': record['hashtags'], 'views': record['views'], 'reviews': record['reviews'], 'date': record['date']},
        return search_res
    else:
        rate = int(rate_filter[1])
        if rate_filter[0] == '>':
            for record in array: # record is {'name': name, 'author': authors, 'topic': topic, 'hashtags': hashtags, 'views': views, 'reviews': reviews, 'date': date}
                if record['reviews'] >= rate:
                    search_res += {'name': record['name'], 'author': record['author'], 'topic': record['topic'], 'hashtags': record['hashtags'], 'views': record['views'], 'reviews': record['reviews'], 'date': record['date']},
            return search_res
        elif rate_filter[0] == '<':
            for record in array: # record is {'name': name, 'author': authors, 'topic': topic, 'hashtags': hashtags, 'views': views, 'reviews': reviews, 'date': date}
                if record['reviews'] <= rate:
                    search_res += {'name': record['name'], 'author': record['author'], 'topic': record['topic'], 'hashtags': record['hashtags'], 'views': record['views'], 'reviews': record['reviews'], 'date': record['date']},
            return search_res

def search_by_views(array, views_filter):
    search_res = []
    if views_filter == None:
        return array
    views = int(views_filter[1:])
    if views_filter[0] == '>':
        for record in array: # record is {'name': name, 'author': authors, 'topic': topic, 'hashtags': hashtags, 'views': views, 'reviews': reviews, 'date': date}
            if record['views'] >= views:
                search_res += {'name': record['name'], 'author': record['author'], 'topic': record['topic'], 'hashtags': record['hashtags'], 'views': record['views'], 'reviews': record['reviews'], 'date': record['date']},
        return search_res
    else:
        for record in array: # record is {'name': name, 'author': authors, 'topic': topic, 'hashtags': hashtags, 'views': views, 'reviews': reviews, 'date': date}
            if record['views'] <= views:
                search_res += {'name': record['name'], 'author': record['author'], 'topic': record['topic'], 'hashtags': record['hashtags'], 'views': record['views'], 'reviews': record['reviews'], 'date': record['date']},
        return search_res

def search_start(array, search_field, search_value, topic_filter, rate_filter, views_filter): # function for searching articles
    search_input_check(search_field, topic_filter, rate_filter, views_filter) # check if every input is fine
    array = search_by_rate(array, rate_filter) # update article list with rate filter
    array = search_by_views(array, views_filter) # update article list with views filter
    if topic_filter == None:
        if search_value == None:
            return sort_articles(array)
        return search_by_name(array, search_field, search_value)
    else:
        if search_value == None:
            array = sort_articles(array)
            return {f"{topic_filter}": array[f"{topic_filter}"]}
        array = search_by_name(array, search_field, search_value)
        return {f"{topic_filter}": array[f"{topic_filter}"]}

def hashtag_add(article_id, hashtag):
    cursor.execute(f"DELETE FROM public.article_hashtag WHERE article_id={article_id}")
    conn.commit()
    start = 0
    new_tag = ""
    for i in range(len(hashtag)):
        if hashtag[i] == '#':
            if start == i:
                continue
            elif start == i+1:
                return exception(status.HTTP_400_BAD_REQUEST, "There are two '#' follow each other.")
            else:
                if new_tag == "_":
                    conn.comit()
                    return 0
                cursor.execute(f"SELECT * FROM public.article_hashtag WHERE article_id={article_id} and hashtag='{new_tag}'")
                records = list(cursor.fetchall())
                if records == []:
                    cursor.execute(f"INSERT INTO public.article_hashtag (article_id, hashtag) VALUES ({article_id}, '{new_tag}')")
                start = i
                new_tag = ""
        elif hashtag[i] == "'":
            return exception(status.HTTP_400_BAD_REQUEST, "Hashtag field can't contain apostrophe.")
        elif hashtag[i] == ' ':
            new_tag += '_'
        else:
            new_tag += hashtag[i]
    if new_tag == "_":
        conn.comit()
        return 0
    elif new_tag != "":
        cursor.execute(f"SELECT * FROM public.article_hashtag WHERE article_id={article_id} and hashtag='{new_tag}'")
        records = list(cursor.fetchall())
        if records == []:
            cursor.execute(f"INSERT INTO public.article_hashtag (article_id, hashtag) VALUES ({article_id}, '{new_tag}')")
    conn.commit()
    return 0

"""
def form_reviews(article_id):
    res = ""
    cursor.execute(f"SELECT * FROM public.rating WHERE article_id={article_id} and isdeleted={False}")
    rating = list(cursor.fetchall())
    if rating == []:
        return None
    else:
        for i in (len(rating)-1, 0, -1):
            cursor.execute(f"SELECT * FROM public.users WHERE id={rating[i][1]} and isbanned={False}")
            records = list(cursor.fetchall())
            username = records[0][1]
            fullname = records[0][3]

def build_html(direction):
    path = f".\\templates\\{direction}.html"
    with open(path, "r") as text_file:
        lines = text_file.readlines()
    text_file.close()
    rem = 0
    res = ""
    for i in range (len(lines)):
        if rem == 0:
            res += lines[i]
        if lines[i] == "\t\t\t\tvar myArray = [\n":
            rem = 1
        elif lines[i] == "\t\t\t\t]\n":
            if direction == 'home':
                res += select_table_desc() + lines[i]
            else:
                res += select_table_published() + lines[i]
            rem = 0
    with open(path, "w") as file:
        file.write(res)
    file.close()
    return 0
"""
#GET
def get_user_id(credential): # get user id from access token
    for i in range(len(credential)):
        if credential[i] == " ":
            username = credential[(i+1):]
            break
    cursor.execute(f"SELECT * FROM public.users WHERE login = '{username}'")
    records = list(cursor.fetchall())
    return records[0][0]

def get_topic(article_id): # get article topic by article id
    cursor.execute(f"SELECT * FROM public.article_topic WHERE article_id={article_id}")
    article_desc = list(cursor.fetchall())
    cursor.execute(f"SELECT * FROM public.topic WHERE id={article_desc[0][1]}")
    topic_desc = list(cursor.fetchall())
    topic = topic_desc[0][1]
    return topic

def get_topic_id(topic):
    cursor.execute(f"SELECT * FROM public.topic WHERE name='{topic}'")
    rec = list(cursor.fetchall())
    return rec[0][0]
    """
    if topic == "science":
        topic_id = 1
    elif topic == "art":
        topic_id = 2
    elif topic == "history":
        topic_id = 3
    else:
        topic_id = 4
    return topic_id
    """

def get_article_status(status_id):
    cursor.execute(f"SELECT * FROM public.status WHERE id={status_id}")
    rec = list(cursor.fetchall())
    return rec[0][1]
    """
    if status_id == 1:
        return "draft"
    elif status_id == 2:
        return "published"
    elif status_id == 3:
        return "aprooved"
    else:
        return "denied"
    """

def get_title(article_name):
    cursor.execute(f"SELECT * FROM public.article WHERE name = '{article_name}'")
    records = list(cursor.fetchall())
    return records[0][2]

def get_rating(article_id):
    cursor.execute(f"SELECT * FROM public.rating WHERE article_id={article_id} and isdeleted={False}")
    rating_desc = list(cursor.fetchall())
    count = 0
    for log in rating_desc:
        count += log[4]
    if count!=0:
        reviews = round(count/len(rating_desc), 1)
    else:
        reviews = 0
    return reviews

def get_current_date():
    time = str(datetime.datetime.now())
    time = time[0:10]
    res = ""
    for char in time:
        if char != "-":
            res += char
        else:
         res += '.'
    return res

def get_authors(article_id): # get article authors in one str
    cursor.execute(f"SELECT * FROM public.article_writer WHERE article_id={article_id}") # selecting article's authors
    article_desc = list(cursor.fetchall())
    authors = ""
    for log in article_desc: # getting authors of article
        cursor.execute(f"SELECT * FROM public.users WHERE id={log[1]}")
        desc = list(cursor.fetchall())
        authors += desc[0][3] + ", " # form str of authors
    authors=authors[0:len(authors)-2] # remove ", " from end of authors str
    return authors

def get_authors_username(article_id): # get article authors in one str
    cursor.execute(f"SELECT * FROM public.article_writer WHERE article_id={article_id}") # selecting article's authors
    article_desc = list(cursor.fetchall())
    authors = ""
    for log in article_desc: # getting authors of article
        cursor.execute(f"SELECT * FROM public.users WHERE id={log[1]}")
        desc = list(cursor.fetchall())
        authors += desc[0][1] + ", " # form str of authors
    authors=authors[0:len(authors)-2] # remove ", " from end of authors str
    return authors

def get_hashtags(article_id):
    cursor.execute(f"SELECT * FROM public.article_hashtag WHERE article_id={article_id}")
    hashtag_desc = list(cursor.fetchall())
    hashtags = ""
    for rec in hashtag_desc:
        hashtags += "#" + rec[1] + ", "
    if hashtags != "":
        hashtags = hashtags[0:(len(hashtags)-2)]
    return hashtags

#SELECT
def select_role(roles):
    res = [0, 0, 0, 0]
    for role in roles:
        if role == 1:
            res[0]=1
        elif role == 2:
            res[1]=1
        elif role == 3:
            res[2]=1
        elif role == 4:
            res[3]=1
    return res

def select_table_desc(credentials):
    if credentials[0] == '5':
        return exception(status.HTTP_423_LOCKED, "You are banned on server.")
    cursor.execute(f"SELECT * FROM public.article WHERE isdeleted={False}")
    records = list(cursor.fetchall())
    array = []
    for rec in records:
        article_id = rec[0]
        name = rec[1]
        date = rec[5]
        cursor.execute(f"SELECT * FROM public.article_status WHERE article_id={article_id}")
        check = list(cursor.fetchall())
        if check[0][1] == 3:
            cursor.execute(f"SELECT * FROM public.article_writer WHERE article_id={article_id}")
            article_desc = list(cursor.fetchall())
            authors = get_authors(article_id)
            topic = get_topic(article_id)
            reviews = get_rating(article_id)
            cursor.execute(f"SELECT * FROM public.user_read WHERE article_id={article_id} and isread={True}")
            views_check = list(cursor.fetchall())
            views = len(views_check)
            hashtags = get_hashtags(article_id)
            array += {'name':name, 'author': authors, 'topic': topic, 'hashtags': hashtags, 'views': views, 'reviews': reviews, 'date': date},
    return array

def select_table_published(credentials):
    if credentials[0] == '5':
        return exception(status.HTTP_423_LOCKED, "You are banned on server.")
    elif credentials[0] != '1' and credentials[0] != '2' and credentials[1] != '2':
        return exception(status.HTTP_423_LOCKED, "You aren't administrator or moderator.")
    cursor.execute(f"SELECT * FROM public.article_status WHERE status_id={2}")
    records = list(cursor.fetchall())
    array = []
    for rec in records:
        article_id = rec[0]
        cursor.execute(f"SELECT * FROM public.article WHERE id={article_id}")
        article_desc = list(cursor.fetchall())
        name = article_desc[0][1]
        date = article_desc[0][5]
        cursor.execute(f"SELECT * FROM public.article_writer WHERE article_id={article_id}")
        check = list(cursor.fetchall())
        authors = get_authors(article_id)
        topic = get_topic(article_id)
        reviews = 0
        views = 0
        hashtags = get_hashtags(article_id)
        array += {'name': name, 'author': authors, 'topic': topic, 'hashtags': hashtags, 'views': views, 'reviews': reviews, 'date': date},
    return array

def select_table_personal(credentials):
    if credentials[0] == '5':
        return exception(status.HTTP_423_LOCKED, "You are banned on server.")
    if credentials[0] != '1' and credentials[0] != '3' and credentials[1] != '3':
        return exception(status.HTTP_423_LOCKED, "You aren't administrator or writer.")
    user_id = get_user_id(credentials) # get user id
    cursor.execute(f"SELECT * FROM public.article_writer WHERE user_id={user_id}") # select articles where user is author or redactor
    records = list(cursor.fetchall())
    array = []
    for rec in records:
        article_id = rec[0]
        cursor.execute(f"SELECT * FROM public.article WHERE id={article_id}") # select article info
        article_desc = list(cursor.fetchall())
        name = article_desc[0][1] # get article name
        date = article_desc[0][5] # get date of article's creation/publication
        cursor.execute(f"SELECT * FROM public.article_writer WHERE article_id={article_id}") # select article's writers
        check = list(cursor.fetchall())
        authors = get_authors(article_id)
        topic = get_topic(article_id) # get topic id
        reviews = get_rating(article_id) # get article's rating
        cursor.execute(f"SELECT * FROM public.user_read WHERE article_id={article_id} and isread={True}") # select article's views info
        views_check = list(cursor.fetchall())
        views = len(views_check) # get number of article views
        hashtags = get_hashtags(article_id)
        array += {'name': name, 'author': authors, 'topic': topic, 'hashtags': hashtags, 'views': views, 'reviews': reviews, 'date': date},
    return array

def select_reviews(credentials, article_id):
    #author, username, rate, review, date
    if credentials[0] == '5':
        return exception(status.HTTP_423_LOCKED, "You are banned on server.")
    user_id = get_user_id(credentials)
    array = []
    cursor.execute(f"SELECT * FROM public.article WHERE id={article_id}")
    records = list(cursor.fetchall())
    if records != []:
        article_name = records[0][1]
        path = f".\\reviews\\{article_name}.txt"
        with open(path, "r") as text_file:
            lines = text_file.readlines()
        text_file.close()
        for line in lines:
            author_id = ""
            for i in range(len(line)):
                if line[i] == ':':
                    start = i
                    break
                else:
                    author_id += line[i]
            if int(author_id) == int(user_id):
                continue
            else:
                review = line[start+1:]
                review = review[0:len(review)-2]
                cursor.execute(f"SELECT * FROM public.users WHERE id={author_id}")
                author_desc = list(cursor.fetchall())
                username = author_desc[0][1]
                author = author_desc[0][3]
                cursor.execute(f"SELECT * FROM public.rating WHERE user_id={author_id} and article_id={article_id}")
                rating_desc = list(cursor.fetchall())
                rate = rating_desc[0][4]
                date = rating_desc[0][3]
                array += {'author': author, 'username': username, 'rate': rate, 'comment': review, 'date': date},
    return array

#for selecting articles aprooved recently
def select_table_recent(credentials):
    if credentials[0] == '5':
        return exception(status.HTTP_423_LOCKED, "You are banned on server.")
    current_date = get_current_date() # get date
    user_id = get_user_id(credentials) # get user id
    cursor.execute(f"SELECT * FROM public.article WHERE isdeleted={False}") # selecting all not deleted articles
    records = list(cursor.fetchall())
    array = []
    for rec in records:
        article_id = rec[0] # get article id
        name = rec[1] # get article name
        date = rec[5] # get date of aprooving article
        cursor.execute(f"SELECT * FROM public.article_status WHERE article_id={article_id}") # selecting articles's status
        check = list(cursor.fetchall())
        cursor.execute(f"SELECT * FROM public.user_read WHERE user_id={user_id} and article_id={article_id}") # checking which articles user has already read
        read_check = list(cursor.fetchall())
        if check[0][1] == 3 and (read_check[0][2] != True or rec[5] == current_date): # checking if article is aprooved, if user read current article or article was aprooved today  
            cursor.execute(f"SELECT * FROM public.article_writer WHERE article_id={article_id}") # selecting article's authors
            article_desc = list(cursor.fetchall())
            authors = get_authors(article_id)
            topic = get_topic(article_id) # getting article's topic
            reviews = get_rating(article_id) # getting article's rating 
            cursor.execute(f"SELECT * FROM public.user_read WHERE article_id={article_id} and isread={True}")
            views_check = list(cursor.fetchall())
            views = len(views_check) # get number of article views
            hashtags = get_hashtags(article_id)
            array += {'name': name, 'author': authors, 'topic': topic, 'hashtags': hashtags, 'views': views, 'reviews': reviews, 'date': date}, # form array
    return array


"""  
#TESTS
if __name__ == '__main__':
    test = "1234557645324"
    print(test[1:])
    print(test[1:].isdigit())
    test = {'science': [{'test': 1, 'res': 2}, {'test': 2, 'res': 1}], 'art': [{'test': 3, 'res': 4}, {'test': 3, 'res': 5}]}
    for rec in test:
        print(rec) # science, art
        print(test[f"{rec}"]) # [{'test': 1, 'res': 2}, {'test': 2, 'res': 1}], [{'test': 3, 'res': 4}, {'test': 3, 'res': 5}]
    time = str(datetime.datetime.now())
    time = time[0:10]
    print(time)
    array = select_table_desc()
    print(array)
    conn = psycopg2.connect(database="server_db",
                                user="postgres",
                                password="postgres",
                                host="localhost",
                                port="5432")
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM role_user WHERE user_id=4")
    records = list(cursor.fetchall())
    for i in range(len(records)):
        print(records[i], i)

if __name__ == '__main__':
    path = f".\\articles\\test3.txt"
    with open(path, "r") as text_file:
        lines = text_file.readlines()
    text_file.close()
    print(lines)
    form_text(path)
    with open(".\\reviews\\test2.txt", "w") as file:
        file.write("")
    file.close()
    with open(".\\reviews\\test3.txt", "w") as file:
        file.write("")
    file.close()
    with open(".\\reviews\\denis.txt", "w") as file:
        file.write("")
    file.close()
    path = f".\\articles\\copy.txt"
    with open(path, "w") as file:
        file.write("Your text goes here. And reads like this.")
    text_file = open(path, "r")
    lines = text_file.readlines()
    print(lines[0])
    with open("copy.txt", "w") as file:
        file.write("Your text goes here")
    conn = psycopg2.connect(database="server_db",
                                user="postgres",
                                password="postgres",
                                host="localhost",
                                port="5432")
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM role_user WHERE user_id=4")
    records = list(cursor.fetchall())
"""
    
    

 