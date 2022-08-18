import psycopg2, cv2, datetime
from fastapi import status, HTTPException
from src.exceptions import exception

conn = psycopg2.connect(database="server_db",
                        user="postgres",
                        password="postgres",
                        host="localhost",
                        port="5432")

cursor = conn.cursor()

#AUTHORIZATION
def sign_in_user(form_data): # main: "/sign_in"
    cursor.execute(f"SELECT * FROM public.users WHERE login='{form_data.username}' AND password='{form_data.password}'")
    records = list(cursor.fetchall())
    if records == []: # check if there is user in database
        return exception(status.HTTP_401_UNAUTHORIZED, "Incorrect username or password.")
    cursor.execute(f"SELECT * FROM public.role_user WHERE user_id={records[0][0]}") # get user's roles
    user_desc = list(cursor.fetchall())
    # form user's token
    token = "" 
    for desc in user_desc:
        if desc[1] != 5:
            token += f"{desc[1]}"
        else:
            token = 5
            break
    token += " " + form_data.username # token "{roles} {username}"
    stop_sessions_check(records[0][0], 1) # check if administrator stopped sessions
    save_event("sign_in", f"{form_data.username} signed in.", records[0][0]) # save user's 'sign in' event
    return {'access_token': token}

def sign_up_user(fullname, username, password, confirm_password): # main: "/sign_up"
    stop_sessions_check(0, 1) # check if administrator stopped sessions
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
            article_desc = list(cursor.fetchall()) # get all approved articles
            for article in article_desc: # mark all approved as 'unread' for the user
                cursor.execute(f"INSERT INTO public.user_read (user_id, article_id, isread) VALUES ({records[0][0]}, {article[0]}, {False})")
            conn.commit()
            save_event("sign_up", f"{username} is added to database.", records[0][0])
            return {"username": username, "password": password}

def stop_sessions_check(user_id, sign_in): # check if administrator stopped all sessions
    cursor.execute(f"SELECT * FROM public.role_user WHERE user_id={user_id} and role_id=1") # check if user is administrator
    role_desc = list(cursor.fetchall())
    if role_desc != [] and sign_in == 1: # check if administrator tries to sign_in
        return 0
    if sign_in == 0:
        cursor.execute(f"SELECT * FROM public.events WHERE user_id={user_id} and event='sign_in'") # get user's 'sign_in' events
        records = list(cursor.fetchall())
        date1 = records[len(records)-1][4] # get last user's 'sign_in' event date and time
        time1 = records[len(records)-1][5]
    cursor.execute(f"SELECT * FROM public.events WHERE event='stop_all_sessions'") #  or event='stop_sessions_except'
    records = list(cursor.fetchall())
    if records == [] and role_desc != []:
        return 0
    elif records != [] and role_desc != []:
        date2 = records[len(records)-1][4]
        time2 = records[len(records)-1][5]
        desc = get_time_defference(date1, date2, time1, time2)
        if desc['greater'] == 2: # check if sessions was stopped after administrator signed in
            return exception(status.HTTP_423_LOCKED, "Server's sessions was stopped. You need to sign in again.")
        return 0
    # user isn't administrator
    cursor.execute(f"SELECT * FROM public.events WHERE event='stop_all_sessions' or event='stop_sessions_except'")
    records = list(cursor.fetchall())
    date2 = records[len(records)-1][4] # get last 'stop sessions' event date and time
    time2 = records[len(records)-1][5]
    if sign_in == 0:
        desc = get_time_defference(date1, date2, time1, time2)
        if desc['greater'] == 2: # check if 'stop sessions' event was launched after user's request
            return exception(status.HTTP_423_LOCKED, "Server's sessions was stopped. You need to sign in again.")
        return 0
    current_date = get_current_date()
    current_time = get_current_time()
    if sign_in == 1: # check if 'stop sessions' event was launched after user tries to sign in
        check = get_time_defference(current_date, date2, current_time, time2)
        if check['difference']<=3600: # check if user tries to sign in when 'stop sessions' event was launched less than hour ago
            return exception(status.HTTP_423_LOCKED, "Server's sessions was stopped. Try later.") 
        return 0
    return exception(status.HTTP_423_LOCKED, "Something went wrong...") # everything is right

#REVIEWS
def send_review(article_name, action, rate, review_text, credentials): # main:"/archive/{article_name}"
    user_id = get_user_id(credentials) # get user id
    stop_sessions_check(user_id, 0) # check if administrator stopped sessions
    article_desc = authorization_check_article(credentials, article_name) # get article info
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
            lines += f"\n{user_id}:{review_text.review_text}\n" # append user review
            text = form_article(lines)
            with open(path, "w") as file: # update file with reviews
                file.write(text)
            file.close()
            cursor.execute(f"INSERT INTO public.rating (user_id, article_id, date, rate, isdeleted) VALUES ({user_id}, {article_id}, '{date}', {rate}, {False})")
        event = f"Review to {article_name} is sent."
    else: # if user wants to delete his review
        if user_review['rating'] == None: # check if user didn't writte review for the article
            return exception(status.HTTP_400_BAD_REQUEST, "You didn't write review for this article.")
        event = f"Review is deleted from {article_name}."
        cursor.execute(f"UPDATE public.rating SET isdeleted={True} WHERE user_id={user_id} and article_id={article_id}") # mark user review as deleted
        delete_review(article_name, user_id, article_id, path) # remove user's review from file
    conn.commit()
    article_desc = authorization_check_article(credentials, article_name) # update article info
    save_event("review_update", event, user_id)
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
def update_role(username, role, action, credentials): # main: "/role"
    admin_id = get_user_id(credentials) # get user id
    stop_sessions_check(admin_id, 0) # check if administrator stopped sessions
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
                save_event("role_update", f"Role '{role}' is seccessfuly removed from {username}.", admin_id)
                return f"Role '{role}' is seccessfuly removed from {username}."
        else:
            # adding 'reader' role to user
            cursor.execute(f"INSERT INTO public.role_user (user_id, role_id) VALUES ({user_id}, {role_id})")
            cursor.execute(f"DELETE FROM public.role_user WHERE user_id={user_id} and role_id={4}")
            save_event("role_update", f"Role '{role}' is seccessfuly added to {username}.", admin_id)
            conn.commit()
            return f"Role '{role}' is seccessfuly added to {username}."
    else: # if administrator chooses 'ban' in role field
        # if administrator wants to ban user or remove user from ban list
        if action == 'remove':
            # giving user 'reader' role back
            cursor.execute(f"UPDATE public.role_user SET role_id=4 WHERE user_id={user_id} and role_id={role_id}")
            cursor.execute(f"UPDATE public.users SET banned={False} WHERE id={user_id}")
            save_event("role_update", f"{username} is removed from banlist.", admin_id)
            conn.commit()
            return f"{username} is removed from banlist."
        else:
            # sending user into banlist
            cursor.execute(f"UPDATE public.role_user SET role_id={role_id} WHERE user_id={user_id}")
            cursor.execute(f"UPDATE public.users SET banned={True} WHERE id={user_id}")
            save_event("role_update", f"{username} is banned now.", admin_id)
            conn.commit()
            return f"{username} is banned now."

def stop_sessions(action, credentials): # main: "/session_settings"
    admin_id = get_user_id(credentials) # get user id
    stop_sessions_check(admin_id, 0) # check if administrator stopped sessions
    if credentials[0] == '5': # check if user is banned
        return exception(status.HTTP_423_LOCKED, "You are banned on server.")
    elif credentials[0] != '1':
        return exception(status.HTTP_423_LOCKED, "You aren't administrator.")
    if action == "stop_all_sessions":
        save_event("stop_all_sessions", "Adminnistrator stopped all sessions.", admin_id)
        return "All sessions are stoped for 60 minutes."
    if action == "stop_sessions_except":
        save_event("stop_sessions_except", "Adminnistrator stopped all sessions except administrator session.", admin_id)
        return "All sessions except yours are stoped for 60 minutes."

def save_event(event_type, description, user_id):
    date = get_current_date()
    time = get_current_time()
    cursor.execute(f"INSERT INTO public.events (user_id, event, description, date, time) VALUES ({user_id}, '{event_type}', '{description}', '{date}', '{time}')")
    conn.commit()
    return 0
    

#ARTICLE EDITS FOR WRITERS
def create_article(topic, article_name, title, credentials): # main: "/create"
    user_id = get_user_id(credentials) # get user id
    stop_sessions_check(user_id, 0) # check if administrator stopped sessions
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
            save_event("article_create", f"{article_name} is created", user_id)
            return "Article is created."

def authorization_editors_check(article_name, credentials): # main: "/editors/{article_name}"
    user_id = get_user_id(credentials) # get user id
    stop_sessions_check(user_id, 0) # check if administrator stopped sessions
    if credentials[0] == '5': # check if user is banned
        return exception(status.HTTP_423_LOCKED, "You are banned on server.")
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

def update_authors(article_name, username, role, action, credentials): # main: "/editors/{article_name}"
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
            event=f"{username} is now redactor of {article_name}."
        else:
            if username in author_desc['authors']: # if user is redactor of article he will become an author
                cursor.execute(f"UPDATE public.article_writer SET isauthor={True} WHERE article_id={author_desc['article_id']} and user_id={user_id}")
            else: # insert user as author if he isn't redactor or author of article
                cursor.execute(f"INSERT INTO public.article_writer (article_id, user_id, isauthor) VALUES ({author_desc['article_id']}, {user_id}, {True})")
            event=f"{username} is now author of {article_name}."
    elif action == "remove":
        if not username in author_desc['authors']: # check if username was inputed correct
            return exception(status.HTTP_400_BAD_REQUEST, "This user isn't a redactor of this article.")
        else:
            if role == "redactor": # if user is removed from redactors he will lose rights to update article
                event=f"{username} isn't redactor of {article_name} anymore."
                cursor.execute(f"DELETE FROM public.article_writer WHERE article_id={author_desc['article_id']} and user_id={user_id}")
            else: # if user is removed from authors he will become a redactor
                event=f"{username} is now redactor of {article_name}."
                cursor.execute(f"UPDATE public.article_writer SET isauthor={False} WHERE article_id={author_desc['article_id']} and user_id={user_id}")
    conn.commit()
    author_desc = authorization_editors_check(article_name, credentials) # update authors info
    save_event("authors_update", event, writer_id)
    return {'event': event, 'author_desc': author_desc}

def authorization_check_draft(credentials, article): # main: "/create/{article_name}"
    user_id = get_user_id(credentials) # get user id
    stop_sessions_check(user_id, 0) # check if administrator stopped sessions
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


def update_draft(article_name, action, article, credentials): # main: "/create/{article_name}"
    user_id = get_user_id(credentials) # get user id
    stop_sessions_check(user_id, 0) # check if administrator stopped sessions
    article_desc = authorization_check_draft(credentials, article_name) # get article info
    path = f".\\articles\\{article_name}.txt"
    cursor.execute(f"SELECT * FROM public.article WHERE name='{article_name}'")
    records=list(cursor.fetchall())
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
            save_event("status_update", f"{article_name} is draft now.", user_id)
            return {'event': f"{article_name} is draft now.", 'article_info': article_desc}
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
            article_desc['hashtags'] = get_hashtags(article_desc['article_id']) # update article tags
        event=f"{article_name} is saved."
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
            article_desc['hashtags'] = get_hashtags(article_desc['article_id']) # update article tags
        article_desc['article_status'] = 2
        cursor.execute(f"UPDATE public.article_status SET status_id={2} WHERE article_id={records[0][0]}")
        cursor.execute(f"UPDATE public.article SET date='{get_current_date()}' WHERE name='{article_name}'")
        event=f"{article_name} is published."
    elif action == "back_to_draft":
        return exception(status.HTTP_400_BAD_REQUEST, f"{article_name} is draft already.")
    else: # if redactor tries do something exept 'save'
        return exception(status.HTTP_423_LOCKED, "You aren't an author of this article.")
    conn.commit()
    save_event("status_update", event, user_id)
    return article_desc

#PUBLISHED FOR MODERATORS
def authorization_check_published(article_name, credentials):
    user_id = get_user_id(credentials) # get user id
    stop_sessions_check(user_id, 0) # check if administrator stopped sessions
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
        path = f".\\articles\\{article_name}.txt"
        text = form_text(path)
        hashtags = get_hashtags(article_id)
        return {'user_id': user_id, 'article_id': article_id, 'hashtags': hashtags, 'title': title, 'article_text': text, 'article_status': 2, 'date': date}

def update_article_status(article_name, action, reason, credentials): # main: "/published/{article_name}"
    article_desc = authorization_check_published(article_name, credentials) # get article info
    user_id = get_user_id(credentials)
    if action == "approve":
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
        save_event("status_update", f"{article_name} is approved.", user_id)
        return {'event': f"{article_name} is approved.", 'article_desc': article_desc}
    else:
        if reason == None or reason == "":
            return exception(status.HTTP_400_BAD_REQUEST, "You must enter reason of rejection.")
        date = get_current_date()
        cursor.execute(f"UPDATE public.article_status SET status_id={4} WHERE article_id={article_id}")
        cursor.execute(f"UPDATE public.article SET description='{reason}', isdeleted={True}, date='{date}' WHERE id={article_id}")
        conn.commit()
        article_desc['article_status'] = 4
        article_desc['date'] = date
        save_event("status_update", f"{article_name} is denied. Reason: {reason}", user_id)
        return {'event': f"{article_name} is denied. Reason: {reason}", 'article_desc': article_desc}

#CHECK
def field_check(field, space_check):
    for char in field:
        if char == "'" or (char == " " and space_check == 1):
            return 0
    return 1
        
def authorization_check_article(credentials, article_name): # main: "/archive/{article_name}"
    user_id = get_user_id(credentials) # get user id
    stop_sessions_check(user_id, 0) # check if administrator stopped sessions
    if credentials[0] == '5':
        return exception(status.HTTP_423_LOCKED, "You are banned on server.")
    if field_check(article_name, 0) == 0:
        return exception(status.HTTP_404_NOT_FOUND, "There is no such article in database.")
    cursor.execute(f"SELECT * FROM public.article WHERE name='{article_name}' and isdeleted = {False}")
    records = list(cursor.fetchall())
    if records == []:
        return exception(status.HTTP_404_NOT_FOUND, "There is no such article in database.")       
    article_id = records[0][0]
    cursor.execute(f"SELECT * FROM public.article_status WHERE article_id={article_id}")
    check = list(cursor.fetchall())
    status_id = check[0][1]
    #checking if article is approved.
    if status_id != 3:
        cursor.execute(f"SELECT * FROM public.article_writer WHERE article_id={article_id} and user_id={user_id}")
        check = list(cursor.fetchall())
        if check == []:
            return exception(status.HTTP_400_BAD_REQUEST, "This article isn't approved.")
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

def hashtag_add(article_id, hashtag):
    cursor.execute(f"DELETE FROM public.article_hashtag WHERE article_id={article_id}")
    conn.commit()
    start = 0
    new_tag = ""
    for i in range(len(hashtag)):
        if hashtag[i] == '#':
            if start == i:
                continue
            elif start == i-1:
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

#SEARCH FUNCTIONS
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
        return search_by_name(array, search_field, search_value) # update article list with search value
    else:
        if search_value == None:
            array = sort_articles(array)
            return {f"{topic_filter}": array[f"{topic_filter}"]}
        array = search_by_name(array, search_field, search_value) # update article list with search value
        return {f"{topic_filter}": array[f"{topic_filter}"]}

#GET
def get_user_id(credential): # get user id from access token
    for i in range(len(credential)):
        if credential[i] == " ":
            username = credential[(i+1):]
            break
    cursor.execute(f"SELECT * FROM public.users WHERE login = '{username}'")
    records = list(cursor.fetchall())
    return records[0][0]

def crypt_role(role):
    cursor.execute(f"SELECT * FROM public.role WHERE name='{role}'")
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

def get_article_status(status_id):
    cursor.execute(f"SELECT * FROM public.status WHERE id={status_id}")
    rec = list(cursor.fetchall())
    return rec[0][1]

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

def get_current_time():
    time = str(datetime.datetime.now())
    time = time[11:19]
    return time

def get_time_defference(date1, date2, time1, time2):
    hour1 = int(time1[0:2])
    minutes1 = int(time1[3:5])
    seconds1 = int(time1[6:])
    hour2 = int(time2[0:2])
    minutes2 = int(time2[3:5])
    seconds2 = int(time2[6:])
    time_value1 = hour1*3600+minutes1*60+seconds1
    time_value2 = hour2*3600+minutes2*60+seconds2
    year1 = int(date1[0:4])
    year2 = int(date2[0:4])
    month1 = int(date1[5:7])
    month2 = int(date2[5:7])
    day1 = int(date1[8:])
    day2 = int(date2[8:])
    num = 1*(time_value1>time_value2)+2*(time_value1<time_value2)
    difference = abs(time_value1-time_value2)
    if year1 > year2:
        return {'greater': 1, 'difference': difference+3601}
    elif year1 < year2:
        return {'greater': 2, 'difference': difference+3601}
    if month1 > month2:
        return {'greater': 1, 'difference': difference+3601}
    elif month1 < month2:
        return {'greater': 2, 'difference': difference+3601}
    if day1 > day2:
        return {'greater': 1, 'difference': (difference-86339)*(86339<difference)+difference*(86339>difference)}
    elif day1 < day2:
        return {'greater': 2, 'difference': (difference-86339)*(86339<difference)+difference*(86339>difference)}
    return {'greater': num, 'difference': difference}

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

#SELECT ARTICLES AND REVIEWS INFO
def select_table_desc(credentials): # main: "/archive" (select all approved articles)
    # output dict {name, authors, topic, hashtags, views, reviews, date}
    user_id = get_user_id(credentials) # get user id
    stop_sessions_check(user_id, 0) # check if administrator stopped sessions
    if credentials[0] == '5': # check if user is banned
        return exception(status.HTTP_423_LOCKED, "You are banned on server.")
    cursor.execute(f"SELECT * FROM public.article WHERE isdeleted={False}") # select all not-deleted articles
    records = list(cursor.fetchall())
    array = []
    for rec in records: # for every article check if it's approved and get name, authors, topic, hashtags, number of views, rating and date of approovation
        article_id = rec[0]
        name = rec[1]
        date = rec[5]
        cursor.execute(f"SELECT * FROM public.article_status WHERE article_id={article_id}")
        check = list(cursor.fetchall())
        if check[0][1] == 3: # check if article is approved
            cursor.execute(f"SELECT * FROM public.article_writer WHERE article_id={article_id}")
            article_desc = list(cursor.fetchall())
            authors = get_authors(article_id)
            topic = get_topic(article_id)
            reviews = get_rating(article_id)
            cursor.execute(f"SELECT * FROM public.user_read WHERE article_id={article_id} and isread={True}")
            views_check = list(cursor.fetchall())
            views = len(views_check)
            hashtags = get_hashtags(article_id) # get article's hashtags
            array += {'name':name, 'author': authors, 'topic': topic, 'hashtags': hashtags, 'views': views, 'reviews': reviews, 'date': date},
    return array

def select_table_published(credentials): # main "/published" (select all articles with 'published' status)
    # output dict {name, authors, topic, hashtags, views, reviews, date}
    user_id = get_user_id(credentials) # get user id
    stop_sessions_check(user_id, 0) # check if administrator stopped sessions
    if credentials[0] == '5': # check if user is banned
        return exception(status.HTTP_423_LOCKED, "You are banned on server.")
    elif credentials[0] != '1' and credentials[0] != '2' and credentials[1] != '2': # check if user is administrator or moderator
        return exception(status.HTTP_423_LOCKED, "You aren't administrator or moderator.")
    cursor.execute(f"SELECT * FROM public.article_status WHERE status_id={2}") # select all articles with 'published' status
    records = list(cursor.fetchall())
    array = []
    for rec in records: # for every article get name, authors, topic, hashtags, number of views, rating and date of publication
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
        hashtags = get_hashtags(article_id) # get article's hashtags
        array += {'name': name, 'author': authors, 'topic': topic, 'hashtags': hashtags, 'views': views, 'reviews': reviews, 'date': date},
    return array

def select_table_personal(credentials): # main: "/workshop" (select user's articles)
    # output dict {name, authors, topic, hashtags, views, reviews, date}
    user_id = get_user_id(credentials) # get user id
    stop_sessions_check(user_id, 0) # check if administrator stopped sessions
    if credentials[0] == '5': # check if user is banned
        return exception(status.HTTP_423_LOCKED, "You are banned on server.")
    if credentials[0] != '1' and credentials[0] != '3' and credentials[1] != '3': # check if user is administrator or writer
        return exception(status.HTTP_423_LOCKED, "You aren't administrator or writer.")
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
        hashtags = get_hashtags(article_id) # get article's hashtags
        array += {'name': name, 'author': authors, 'topic': topic, 'hashtags': hashtags, 'views': views, 'reviews': reviews, 'date': date},
    return array

def add_status_to_array(desc):
    new_desc = []
    for topic in desc:
        if desc[f"{topic}"] == None:
            continue
        for record in desc[f"{topic}"]:
            cursor.execute(f"SELECT * FROM public.article WHERE name='{record['name']}'")
            records=list(cursor.fetchall())
            cursor.execute(f"SELECT * FROM public.article_status WHERE article_id={records[0][0]}")
            article_desc = list(cursor.fetchall())
            article_status = get_article_status(article_desc[0][1])
            new_desc += {'name': record['name'], 'author': record['author'], 'topic': record['topic'], 'status': article_status, 'hashtags': record['hashtags'], 'views': record['views'], 'reviews': record['reviews'], 'date': record['date']},
    return new_desc
    

def select_reviews(credentials, article_id): # main: "/archive/{article_name}" (select all article reciews)
    # output dict {author, username, rate, review, date}
    user_id = get_user_id(credentials) # get user id
    stop_sessions_check(user_id, 0) # check if administrator stopped sessions
    if credentials[0] == '5':
        return exception(status.HTTP_423_LOCKED, "You are banned on server.")
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

def select_table_recent(credentials): # main: "/home" (select articles approved recently)
    # output dict {name, authors, topic, hashtags, views, reviews, date}
    user_id = get_user_id(credentials) # get user id
    stop_sessions_check(user_id, 0) # check if administrator stopped sessions
    if credentials[0] == '5': # check if user is banned
        return exception(status.HTTP_423_LOCKED, "You are banned on server.")
    current_date = get_current_date() # get date
    cursor.execute(f"SELECT * FROM public.article WHERE isdeleted={False}") # select all not deleted articles
    records = list(cursor.fetchall())
    array = []
    for rec in records: # for every article check if it's approved and get name, authors, topic, hashtags, number of views, rating and date of approovation
        article_id = rec[0] # get article id
        name = rec[1] # get article name
        date = rec[5] # get date of approving article
        cursor.execute(f"SELECT * FROM public.article_status WHERE article_id={article_id}") # select articles's status
        check = list(cursor.fetchall())
        cursor.execute(f"SELECT * FROM public.user_read WHERE user_id={user_id} and article_id={article_id}") # check which articles user has already read
        read_check = list(cursor.fetchall())
        if check[0][1] == 3 and (read_check[0][2] != True or rec[5] == current_date): # check if article is approved, if user read current article or article was approved today  
            cursor.execute(f"SELECT * FROM public.article_writer WHERE article_id={article_id}") # select article's authors
            article_desc = list(cursor.fetchall())
            authors = get_authors(article_id)
            topic = get_topic(article_id) # get article's topic
            reviews = get_rating(article_id) # get article's rating 
            cursor.execute(f"SELECT * FROM public.user_read WHERE article_id={article_id} and isread={True}")
            views_check = list(cursor.fetchall())
            views = len(views_check) # get number of article views
            hashtags = get_hashtags(article_id) # get article's hashtags
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
def check_writer_uploads():
    cursor.execute(f"SELECT * FROM public.article_status WHERE status_id=2")
    records = list(cursor.fetchall())
    res = 0
    for i in records:
        res+=1
    return res
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